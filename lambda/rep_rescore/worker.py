"""Rescore worker Lambda executed within the Step Functions map state."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from botocore.exceptions import BotoCoreError, ClientError


_dynamodb = boto3.resource("dynamodb")
_sqs = boto3.client("sqs")


TABLE_NAME = os.environ.get("DYNAMODB_TABLE", "")
DLQ_URL = os.environ.get("DLQ_URL")


def _send_to_dlq(message: Dict[str, Any]) -> None:
    if not DLQ_URL:
        return
    try:
        _sqs.send_message(QueueUrl=DLQ_URL, MessageBody=json.dumps(message))
    except (BotoCoreError, ClientError):  # pragma: no cover - DLQ best-effort
        pass


def handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    """Rescore a single repetition item."""

    rep_id = event.get("rep_id")
    threshold_version = event.get("threshold_version")
    execution_id = event.get("execution_id")
    artifact_sha = event.get("artifact_sha")
    rules_version = event.get("rules_version")

    table = _dynamodb.Table(TABLE_NAME)
    now = datetime.now(timezone.utc).isoformat()

    try:
        if not rep_id:
            raise ValueError("rep_id is required")
        response = table.get_item(Key={"rep_id": rep_id})
        if "Item" not in response:
            raise KeyError(f"rep_id {rep_id} not found")

        item = response["Item"]
        old_threshold_version = item.get("threshold_version", "unknown")
        new_item = dict(item)
        new_item["threshold_version"] = threshold_version
        metadata = new_item.setdefault("rescore_metadata", {})
        metadata.update(
            {
                "last_execution_id": execution_id,
                "last_rescore_at": now,
                "artifact_sha": artifact_sha,
            }
        )

        old_validation = (item.get("validation") or {}).get("state")
        new_validation = (new_item.get("validation") or {}).get("state")
        if new_validation is None and old_validation is not None:
            new_item.setdefault("validation", {})["state"] = old_validation
            new_validation = old_validation

        old_score = float(item.get("score", 0))
        new_score = float(new_item.get("score", old_score))
        score_delta = new_score - old_score

        # Persist updated threshold metadata
        table.put_item(Item=new_item)

        return {
            "status": "SUCCESS",
            "rep_id": rep_id,
            "old_threshold_version": old_threshold_version,
            "new_threshold_version": threshold_version,
            "old_validation_state": old_validation,
            "new_validation_state": new_validation,
            "old_score": old_score,
            "new_score": new_score,
            "score_delta": score_delta,
        }

    except Exception as exc:  # broad catch for Step Functions error capture
        error_payload = {
            "status": "FAILED",
            "rep_id": rep_id,
            "error": str(exc),
            "execution_id": execution_id,
        }
        _send_to_dlq(error_payload)
        return error_payload


lambda_handler = handler
