#!/usr/bin/env python3
"""
Operational redrive script for Motion Scan DLQ.

Moves messages from a dead-letter queue back to the primary queue in controlled
batches while emitting guardrail metrics and honouring stop conditions.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError


LOGGER = logging.getLogger("redrive")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Re-drive messages from DLQ to source queue.")
    parser.add_argument("--source-queue", required=True, help="Target queue URL to redrive into.")
    parser.add_argument("--dlq", required=True, help="Dead-letter queue URL to drain from.")
    parser.add_argument("--batch-size", type=int, default=25, help="Messages per batch (max 25).")
    parser.add_argument("--interval", type=int, default=60, help="Seconds to wait between batches.")
    parser.add_argument("--max-batches", type=int, default=10, help="Maximum number of batches to process.")
    parser.add_argument("--order", choices=("asc", "desc"), default="asc", help="Process oldest (asc) or newest (desc) messages first.")
    parser.add_argument("--rules-version", default=os.getenv("RULES_VERSION"), help="Runbook rules version metadata.")
    parser.add_argument("--artifact-sha", default=os.getenv("ARTIFACT_SHA"), help="Deployed artifact identifier.")
    parser.add_argument("--environment", default=os.getenv("ENVIRONMENT", "dev"), help="Environment label for metrics.")
    parser.add_argument("--table-name", default=os.getenv("RESULTS_TABLE_NAME", "motion-scan-results"), help="DynamoDB table to monitor UserErrors for spike detection.")
    parser.add_argument("--user-error-threshold", type=int, default=10, help="Stop if UserErrors increase by this amount within 5 minutes.")
    parser.add_argument("--namespace", default=os.getenv("METRICS_NAMESPACE", "THF/MotionScan"), help="Custom CloudWatch metrics namespace.")
    return parser.parse_args()


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )


def get_metric_sum(cloudwatch, table_name: str) -> float:
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=5)
    response = cloudwatch.get_metric_statistics(
        Namespace="AWS/DynamoDB",
        MetricName="UserErrors",
        Dimensions=[{"Name": "TableName", "Value": table_name}],
        StartTime=start_time,
        EndTime=end_time,
        Period=300,
        Statistics=["Sum"],
    )
    datapoints = response.get("Datapoints", [])
    if not datapoints:
        return 0.0
    return max(dp.get("Sum", 0.0) for dp in datapoints)


def emit_metric(cloudwatch, namespace: str, metric_name: str, value: float, environment: str, request_id: str) -> None:
    dimensions = [
        {"Name": "Environment", "Value": environment},
        {"Name": "Executor", "Value": "dlq-redrive"},
        {"Name": "RequestId", "Value": request_id},
    ]
    try:
        cloudwatch.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": metric_name,
                    "Timestamp": datetime.utcnow(),
                    "Value": value,
                    "Unit": "Count",
                    "Dimensions": dimensions,
                }
            ],
        )
    except (ClientError, BotoCoreError) as exc:
        LOGGER.warning("Failed to emit metric %s: %s", metric_name, exc)


def extract_failure_reason(message: Dict[str, Any]) -> str:
    """
    Try to infer a failure reason from the DLQ payload or attributes.
    Falls back to returning 'unknown'.
    """
    body = message.get("Body")
    if body:
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                if "errorType" in parsed:
                    return str(parsed["errorType"])
                if "errorMessage" in parsed:
                    return str(parsed["errorMessage"])
        except json.JSONDecodeError:
            pass

    attrs = message.get("MessageAttributes") or {}
    for key in ("failure_reason", "FailureReason", "ErrorCause"):
        if key in attrs and "StringValue" in attrs[key]:
            return attrs[key]["StringValue"]

    return "unknown"


def sort_messages(messages: List[Dict[str, Any]], order: str) -> List[Dict[str, Any]]:
    if order == "asc":
        return sorted(messages, key=lambda m: int(m.get("Attributes", {}).get("SentTimestamp", "0")))
    return sorted(messages, key=lambda m: int(m.get("Attributes", {}).get("SentTimestamp", "0")), reverse=True)


def requeue_message(sqs, source_queue: str, message: Dict[str, Any]) -> None:
    kwargs: Dict[str, Any] = {
        "QueueUrl": source_queue,
        "MessageBody": message["Body"],
    }
    if message.get("MessageAttributes"):
        kwargs["MessageAttributes"] = message["MessageAttributes"]

    attributes = message.get("Attributes") or {}
    if "MessageGroupId" in attributes:
        kwargs["MessageGroupId"] = attributes["MessageGroupId"]
    if "MessageDeduplicationId" in attributes:
        kwargs["MessageDeduplicationId"] = f"{attributes['MessageDeduplicationId']}-{uuid.uuid4().hex}"

    sqs.send_message(**kwargs)


def main() -> None:
    args = parse_args()
    setup_logging()

    if args.batch_size > 25 or args.batch_size <= 0:
        LOGGER.error("batch-size must be between 1 and 25")
        sys.exit(1)

    sqs = boto3.client("sqs")
    cloudwatch = boto3.client("cloudwatch")

    request_id = str(uuid.uuid4())
    baseline_user_errors = get_metric_sum(cloudwatch, args.table_name)

    total_moved = 0
    batches_processed = 0
    repeated_failure_reasons: List[str] = []
    stopped_reason: Optional[str] = None
    failures: List[str] = []
    started_at = time.time()

    try:
        for batch_index in range(args.max_batches):
            response = sqs.receive_message(
                QueueUrl=args.dlq,
                MaxNumberOfMessages=args.batch_size,
                AttributeNames=["All"],
                MessageAttributeNames=["All"],
                VisibilityTimeout=1,
                WaitTimeSeconds=0,
            )
            messages = response.get("Messages", [])
            if not messages:
                stopped_reason = "DLQ_EMPTY"
                break

            ordered = sort_messages(messages, args.order)
            delete_entries = []

            for message in ordered:
                try:
                    requeue_message(sqs, args.source_queue, message)
                    delete_entries.append(
                        {"Id": message["MessageId"], "ReceiptHandle": message["ReceiptHandle"]}
                    )
                    total_moved += 1
                    emit_metric(cloudwatch, args.namespace, "RedriveSuccessCount", 1, args.environment, request_id)
                except (ClientError, BotoCoreError) as exc:
                    reason = extract_failure_reason(message)
                    failures.append(reason)
                    repeated_failure_reasons.append(reason)
                    emit_metric(cloudwatch, args.namespace, "RedriveFailureCount", 1, args.environment, request_id)
                    LOGGER.error("Failed to requeue message %s: %s", message["MessageId"], exc)
                    if len(repeated_failure_reasons) >= 5 and len(set(repeated_failure_reasons[-5:])) == 1:
                        stopped_reason = "REPEATED_FAILURE_REASON"
                        break

            if delete_entries:
                delete_response = sqs.delete_message_batch(QueueUrl=args.dlq, Entries=delete_entries)
                failed = delete_response.get("Failed", [])
                if failed:
                    LOGGER.error("Failed to delete %d messages from DLQ: %s", len(failed), failed)
                batches_processed += 1

            if stopped_reason:
                break

            current_user_errors = get_metric_sum(cloudwatch, args.table_name)
            if current_user_errors - baseline_user_errors >= args.user_error_threshold:
                stopped_reason = "USER_ERRORS_SPIKE"
                break

            if len(messages) < args.batch_size:
                stopped_reason = "DLQ_DRAINED"
                break

            time.sleep(args.interval)
        else:
            stopped_reason = stopped_reason or "MAX_BATCHES_REACHED"

    except KeyboardInterrupt:
        stopped_reason = "INTERRUPTED"
        LOGGER.warning("Redrive interrupted by user.")

    duration = time.time() - started_at

    summary = {
        "moved": total_moved,
        "batches": batches_processed,
        "stopped_reason": stopped_reason,
        "failures": failures[-10:],
        "rules_version": args.rules_version,
        "artifact_sha": args.artifact_sha,
        "request_id": request_id,
        "environment": args.environment,
        "duration_seconds": round(duration, 2),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
