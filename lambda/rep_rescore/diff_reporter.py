"""Lambda to generate rescore difference reports."""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3


_s3 = boto3.client("s3")

BUCKET = os.environ.get("REPORT_BUCKET")
PREFIX = os.environ.get("REPORT_PREFIX", "diffs/")


def _put_object(key: str, body: bytes, content_type: str) -> None:
    if not BUCKET:
        raise ValueError("REPORT_BUCKET not configured")
    _s3.put_object(Bucket=BUCKET, Key=key, Body=body, ContentType=content_type)


def _build_csv(rows: List[Dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    fieldnames = [
        "rep_id",
        "status",
        "old_threshold_version",
        "new_threshold_version",
        "old_validation_state",
        "new_validation_state",
        "old_score",
        "new_score",
        "score_delta",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field) for field in fieldnames})
    return buffer.getvalue().encode("utf-8")


def handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    execution_id = event.get("execution_id")
    threshold_version = event.get("threshold_version")
    artifact_sha = event.get("artifact_sha")
    rules_version = event.get("rules_version")
    results = event.get("results", [])

    success = [item for item in results if item.get("status") == "SUCCESS"]
    failed = [item for item in results if item.get("status") == "FAILED"]

    reclassified = [
        item
        for item in success
        if item.get("old_validation_state") != item.get("new_validation_state")
        or abs(float(item.get("score_delta", 0))) > 1e-6
    ]

    summary = {
        "execution_id": execution_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold_version": threshold_version,
        "artifact_sha": artifact_sha,
        "rules_version": rules_version,
        "total_processed": len(results),
        "success_count": len(success),
        "failure_count": len(failed),
        "reclassified_count": len(reclassified),
        "avg_score_delta": (
            sum(float(item.get("score_delta", 0)) for item in success) / len(success)
            if success
            else 0.0
        ),
    }

    prefix = PREFIX.rstrip("/") + f"/{execution_id}/"
    summary_key = prefix + "summary.json"
    details_key = prefix + "details.csv"
    failures_key = prefix + "failures.jsonl"

    _put_object(summary_key, json.dumps(summary, ensure_ascii=False).encode("utf-8"), "application/json")
    _put_object(details_key, _build_csv(success), "text/csv")

    if failed:
        lines = "\n".join(json.dumps(item, ensure_ascii=False) for item in failed)
        _put_object(failures_key, lines.encode("utf-8"), "application/jsonlines")

    return summary


lambda_handler = handler
