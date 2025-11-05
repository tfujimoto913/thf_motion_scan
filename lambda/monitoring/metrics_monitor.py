"""
Metrics monitoring Lambda - BCR/kappa/override continuous evaluation.

Purpose: Monitor key metrics (BCR, kappa, override_ratio) every 1 minute.
         Detect WARN/FAIL conditions with debounce logic (15min/5min).
         Notify via SNS when threshold breaches persist.

Decision Log: ADR-040 (UI monitoring 2-tier alert design)

Architecture:
  1. EventBridge triggers this Lambda every 1 minute
  2. Fetch BCR/kappa/override metrics from CloudWatch (GetMetricStatistics)
  3. Evaluate thresholds: WARN (BCR<0.5, κ<0.3, override>30%)
                          FAIL (BCR<0.3, κ<0.2, override>50%)
  4. Update DynamoDB state (increment counters if condition persists)
  5. Trigger SNS notification if debounce threshold reached (WARN: 15min, FAIL: 5min)
  6. Emit EMF metrics for monitoring dashboard

CRITICAL:
  - Single data source: CloudWatch metrics (not DynamoDB direct query)
  - Independent per metric × env × rules_version
  - State stored in MetricsMonitoringStateTable (TTL: 90 days)
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# Add src/ to path for sns_notifier import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

try:
    from monitoring.sns_notifier import (
        build_message_payload,
        send_notification as sns_send_notification,
        MessageValidationError,
        SNSNotificationError,
    )
except ImportError as e:
    print(f"Warning: Could not import sns_notifier: {e}")
    # Fallback to legacy notification (for backward compatibility)
    sns_send_notification = None

# --- Configuration ---
METRICS_NAMESPACE = os.getenv("METRICS_NAMESPACE", "THF/MotionScan")
STATE_TABLE_NAME = os.getenv("STATE_TABLE_NAME")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
RULES_VERSION = os.getenv("RULES_VERSION", "v2.1")
DASHBOARD_URL = os.getenv(
    "DASHBOARD_URL", "https://console.aws.amazon.com/cloudwatch/"
)  # TODO: Replace with Streamlit threshold_editor URL

# Thresholds (WARN: 15 consecutive minutes, FAIL: 5 consecutive minutes)
WARN_DEBOUNCE_MINUTES = 15
FAIL_DEBOUNCE_MINUTES = 5

# Metric definitions with thresholds
METRICS_CONFIG = [
    {
        "metric_name": "BCR",
        "cloudwatch_metric": "BalancedCorrectRate",
        "warn_threshold": 0.5,
        "fail_threshold": 0.3,
        "comparison": "less_than",  # BCR lower is worse
    },
    {
        "metric_name": "Kappa",
        "cloudwatch_metric": "CohenKappa",
        "warn_threshold": 0.3,
        "fail_threshold": 0.2,
        "comparison": "less_than",  # Kappa lower is worse
    },
    {
        "metric_name": "OverrideRatio",
        "cloudwatch_metric": "OverrideRatio",
        "warn_threshold": 30.0,
        "fail_threshold": 50.0,
        "comparison": "greater_than",  # Override higher is worse
    },
]

# AWS clients (lazy init)
_cloudwatch_client = None
_dynamodb_client = None
_sns_client = None


def _get_cloudwatch():
    global _cloudwatch_client
    if _cloudwatch_client is None:
        _cloudwatch_client = boto3.client("cloudwatch")
    return _cloudwatch_client


def _get_dynamodb():
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = boto3.resource("dynamodb")
    return _dynamodb_client


def _get_sns():
    global _sns_client
    if _sns_client is None:
        _sns_client = boto3.client("sns")
    return _sns_client


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_timestamp() -> str:
    return _utc_now().isoformat()


# --- Data Models ---
@dataclass
class MetricValue:
    """Represents a single metric evaluation result."""

    metric_name: str
    value: Optional[float]
    status: str  # OK / WARN / FAIL
    timestamp: str


@dataclass
class MonitoringState:
    """DynamoDB state record for a metric."""

    metric_name: str
    env_version: str
    current_state: str  # OK / WARN / FAIL
    warn_count: int
    fail_count: int
    last_check_ts: str
    state_entered_ts: str
    ttl: int


# --- CloudWatch Metrics Fetching ---
def fetch_metric_from_cloudwatch(
    metric_name: str, lookback_minutes: int = 1
) -> Optional[float]:
    """
    Fetch the latest value of a custom metric from CloudWatch.

    Args:
        metric_name: CloudWatch metric name (e.g., BalancedCorrectRate)
        lookback_minutes: Time window to fetch (default: 1 minute)

    Returns:
        Average value of the metric in the time window, or None if no data.
    """
    cw = _get_cloudwatch()
    end_time = _utc_now()
    start_time = end_time - timedelta(minutes=lookback_minutes)

    try:
        response = cw.get_metric_statistics(
            Namespace=METRICS_NAMESPACE,
            MetricName=metric_name,
            Dimensions=[
                {"Name": "Environment", "Value": ENVIRONMENT},
                {"Name": "RulesVersion", "Value": RULES_VERSION},
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=60,  # 1 minute granularity
            Statistics=["Average"],
        )

        datapoints = response.get("Datapoints", [])
        if not datapoints:
            return None

        # Return the most recent datapoint
        datapoints.sort(key=lambda dp: dp["Timestamp"], reverse=True)
        return datapoints[0].get("Average")

    except ClientError as exc:
        print(f"Failed to fetch metric {metric_name}: {exc}")
        return None


# --- Threshold Evaluation ---
def evaluate_threshold(
    metric_config: Dict[str, Any], value: Optional[float]
) -> str:
    """
    Evaluate metric value against WARN/FAIL thresholds.

    Returns:
        "OK", "WARN", or "FAIL"
    """
    if value is None:
        return "OK"  # No data = no alarm

    comparison = metric_config["comparison"]
    warn_threshold = metric_config["warn_threshold"]
    fail_threshold = metric_config["fail_threshold"]

    if comparison == "less_than":
        if value < fail_threshold:
            return "FAIL"
        elif value < warn_threshold:
            return "WARN"
    elif comparison == "greater_than":
        if value > fail_threshold:
            return "FAIL"
        elif value > warn_threshold:
            return "WARN"

    return "OK"


# --- DynamoDB State Management ---
def load_state(metric_name: str, env_version: str) -> Optional[MonitoringState]:
    """Load monitoring state from DynamoDB."""
    if not STATE_TABLE_NAME:
        return None

    table = _get_dynamodb().Table(STATE_TABLE_NAME)
    try:
        response = table.get_item(
            Key={"metric_name": metric_name, "env_version": env_version}
        )
        item = response.get("Item")
        if not item:
            return None

        return MonitoringState(
            metric_name=item["metric_name"],
            env_version=item["env_version"],
            current_state=item.get("current_state", "OK"),
            warn_count=int(item.get("warn_count", 0)),
            fail_count=int(item.get("fail_count", 0)),
            last_check_ts=item.get("last_check_ts", ""),
            state_entered_ts=item.get("state_entered_ts", ""),
            ttl=int(item.get("ttl", 0)),
        )
    except ClientError as exc:
        print(f"Failed to load state for {metric_name}: {exc}")
        return None


def save_state(state: MonitoringState) -> None:
    """Save monitoring state to DynamoDB."""
    if not STATE_TABLE_NAME:
        return

    table = _get_dynamodb().Table(STATE_TABLE_NAME)
    ttl = int(time.time()) + (90 * 24 * 3600)  # 90 days

    try:
        table.put_item(
            Item={
                "metric_name": state.metric_name,
                "env_version": state.env_version,
                "current_state": state.current_state,
                "warn_count": state.warn_count,
                "fail_count": state.fail_count,
                "last_check_ts": state.last_check_ts,
                "state_entered_ts": state.state_entered_ts,
                "ttl": ttl,
            }
        )
    except ClientError as exc:
        print(f"Failed to save state for {state.metric_name}: {exc}")


# --- Debounce Logic ---
def update_state_with_debounce(
    state: Optional[MonitoringState],
    metric_name: str,
    new_status: str,
    env_version: str,
) -> tuple[MonitoringState, bool]:
    """
    Update state with debounce logic.

    Returns:
        (updated_state, should_notify)
    """
    now = _iso_timestamp()

    if state is None:
        # Initialize new state
        state = MonitoringState(
            metric_name=metric_name,
            env_version=env_version,
            current_state=new_status,
            warn_count=1 if new_status == "WARN" else 0,
            fail_count=1 if new_status == "FAIL" else 0,
            last_check_ts=now,
            state_entered_ts=now,
            ttl=0,
        )
        return state, False

    # Update counters
    state.last_check_ts = now

    if new_status == "OK":
        # Reset all counters
        if state.current_state != "OK":
            state.current_state = "OK"
            state.warn_count = 0
            state.fail_count = 0
            state.state_entered_ts = now
            return state, True  # Notify recovery
        else:
            state.warn_count = 0
            state.fail_count = 0
            return state, False

    elif new_status == "WARN":
        state.warn_count += 1
        state.fail_count = 0  # Reset FAIL counter

        if state.warn_count >= WARN_DEBOUNCE_MINUTES:
            if state.current_state != "WARN":
                state.current_state = "WARN"
                state.state_entered_ts = now
                return state, True  # Notify WARN breach
        return state, False

    elif new_status == "FAIL":
        state.fail_count += 1
        state.warn_count = 0  # Reset WARN counter

        if state.fail_count >= FAIL_DEBOUNCE_MINUTES:
            if state.current_state != "FAIL":
                state.current_state = "FAIL"
                state.state_entered_ts = now
                return state, True  # Notify FAIL breach
        return state, False

    return state, False


# --- SNS Notification ---
def send_notification(
    metric_name: str, state: MonitoringState, value: Optional[float]
) -> None:
    """
    Send SNS notification for state transition (contract-compliant).

    Contract: contracts/sns_notification.yaml (v1.0.0)
    """
    if not SNS_TOPIC_ARN:
        print("SNS_TOPIC_ARN not configured, skipping notification")
        return

    # Fallback to legacy notification if sns_notifier not available
    if sns_send_notification is None:
        _send_legacy_notification(metric_name, state, value)
        return

    # Build human-readable reason
    value_str = f"{value:.3f}" if value is not None else "N/A"

    if state.current_state == "OK":
        reason = f"{metric_name} recovered to normal (current: {value_str})"
    elif state.current_state == "WARN":
        reason = (
            f"{metric_name} has been in WARN state for {state.warn_count} "
            f"consecutive minutes (current: {value_str})"
        )
    elif state.current_state == "FAIL":
        reason = (
            f"{metric_name} in FAIL state for {state.fail_count} consecutive minutes "
            f"(current: {value_str}) - immediate action required"
        )
    else:
        reason = f"{metric_name} state changed to {state.current_state}"

    # Map state to severity
    severity_map = {"OK": "INFO", "WARN": "WARN", "FAIL": "CRITICAL"}
    severity = severity_map.get(state.current_state, "INFO")

    # Build metadata
    metadata = {
        "metric_name": metric_name,
        "current_value": value,
        "warn_count": state.warn_count,
        "fail_count": state.fail_count,
        "warn_debounce_threshold": WARN_DEBOUNCE_MINUTES,
        "fail_debounce_threshold": FAIL_DEBOUNCE_MINUTES,
        "state_entered_ts": state.state_entered_ts,
        "rules_version": RULES_VERSION,
    }

    # Build contract-compliant payload
    try:
        payload = build_message_payload(
            env=ENVIRONMENT,
            overall=state.current_state,
            source="metrics_monitor",
            reason=reason,
            url=DASHBOARD_URL,
            severity=severity,
            metadata=metadata,
        )

        # Send notification
        subject = f"[{state.current_state}] {metric_name} Alert - {ENVIRONMENT}"
        response = sns_send_notification(
            topic_arn=SNS_TOPIC_ARN,
            payload=payload,
            subject=subject,
        )

        print(
            f"✅ SNS notification sent: {metric_name} → {state.current_state} "
            f"(MessageId: {response.get('MessageId', 'N/A')})"
        )

        # Log notification event (for CloudWatch Logs)
        notification_event = {
            "event": "metrics_monitor_notification",
            "metric_name": metric_name,
            "state": state.current_state,
            "severity": severity,
            "message_id": response.get("MessageId"),
            "timestamp": _iso_timestamp(),
        }
        print(json.dumps(notification_event))

    except (MessageValidationError, SNSNotificationError) as exc:
        print(f"❌ Failed to send SNS notification: {exc}")
    except Exception as exc:
        print(f"❌ Unexpected error sending notification: {exc}")


def _send_legacy_notification(
    metric_name: str, state: MonitoringState, value: Optional[float]
) -> None:
    """
    Legacy notification fallback (for backward compatibility).

    DEPRECATED: Use contract-compliant send_notification() instead.
    """
    subject = f"[{ENVIRONMENT}] Metrics Alert: {metric_name} → {state.current_state}"
    message = f"""
