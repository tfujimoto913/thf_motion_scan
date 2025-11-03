"""DLQ redrive Lambda for rep rescore failures."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3


_sqs = boto3.client("sqs")
_stepfunctions = boto3.client("stepfunctions")

DLQ_URL = os.environ.get("DLQ_URL")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")


def _receive_messages(max_messages: int) -> List[Dict[str, Any]]:
    response = _sqs.receive_message(
        QueueUrl=DLQ_URL,
        MaxNumberOfMessages=max_messages,
        WaitTimeSeconds=0,
    )
    return response.get("Messages", [])


def handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    if not DLQ_URL or not STATE_MACHINE_ARN:
        raise RuntimeError("DLQ_URL and STATE_MACHINE_ARN must be set")

    max_messages = int(event.get("max_messages", 10))
    messages = _receive_messages(max_messages)
    restarted = 0

    for message in messages:
        body = json.loads(message.get("Body", "{}"))
        rep_id = body.get("rep_id")
        threshold_version = body.get("new_threshold_version") or body.get("threshold_version")
        artifact_sha = body.get("artifact_sha", "unknown")
        rules_version = body.get("rules_version", threshold_version)
        if not rep_id:
            continue

        execution_id = body.get("execution_id") or str(uuid.uuid4())
        payload = {
            "execution_id": execution_id,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "threshold_version": threshold_version,
            "artifact_sha": artifact_sha,
            "rules_version": rules_version,
            "rep_ids": [rep_id],
        }

        _stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=f"redrive-{execution_id}-{int(datetime.utcnow().timestamp())}",
            input=json.dumps(payload),
        )

        _sqs.delete_message(QueueUrl=DLQ_URL, ReceiptHandle=message["ReceiptHandle"])
        restarted += 1

    return {"restarted": restarted}


lambda_handler = handler
