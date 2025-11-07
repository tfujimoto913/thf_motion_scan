"""Billing guard Lambda.

Triggered by the Billing FAIL alarm to aggressively suspend tagged workloads.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .common import emit_billing_event, stop_tagged_instances, throttle_tagged_lambdas

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

ec2 = boto3.client("ec2")
lambda_client = boto3.client("lambda")
events = boto3.client("events")

ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
TAG_KEY = os.getenv("AUTOSUSPEND_TAG_KEY", "AutoSuspend")
TAG_VALUE = os.getenv("AUTOSUSPEND_TAG_VALUE", "true")
FAIL_ALARM_NAME = os.getenv("BILLING_FAIL_ALARM_NAME") or f"MotionScan-{ENVIRONMENT}-Billing-Fail"


def _parse_sns_event(event: Dict[str, Any]) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    for record in event.get("Records", []):
        sns = record.get("Sns", {}) if isinstance(record, dict) else {}
        message_str = sns.get("Message", "")
        try:
            payload = json.loads(message_str)
        except json.JSONDecodeError:
            LOGGER.warning("Ignoring non-JSON SNS message: %s", message_str)
            continue

        if isinstance(payload, dict):
            messages.append(payload)
        else:
            LOGGER.warning("SNS message payload is not a dict: %s", payload)
    return messages


def _should_engage_guard(message: Dict[str, Any]) -> bool:
    alarm_name = message.get("AlarmName")
    new_state = message.get("NewStateValue")

    if new_state != "ALARM":
        return False

    if FAIL_ALARM_NAME and alarm_name != FAIL_ALARM_NAME:
        LOGGER.info("Skipping alarm %s (expecting %s)", alarm_name, FAIL_ALARM_NAME)
        return False

    return True


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    force = isinstance(event, dict) and bool(event.get("force"))
    dry_run = isinstance(event, dict) and bool(event.get("dry_run"))

    if force:
        relevant = [{"AlarmName": FAIL_ALARM_NAME, "NewStateValue": "ALARM"}]
    else:
        messages = _parse_sns_event(event)
        relevant = [msg for msg in messages if _should_engage_guard(msg)]

    if not relevant:
        LOGGER.info("No relevant billing fail alarms detected")
        return {"ok": True, "reason": "no_action"}

    if dry_run:
        instances: List[str] = []
        throttled: List[Dict[str, Any]] = []
    else:
        instances = stop_tagged_instances(ec2, tag_key=TAG_KEY, tag_value=TAG_VALUE)
        throttled = throttle_tagged_lambdas(lambda_client, events, tag_key=TAG_KEY, tag_value=TAG_VALUE)

    payload = {
        "environment": ENVIRONMENT,
        "alarms": [msg.get("AlarmName") for msg in relevant],
        "instances_stopped": instances,
        "lambda_throttled": throttled,
        "dry_run": dry_run,
        "forced": force,
    }

    emit_billing_event(
        kind="billing_guard",
        source="billing_guard",
        payload=payload,
        context=context,
    )

    return {
        "ok": True,
        "reason": "billing_guard_engaged",
        **payload,
    }
