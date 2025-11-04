"""
Shared helpers for billing guardrail Lambdas.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence

import boto3
from botocore.exceptions import BotoCoreError, ClientError

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)


def utc_now() -> datetime:
    """Return current UTC time with timezone awareness."""
    return datetime.now(timezone.utc)


def _normalise_tag_value(value: Optional[str]) -> str:
    return (value or "").strip().lower()


def load_metric_sources(raw_definition: Optional[str]) -> List[Dict[str, Any]]:
    """Parse metric sources definition from JSON string.

    Each entry is expected to contain:
      - namespace / Namespace
      - metric / MetricName
      - optional dimensions list (Name/Value pairs)
      - optional stat (defaults to Sum)
      - optional period in seconds (defaults to 3600)
    """
    if not raw_definition:
        return []

    try:
        payload = json.loads(raw_definition)
    except json.JSONDecodeError:
        LOGGER.error("Failed to parse METRIC_SOURCES; falling back to empty list")
        return []

    if not isinstance(payload, list):
        LOGGER.error("METRIC_SOURCES must be a JSON array; received %s", type(payload).__name__)
        return []

    sources: List[Dict[str, Any]] = []
    for idx, entry in enumerate(payload):
        if not isinstance(entry, dict):
            LOGGER.warning("Metric source #%s ignored because it is not an object", idx)
            continue

        namespace = entry.get("namespace") or entry.get("Namespace")
        metric = entry.get("metric") or entry.get("MetricName")
        if not namespace or not metric:
            LOGGER.warning("Metric source #%s missing namespace/metric; skipping", idx)
            continue

        raw_dimensions: Sequence[Any] = entry.get("dimensions") or entry.get("Dimensions") or []
        dimensions: List[Dict[str, str]] = []
        for dim in raw_dimensions:
            if not isinstance(dim, dict):
                LOGGER.warning("Metric source #%s has invalid dimension %s", idx, dim)
                continue
            name = dim.get("Name") or dim.get("name")
            value = dim.get("Value") or dim.get("value")
            if not name or value is None:
                LOGGER.warning("Metric source #%s has incomplete dimension %s", idx, dim)
                continue
            dimensions.append({"Name": str(name), "Value": str(value)})

        stat = (entry.get("stat") or entry.get("Stat") or "Sum").title()
        period = int(entry.get("period") or entry.get("Period") or 3600)

        sources.append(
            {
                "Namespace": str(namespace),
                "MetricName": str(metric),
                "Dimensions": dimensions,
                "Stat": stat,
                "Period": period,
            }
        )

    return sources


def emit_billing_event(
    *,
    kind: str,
    source: str,
    payload: Dict[str, Any],
    context: Any,
    log_group: Optional[str] = None,
    logs_client: Optional[Any] = None,
) -> None:
    """Emit a structured billing_monitor event to CloudWatch Logs.

    The helper writes both to the Lambda stdout (for standard logs) and to the
    dedicated billing monitor log group (if configured).
    """
    log_group = log_group or os.getenv("BILLING_LOG_GROUP")
    event: Dict[str, Any] = {
        "evt": "billing_monitor",
        "ts": utc_now().isoformat().replace("+00:00", "Z"),
        "kind": kind,
        "source": source,
        **payload,
    }

    LOGGER.info("billing_monitor: %s", json.dumps(event, ensure_ascii=False))

    if not log_group:
        return

    logs_client = logs_client or boto3.client("logs")
    stream_token: Optional[str] = None
    stream_name = f"{kind}-{utc_now().strftime('%Y%m%dT%H%M%S')}-{(getattr(context, 'aws_request_id', '') or uuid.uuid4().hex)[:12]}"

    try:
        logs_client.create_log_stream(logGroupName=log_group, logStreamName=stream_name)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ResourceAlreadyExistsException":
            LOGGER.warning("Failed to create billing log stream: %s", exc)
            return

    try:
        logs_client.put_log_events(
            logGroupName=log_group,
            logStreamName=stream_name,
            logEvents=[
                {
                    "timestamp": int(utc_now().timestamp() * 1000),
                    "message": json.dumps(event, ensure_ascii=False),
                }
            ],
            sequenceToken=stream_token,
        )
    except (ClientError, BotoCoreError) as exc:
        LOGGER.warning("Failed to publish billing monitor event: %s", exc)


def stop_tagged_instances(
    ec2_client: Any,
    *,
    tag_key: str,
    tag_value: str,
) -> List[str]:
    """Stop running EC2 instances that carry the specified AutoSuspend tag."""
    filters = [
        {"Name": "instance-state-name", "Values": ["running"]},
        {"Name": f"tag:{tag_key}", "Values": [tag_value]},
    ]

    instance_ids: List[str] = []
    paginator = ec2_client.get_paginator("describe_instances")
    for page in paginator.paginate(Filters=filters):
        for reservation in page.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                instance_ids.append(instance["InstanceId"])

    if not instance_ids:
        return []

    try:
        ec2_client.stop_instances(InstanceIds=instance_ids)
    except (ClientError, BotoCoreError) as exc:
        LOGGER.error("Failed to stop instances %s: %s", instance_ids, exc)
        return []

    return instance_ids


def throttle_tagged_lambdas(
    lambda_client: Any,
    events_client: Any,
    *,
    tag_key: str,
    tag_value: str,
) -> List[Dict[str, Any]]:
    """Set reserved concurrency to 0 and disable EventBridge rules for tagged functions."""
    affected: List[Dict[str, Any]] = []
    paginator = lambda_client.get_paginator("list_functions")

    for page in paginator.paginate():
        for function in page.get("Functions", []):
            arn = function.get("FunctionArn")
            name = function.get("FunctionName")
            if not arn or not name:
                continue

            try:
                tags = lambda_client.list_tags(Resource=arn).get("Tags", {})
            except (ClientError, BotoCoreError) as exc:
                LOGGER.warning("Failed to list tags for %s: %s", arn, exc)
                continue

            if _normalise_tag_value(tags.get(tag_key)) != _normalise_tag_value(tag_value):
                continue

            try:
                config = lambda_client.get_function_configuration(FunctionName=name)
                previous = config.get("ReservedConcurrentExecutions")
            except (ClientError, BotoCoreError) as exc:
                LOGGER.warning("Failed to fetch configuration for %s: %s", name, exc)
                previous = None

            try:
                lambda_client.put_function_concurrency(
                    FunctionName=name,
                    ReservedConcurrentExecutions=0,
                )
            except (ClientError, BotoCoreError) as exc:
                LOGGER.error("Failed to throttle Lambda %s: %s", name, exc)
                continue

            disabled_rules: List[str] = []
            try:
                rule_response = events_client.list_rule_names_by_target(TargetArn=arn)
                for rule in rule_response.get("RuleNames", []):
                    try:
                        events_client.disable_rule(Name=rule)
                        disabled_rules.append(rule)
                    except (ClientError, BotoCoreError) as exc:
                        LOGGER.warning("Failed to disable EventBridge rule %s for %s: %s", rule, name, exc)
            except (ClientError, BotoCoreError) as exc:
                LOGGER.warning("Failed to enumerate EventBridge rules for %s: %s", name, exc)

            affected.append(
                {
                    "function_name": name,
                    "function_arn": arn,
                    "previous_reserved_concurrency": previous,
                    "disabled_rules": disabled_rules,
                }
            )

    return affected


def ensure_list(value: Optional[Iterable[Any]]) -> List[Any]:
    if not value:
        return []
    return list(value)
