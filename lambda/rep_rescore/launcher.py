"""Launcher Lambda for rep rescore Step Functions pipeline."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3


_stepfunctions = boto3.client("stepfunctions")
_dynamodb = boto3.resource("dynamodb")


def _load_request(event: Dict[str, Any]) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if isinstance(event.get("body"), str):
        try:
            body = json.loads(event["body"])
        except json.JSONDecodeError as exc:  # pragma: no cover - API gateway guard
            raise ValueError("Body must be valid JSON") from exc
    elif isinstance(event.get("body"), dict):
        body = event["body"]
    return body


def _fetch_rep_ids(table_name: str, limit: Optional[int] = None) -> List[str]:
    table = _dynamodb.Table(table_name)
    scan_kwargs: Dict[str, Any] = {"ProjectionExpression": "rep_id"}
    if limit:
        scan_kwargs["Limit"] = int(limit)

    items: List[str] = []
    response = table.scan(**scan_kwargs)
    for item in response.get("Items", []):
        rep_id = item.get("rep_id")
        if isinstance(rep_id, str):
            items.append(rep_id)

    while "LastEvaluatedKey" in response and (not limit or len(items) < limit):
        last_evaluated = response["LastEvaluatedKey"]
        response = table.scan(ExclusiveStartKey=last_evaluated, **scan_kwargs)
        for item in response.get("Items", []):
            rep_id = item.get("rep_id")
            if isinstance(rep_id, str):
                items.append(rep_id)
                if limit and len(items) >= limit:
                    break

    if limit:
        return items[:limit]
    return items


def _start_execution(
    state_machine_arn: str,
    execution_input: Dict[str, Any],
    execution_id: str,
) -> Dict[str, Any]:
    name = f"{execution_id}-{int(datetime.utcnow().timestamp())}"
    response = _stepfunctions.start_execution(
        stateMachineArn=state_machine_arn,
        name=name,
        input=json.dumps(execution_input),
    )
    return response


def handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    """API Gateway entrypoint."""

    table_name = os.environ["DYNAMODB_TABLE"]
    state_machine_arn = os.environ["STATE_MACHINE_ARN"]
    default_threshold_version = os.environ.get("VERSION_TOGGLE", "v2.1")

    try:
        body = _load_request(event)
        rep_ids = body.get("rep_ids")
        if rep_ids is None:
            limit = body.get("limit")
            rep_ids = _fetch_rep_ids(table_name, limit=limit)
        if not isinstance(rep_ids, list) or not rep_ids:
            raise ValueError("rep_ids must be a non-empty list or discoverable from DynamoDB")

        threshold_version = body.get("threshold_version") or default_threshold_version
        artifact_sha = body.get("artifact_sha", "unknown")
        rules_version = body.get("rules_version", threshold_version)
        execution_id = body.get("execution_id") or str(uuid.uuid4())
        requested_at = datetime.now(timezone.utc).isoformat()

        payload = {
            "execution_id": execution_id,
            "requested_at": requested_at,
            "threshold_version": threshold_version,
            "artifact_sha": artifact_sha,
            "rules_version": rules_version,
            "rep_ids": rep_ids,
        }

        sf_response = _start_execution(state_machine_arn, payload, execution_id)

    except ValueError as err:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"message": str(err)}),
        }

    response_body = {
        "execution_id": execution_id,
        "start_time": sf_response.get("startDate", requested_at),
        "state_machine_execution_arn": sf_response.get("executionArn"),
        "rep_count": len(rep_ids),
        "threshold_version": threshold_version,
    }

    return {
        "statusCode": 202,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(response_body),
    }


# Alias for AWS Lambda entrypoint
lambda_handler = handler