Metrics Monitoring Alert

Metric: {metric_name}
Environment: {ENVIRONMENT}
Rules Version: {RULES_VERSION}
Current Value: {value if value is not None else "N/A"}
New State: {state.current_state}
State Entered At: {state.state_entered_ts}

Debounce Counters:
- WARN count: {state.warn_count}/{WARN_DEBOUNCE_MINUTES}
- FAIL count: {state.fail_count}/{FAIL_DEBOUNCE_MINUTES}

Action Required:
{"- Investigate BCR/Kappa/Override degradation" if state.current_state != "OK" else "- Condition resolved"}
{"- Consider rollback if FAIL persists" if state.current_state == "FAIL" else ""}

Dashboard: {DASHBOARD_URL}
""".strip()

    try:
        _get_sns().publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject[:100],  # SNS subject max 100 chars
            Message=message,
        )
        print(f"SNS notification sent (legacy) for {metric_name} → {state.current_state}")
    except ClientError as exc:
        print(f"Failed to send SNS notification: {exc}")


# --- Lambda Handler ---
def handler(event, context):
    """
    EventBridge scheduled Lambda handler (1-minute interval).

    Workflow:
        1. Fetch BCR/kappa/override metrics from CloudWatch
        2. Evaluate thresholds (WARN/FAIL)
        3. Update DynamoDB state with debounce logic
        4. Send SNS notification if threshold breached
        5. Emit EMF metrics for dashboard
    """
    print(f"Metrics monitoring Lambda invoked at {_iso_timestamp()}")
    print(f"Environment: {ENVIRONMENT}, Rules Version: {RULES_VERSION}")

    env_version = f"{ENVIRONMENT}#{RULES_VERSION}"
    results = []

    for metric_config in METRICS_CONFIG:
        metric_name = metric_config["metric_name"]
        cw_metric = metric_config["cloudwatch_metric"]

        # 1. Fetch metric from CloudWatch
        value = fetch_metric_from_cloudwatch(cw_metric)
        print(f"Fetched {metric_name}: {value}")

        # 2. Evaluate threshold
        status = evaluate_threshold(metric_config, value)
        print(f"Evaluated {metric_name}: {status}")

        # 3. Load previous state
        state = load_state(metric_name, env_version)

        # 4. Update state with debounce
        updated_state, should_notify = update_state_with_debounce(
            state, metric_name, status, env_version
        )

        # 5. Save state
        save_state(updated_state)

        # 6. Send notification if needed
        if should_notify:
            send_notification(metric_name, updated_state, value)

        # 7. Collect results for EMF
        results.append(
            {
                "metric_name": metric_name,
                "value": value,
                "status": status,
                "state": updated_state.current_state,
                "warn_count": updated_state.warn_count,
                "fail_count": updated_state.fail_count,
            }
        )

    # 8. Emit EMF metrics (for CloudWatch dashboard)
    emit_emf_metrics(results)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {"timestamp": _iso_timestamp(), "results": results}, default=str
        ),
    }


def emit_emf_metrics(results: List[Dict[str, Any]]) -> None:
    """
    Emit CloudWatch EMF (Embedded Metric Format) for monitoring dashboard.

    Metrics:
        - MetricMonitoringState: 0 (OK), 1 (WARN), 2 (FAIL)
        - WarnCounter: minutes in WARN state
        - FailCounter: minutes in FAIL state
    """
    for result in results:
        metric_name = result["metric_name"]
        state_value = {"OK": 0, "WARN": 1, "FAIL": 2}.get(result["state"], 0)

        # EMF format (printed to stdout, automatically parsed by CloudWatch)
        emf_log = {
            "_aws": {
                "Timestamp": int(_utc_now().timestamp() * 1000),
                "CloudWatchMetrics": [
                    {
                        "Namespace": f"{METRICS_NAMESPACE}/Monitoring",
                        "Dimensions": [
                            ["Environment", "RulesVersion", "MetricName"]
                        ],
                        "Metrics": [
                            {"Name": "MonitoringState", "Unit": "None"},
                            {"Name": "WarnCounter", "Unit": "Count"},
                            {"Name": "FailCounter", "Unit": "Count"},
                        ],
                    }
                ],
            },
            "Environment": ENVIRONMENT,
            "RulesVersion": RULES_VERSION,
            "MetricName": metric_name,
            "MonitoringState": state_value,
            "WarnCounter": result["warn_count"],
            "FailCounter": result["fail_count"],
        }

        print(json.dumps(emf_log))
