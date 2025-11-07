"""
Purpose: Billing Status dashboard page
Responsibility: Display billing metrics, alerts, and auto-suspend/cleanup events
Dependencies: boto3, streamlit
Created: 2025-11-04 by Claude Code
Decision Log: Step 1 - Billing Status tab skeleton

CRITICAL:
- 3-state display: OK/WARN/FAIL based on CloudWatch metrics
- Safety: Display only, no resource modification in Step 1
- Step 2-4 will add AWS operations (dry-run first)
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Project root for config paths
ROOT = Path(__file__).resolve().parents[2]
BILLING_EVENTS_LOG = ROOT / "config" / "thresholds" / "billing_events.jsonl"

# Default thresholds
DEFAULT_WARN_THRESHOLD = 4.0
DEFAULT_FAIL_THRESHOLD = 5.0

# Mock data for fallback (when CloudWatch unavailable)
MOCK_BILLING_DATA = {
    "current_cost_usd": 2.50,
    "threshold_warn_usd": DEFAULT_WARN_THRESHOLD,
    "threshold_fail_usd": DEFAULT_FAIL_THRESHOLD,
    "active_alarms": [],
    "last_actions": [
        {"timestamp": "2025-11-03T10:00:00Z", "action": "auto_suspend", "resource": "i-1234567890abcdef0", "reason": "Low traffic 2h"},
        {"timestamp": "2025-11-02T15:30:00Z", "action": "auto_cleanup", "resource": "vol-0987654321fedcba", "reason": "Unattached 48h"},
    ],
}


def get_billing_state(current_cost: float, warn_threshold: float, fail_threshold: float) -> str:
    """
    What: Determine billing status based on thresholds
    Why: 3-state classification for UI display
    Design Decision: Simple threshold comparison (no hysteresis)

    Args:
        current_cost: Current estimated charges (USD)
        warn_threshold: Warning threshold (USD)
        fail_threshold: Failure threshold (USD)

    Returns:
        "OK" | "WARN" | "FAIL"
    """
    if current_cost >= fail_threshold:
        return "FAIL"
    elif current_cost >= warn_threshold:
        return "WARN"
    else:
        return "OK"


def render_billing_status_card(state: str, current_cost: float, warn_threshold: float, fail_threshold: float):
    """
    What: Display billing status with color-coded indicator
    Why: Quick visual feedback for operators
    Design Decision: Streamlit built-in components (st.success/warning/error)

    Args:
        state: "OK" | "WARN" | "FAIL"
        current_cost: Current cost (USD)
        warn_threshold: WARN threshold (USD)
        fail_threshold: FAIL threshold (USD)
    """
    st.markdown("### 📊 Billing Status")

    if state == "OK":
        st.success(f"✅ **OK** - Billing is within safe range (${current_cost:.2f} / ${fail_threshold:.2f})")
    elif state == "WARN":
        st.warning(f"⚠️ **WARN** - Approaching budget limit (${current_cost:.2f} / ${fail_threshold:.2f})")
        st.info(f"💡 Action recommended: Review resources to avoid hitting ${fail_threshold:.2f} limit")
    else:  # FAIL
        st.error(f"🚨 **FAIL** - Budget exceeded! (${current_cost:.2f} / ${fail_threshold:.2f})")
        st.error("⚠️ Auto-Suspend and Auto-Cleanup should be triggered. Check event log below.")


def render_metrics_dashboard(billing_data: dict[str, Any]):
    """
    What: Display billing metrics in card layout
    Why: At-a-glance view of key metrics
    Design Decision: 3-column layout with st.metric

    Args:
        billing_data: Dict containing current_cost_usd, active_alarms, last_actions
    """
    st.markdown("### 📈 Metrics")

    col1, col2, col3 = st.columns(3)

    with col1:
        current_cost = billing_data["current_cost_usd"]
        threshold = billing_data["threshold_fail_usd"]
        percentage = (current_cost / threshold) * 100
        st.metric(
            label="Current Cost (24h avg)",
            value=f"${current_cost:.2f}",
            delta=f"{percentage:.1f}% of limit",
            delta_color="inverse",
        )

    with col2:
        active_alarms = len(billing_data.get("active_alarms", []))
        st.metric(
            label="Active Alarms",
            value=active_alarms,
            delta="0 new" if active_alarms == 0 else f"{active_alarms} active",
            delta_color="off" if active_alarms == 0 else "normal",
        )

    with col3:
        last_actions = billing_data.get("last_actions", [])
        last_action_count = len(last_actions)
        st.metric(
            label="Last Actions (7d)",
            value=last_action_count,
            delta=f"{last_action_count} events",
            delta_color="off",
        )


def render_event_log(events: list[dict[str, Any]]):
    """
    What: Display auto-suspend/cleanup event history
    Why: Audit trail for automated actions
    Design Decision: Simple table with timestamp, action, resource

    Args:
        events: List of event dicts with keys: timestamp, action, resource, reason
    """
    st.markdown("### 📜 Event Log (Recent Actions)")

    if not events:
        st.info("No recent auto-suspend or auto-cleanup events.")
        return

    # Format for display
    import pandas as pd

    df = pd.DataFrame(events)

    # Parse timestamps for better display
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")

    st.dataframe(df, use_container_width=True, hide_index=True)


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_cloudwatch_billing_data() -> dict[str, Any]:
    """
    What: Fetch real billing data from CloudWatch
    Why: Step 5 - Real-time cost monitoring
    Design Decision: Use EstimatedCharges metric (us-east-1 only)

    Returns:
        Dict with current_cost_usd, threshold_warn_usd, threshold_fail_usd, active_alarms
    """
    if not BOTO3_AVAILABLE:
        st.warning("⚠️ boto3 not available. Using mock data.")
        return MOCK_BILLING_DATA.copy()

    try:
        cloudwatch = boto3.client("cloudwatch", region_name="us-east-1")

        # Get EstimatedCharges (last 6 hours)
        from datetime import datetime, timedelta
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=6)

        response = cloudwatch.get_metric_statistics(
            Namespace="AWS/Billing",
            MetricName="EstimatedCharges",
            Dimensions=[{"Name": "Currency", "Value": "USD"}],
            StartTime=start_time,
            EndTime=end_time,
            Period=21600,  # 6 hours
            Statistics=["Maximum"],
        )

        datapoints = response.get("MetricDatapoints", [])
        if datapoints:
            current_cost = max(dp.get("Maximum", 0.0) for dp in datapoints)
        else:
            current_cost = 0.0

        # Get alarm states
        env = os.environ.get("ENV", "dev")
        warn_alarm_name = f"MotionScan-{env}-Billing-Warn"
        fail_alarm_name = f"MotionScan-{env}-Billing-Fail"

        alarms_response = cloudwatch.describe_alarms(
            AlarmNames=[warn_alarm_name, fail_alarm_name]
        )

        active_alarms = []
        for alarm in alarms_response.get("MetricAlarms", []):
            if alarm.get("StateValue") == "ALARM":
                active_alarms.append({
                    "name": alarm["AlarmName"],
                    "state": alarm["StateValue"],
                    "reason": alarm.get("StateReason", ""),
                })

        return {
            "current_cost_usd": current_cost,
            "threshold_warn_usd": DEFAULT_WARN_THRESHOLD,
            "threshold_fail_usd": DEFAULT_FAIL_THRESHOLD,
            "active_alarms": active_alarms,
        }

    except (ClientError, BotoCoreError) as e:
        st.warning(f"⚠️ CloudWatch access failed: {e}. Using mock data.")
        return MOCK_BILLING_DATA.copy()


def load_billing_events() -> list[dict[str, Any]]:
    """
    What: Load billing events from JSONL log
    Why: Display auto-suspend/cleanup history
    Design Decision: Read last 100 lines (most recent)

    Returns:
        List of event dicts
    """
    if not BILLING_EVENTS_LOG.exists():
        return MOCK_BILLING_DATA["last_actions"]

    try:
        events = []
        with open(BILLING_EVENTS_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))

        # Return last 100 events (most recent)
        return events[-100:]

    except (IOError, json.JSONDecodeError) as e:
        st.warning(f"⚠️ Failed to load billing events: {e}")
        return MOCK_BILLING_DATA["last_actions"]


def get_monitoring_status() -> dict[str, Any]:
    """
    What: Get monitoring status from CloudWatch Alarms
    Why: Display alert badges for billing and UI performance
    Design Decision: Query all relevant alarm states, graceful fallback

    Returns:
        Dict with alarm states:
        {
            "billing": "OK|WARN|FAIL",
            "ui_performance": "OK|WARN|FAIL",
            "latest_alert": {...},
            "alarm_details": [...]
        }
    """
    if not BOTO3_AVAILABLE:
        return {
            "billing": "OK",
            "ui_performance": "OK",
            "latest_alert": None,
            "alarm_details": [],
        }

    try:
        cloudwatch = boto3.client("cloudwatch", region_name="us-east-1")
        env = os.environ.get("ENV", "dev")

        # Query all alarm states
        alarm_names = [
            f"MotionScan-{env}-Billing-Warn",
            f"MotionScan-{env}-Billing-Fail",
            f"MotionScan-{env}-UI-RenderTime-Warn",
            f"MotionScan-{env}-UI-RenderTime-Fail",
            f"MotionScan-{env}-UI-ErrorRate-Warn",
            f"MotionScan-{env}-UI-ErrorRate-Fail",
            f"MotionScan-{env}-UI-Availability-Warn",
            f"MotionScan-{env}-UI-Availability-Fail",
        ]

        response = cloudwatch.describe_alarms(AlarmNames=alarm_names)

        # Analyze alarm states
        billing_state = "OK"
        ui_state = "OK"
        alarm_details = []
        latest_alert = None

        for alarm in response.get("MetricAlarms", []):
            alarm_name = alarm["AlarmName"]
            state_value = alarm.get("StateValue", "INSUFFICIENT_DATA")
            state_reason = alarm.get("StateReason", "")
            state_updated = alarm.get("StateUpdatedTimestamp")

            # Build alarm detail
            detail = {
                "name": alarm_name,
                "state": state_value,
                "reason": state_reason,
                "updated": state_updated.isoformat() if state_updated else None,
            }
            alarm_details.append(detail)

            # Determine component state
            if "Billing" in alarm_name and state_value == "ALARM":
                if "Fail" in alarm_name:
                    billing_state = "FAIL"
                elif billing_state != "FAIL":
                    billing_state = "WARN"

                if latest_alert is None or (state_updated and state_updated > latest_alert.get("updated", datetime.min)):
                    latest_alert = detail

            elif ("UI" in alarm_name or "RenderTime" in alarm_name or "ErrorRate" in alarm_name or "Availability" in alarm_name) and state_value == "ALARM":
                if "Fail" in alarm_name:
                    ui_state = "FAIL"
                elif ui_state != "FAIL":
                    ui_state = "WARN"

                if latest_alert is None or (state_updated and state_updated > latest_alert.get("updated", datetime.min)):
                    latest_alert = detail

        return {
            "billing": billing_state,
            "ui_performance": ui_state,
            "latest_alert": latest_alert,
            "alarm_details": alarm_details,
        }

    except (ClientError, BotoCoreError) as e:
        st.warning(f"⚠️ Failed to fetch monitoring status: {e}")
        return {
            "billing": "OK",
            "ui_performance": "OK",
            "latest_alert": None,
            "alarm_details": [],
        }


def render_billing_status_page():
    """
    What: Main entry point for Billing Status page
    Why: Step 5 complete - real CloudWatch data + event log
    Design Decision: Graceful fallback to mock data if CloudWatch unavailable

    CRITICAL: Step 5 = Real data integration
    """
    st.title("💳 Billing Status Dashboard")

    # Get monitoring status (CloudWatch Alarms)
    monitoring_status = get_monitoring_status()

    # Alert Badge Display
    billing_status = monitoring_status["billing"]
    ui_status = monitoring_status["ui_performance"]
    latest_alert = monitoring_status["latest_alert"]

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        if billing_status == "OK":
            st.success("🟢 **Billing**: All systems operational")
        elif billing_status == "WARN":
            st.warning("🟡 **Billing**: Warning - Cost approaching limit")
        else:  # FAIL
            st.error("🔴 **Billing**: Alert - Cost exceeded limit!")

    with col2:
        if ui_status == "OK":
            st.success("🟢 **UI Performance**: Normal")
        elif ui_status == "WARN":
            st.warning("🟡 **UI Performance**: Warning - Degradation detected")
        else:  # FAIL
            st.error("🔴 **UI Performance**: Alert - Critical degradation!")

    with col3:
        # Mini-Review Button
        if billing_status != "OK" or ui_status != "OK":
            if st.button("📋 View Runbook", help="Click to view incident response runbook"):
                st.session_state["show_runbook"] = True
        else:
            st.info("✅ No alerts")

    # Display Runbook in expander
    if st.session_state.get("show_runbook", False):
        with st.expander("📘 Incident Response Runbook", expanded=True):
            st.markdown("""
            ## 🚨 Incident Response Runbook

            ### 1️⃣ First Response (Within 5 minutes)

            **Immediate Actions:**
            1. Acknowledge alert (click button below)
            2. Check CloudWatch Alarms for details
            3. Review `logs/monitoring_events.jsonl` for recent events
            4. Notify tech lead if severity is FAIL

            **Quick Diagnostics:**
            - Billing WARN/FAIL: Check Cost Explorer, review recent resource changes
            - UI Performance WARN/FAIL: Check Streamlit logs, measure page load time manually
            - UI Availability FAIL: Verify dashboard accessibility, check error logs

            ---

            ### 2️⃣ Root Cause Analysis Template

            **Record your findings:**
            ```
            Timestamp: [YYYY-MM-DD HH:MM UTC]
            Alert: [Billing/UI Performance/UI Availability]
            Severity: [WARN/FAIL]
            Observed Behavior:
            - [What you observed]
            - [Metrics affected]

            Suspected Cause:
            - [Hypothesis 1]
            - [Hypothesis 2]

            Evidence:
            - [Log entries, screenshots, metric graphs]
            ```

            ---

            ### 3️⃣ Rollback Decision Criteria

            **Automatic Rollback Triggers:**
            - ❌ False positive rate +30%
            - ❌ Critical event miss (1+ occurrences)
            - ❌ Cost overrun >$5.00
            - ❌ UI degradation: P90 >1200ms for 3 consecutive evaluations

            **Rollback Procedure:**
            ```bash
            # 1. Stop current deployment
            aws lambda update-function-configuration \\
              --function-name thf-rep-rescore-worker-dev \\
              --environment Variables={DRY_RUN=true}

            # 2. Restore previous version
            aws lambda update-function-code \\
              --function-name thf-rep-rescore-worker-dev \\
              --s3-bucket thf-lambda-artifacts \\
              --s3-key previous-version.zip

            # 3. Verify rollback
            aws lambda get-function --function-name thf-rep-rescore-worker-dev

            # 4. Record event
            echo '{"timestamp":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","event":"rollback","reason":"cost_overrun"}' >> logs/monitoring_events.jsonl
            ```

            ---

            ### 4️⃣ Verification Checklist

            **Post-Rollback Verification:**
            - [ ] CloudWatch Alarms return to OK state (wait 10-15 minutes)
            - [ ] Billing cost stabilizes below $4.00
            - [ ] UI render time P75 < 800ms
            - [ ] No new error spikes in logs
            - [ ] Dashboard accessibility confirmed

            ---

            ### 5️⃣ Mini-Review Meeting

            **Schedule within 24 hours:**
            - **Participants**: Tech Lead, Feature Owner, On-Call Engineer
            - **Duration**: 30 minutes
            - **Required Outputs**:
              1. Root cause analysis document
              2. Action items (with owners and deadlines)
              3. Threshold adjustment proposal (if applicable)

            **Meeting Template:**
            ```
            ## Mini-Review: [Date]

            ### Incident Summary
            - Alert: [Name]
            - Duration: [Start - End]
            - Impact: [Cost/Performance metrics]

            ### Root Cause
            - [Confirmed cause]

            ### Action Items
            - [ ] [Action 1] - Owner: [Name] - Due: [Date]
            - [ ] [Action 2] - Owner: [Name] - Due: [Date]

            ### Threshold Adjustments
            - Current: [Value]
            - Proposed: [Value]
            - Rationale: [Why]
            ```

            ---

            ### 6️⃣ Escalation Path

            **Level 1** (0-5 min): On-Call Engineer
            **Level 2** (5-10 min): Tech Lead
            **Level 3** (10-15 min): Engineering Manager

            **Contact:**
            - Slack: #thf-alerts
            - Email: See `config/monitoring_rules.yaml`

            ---

            ### 7️⃣ Close Runbook

            """)

            if st.button("✅ Acknowledge & Close"):
                st.session_state["show_runbook"] = False
                st.success("✅ Runbook closed. Remember to document findings!")
                st.rerun()

    st.markdown("""
    **Purpose**: Monitor AWS billing, auto-suspend, and auto-cleanup events.

    **Status**:
    - ✅ **Step 1**: UI skeleton
    - ✅ **Step 2**: CloudWatch Alarms + SNS
    - ✅ **Step 3**: Auto-Suspend Lambda (existing)
    - ✅ **Step 4**: Auto-Cleanup Lambda (existing)
    - ✅ **Step 5**: Real CloudWatch integration (current)
    - ✅ **Step 6**: Alert badges + Mini-review runbook (UI Monitoring v1)

    ---
    """)

    # Get real CloudWatch data (with fallback to mock)
    use_real_data = st.sidebar.checkbox("Use Real CloudWatch Data", value=BOTO3_AVAILABLE, disabled=not BOTO3_AVAILABLE)

    if use_real_data and BOTO3_AVAILABLE:
        billing_data = get_cloudwatch_billing_data()
        billing_data["last_actions"] = load_billing_events()
        st.sidebar.success("✅ Using live CloudWatch data")
    else:
        billing_data = MOCK_BILLING_DATA.copy()
        st.sidebar.info("ℹ️ Using mock data")

        # Allow manual state override for testing
        st.sidebar.markdown("### 🔧 Testing Controls")
        override_cost = st.sidebar.number_input(
            "Override Current Cost ($)",
            value=billing_data["current_cost_usd"],
            min_value=0.0,
            max_value=10.0,
            step=0.5,
            help="Test different billing states"
        )
        billing_data["current_cost_usd"] = override_cost

    # Determine state
    state = get_billing_state(
        current_cost=billing_data["current_cost_usd"],
        warn_threshold=billing_data["threshold_warn_usd"],
        fail_threshold=billing_data["threshold_fail_usd"],
    )

    # Render components
    render_billing_status_card(
        state=state,
        current_cost=billing_data["current_cost_usd"],
        warn_threshold=billing_data["threshold_warn_usd"],
        fail_threshold=billing_data["threshold_fail_usd"],
    )

    st.markdown("---")

    render_metrics_dashboard(billing_data)

    st.markdown("---")

    render_event_log(billing_data["last_actions"])

    # Footer
    st.markdown("---")
    st.caption("""
    **Next Steps**:
    - Step 2: CloudWatch Alarms + SNS notifications
    - Step 3: Auto-Suspend Lambda (low-traffic detection)
    - Step 4: Auto-Cleanup Lambda (unattached EBS)
    - Step 5: Real-time CloudWatch integration
    """)


def main():
    """
    What: Standalone entry point for Billing Status page
    Why: Allows running billing.py directly with `streamlit run`
    """
    st.set_page_config(
        page_title="Billing Status",
        page_icon="💳",
        layout="wide",
    )
    render_billing_status_page()


if __name__ == "__main__":
    main()
