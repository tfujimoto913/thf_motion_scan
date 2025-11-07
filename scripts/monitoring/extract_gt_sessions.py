#!/usr/bin/env python3
"""Extract candidate sessions for weekly ground-truth review."""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - optional dependency for local runs
    import boto3  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    boto3 = None  # type: ignore

try:  # pragma: no cover
    from botocore.exceptions import ClientError  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    class ClientError(Exception):  # type: ignore
        def __init__(self, response, operation_name):
            super().__init__(response)
            self.response = response
            self.operation_name = operation_name


NAMESPACE = "extract_gt_sessions"


def log(action: str, **payload: Any) -> None:
    entry = {"action": action, "timestamp": datetime.now(timezone.utc).isoformat()}
    entry.update(payload)
    print(json.dumps(entry, ensure_ascii=False, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract GT review candidates")
    parser.add_argument("--env", default="dev", help="Environment value (default: dev)")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Lookback window in days (default: 7)",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=10,
        help="Number of sessions to sample (default: 10)",
    )
    parser.add_argument(
        "--results-bucket",
        required=True,
        help="S3 bucket containing processed artifacts",
    )
    parser.add_argument(
        "--table-name",
        default="motion-scan-results",
        help="DynamoDB results table name",
    )
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region for both DynamoDB and S3 (default: boto config)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/monitoring/review_list.csv"),
        help="CSV output path (default: docs/monitoring/review_list.csv)",
    )
    parser.add_argument(
        "--force-s3",
        action="store_true",
        help="Always use S3 fallback even if GSI exists",
    )
    parser.add_argument(
        "--video-expiration",
        type=int,
        default=60 * 60 * 24,
        help="Signed URL expiration in seconds (default: 86400)",
    )
    parser.add_argument(
        "--viz-expiration",
        type=int,
        default=60 * 60 * 24,
        help="Visualization URL expiration in seconds (default: 86400)",
    )
    return parser


def describe_table_has_gsi(table_name: str, region: Optional[str]) -> bool:
    if boto3 is None:
        return False
    client = boto3.client("dynamodb", region_name=region)
    description = client.describe_table(TableName=table_name)
    gsis = description.get("Table", {}).get("GlobalSecondaryIndexes", [])
    for gsi in gsis:
        if gsi.get("IndexName") == "GSI_Recent":
            status = gsi.get("IndexStatus")
            return status == "ACTIVE"
    return False


def query_recent_sessions(
    *,
    table_name: str,
    env: str,
    start: datetime,
    end: datetime,
    region: Optional[str],
    limit: int,
) -> List[Dict[str, Any]]:
    if boto3 is None:
        return []
    resource = boto3.resource("dynamodb", region_name=region)
    table = resource.Table(table_name)
    from boto3.dynamodb.conditions import Key

    start_iso = start.isoformat()
    end_iso = end.isoformat()

    response = table.query(
        IndexName="GSI_Recent",
        KeyConditionExpression=Key("env").eq(env) & Key("processed_at").between(start_iso, end_iso),
        Limit=limit,
        ScanIndexForward=False,
    )
    return response.get("Items", [])


def list_summary_objects(
    *,
    bucket: str,
    region: Optional[str],
    days: int,
    client=None,
    current_time: Optional[datetime] = None,
) -> List[str]:
    s3 = client or (boto3.client("s3", region_name=region) if boto3 else None)
    if s3 is None:
        raise RuntimeError("boto3 is required for S3 fallback")

    summary_keys: List[str] = []
    now = current_time or datetime.now(timezone.utc)
    for offset in range(days):
        day = now - timedelta(days=offset)
        prefix = day.strftime("processed/%Y-%m-%d/")
        continuation = None
        while True:
            params = {"Bucket": bucket, "Prefix": prefix}
            if continuation:
                params["ContinuationToken"] = continuation
            response = s3.list_objects_v2(**params)
            for obj in response.get("Contents", []):
                key = obj["Key"]
                if key.endswith("summary.json"):
                    summary_keys.append(key)
            continuation = response.get("NextContinuationToken")
            if not continuation:
                break
    return summary_keys


def load_summary(
    *,
    bucket: str,
    key: str,
    region: Optional[str],
    client=None,
) -> Dict[str, Any]:
    s3 = client or (boto3.client("s3", region_name=region) if boto3 else None)
    if s3 is None:
        raise RuntimeError("boto3 is required for S3 fallback")
    response = s3.get_object(Bucket=bucket, Key=key)
    data = json.loads(response["Body"].read().decode("utf-8"))
    return data


def sample_entries(entries: List[Any], sample_size: int) -> List[Any]:
    if len(entries) <= sample_size:
        return entries
    return random.sample(entries, sample_size)


def generate_signed_url(
    *,
    bucket: str,
    key: str,
    expiration: int,
    region: Optional[str],
    client=None,
) -> str:
    s3 = client or (boto3.client("s3", region_name=region) if boto3 else None)
    if s3 is None:
        raise RuntimeError("boto3 is required for presigned URLs")
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiration,
    )


def derive_visualization_key(summary_key: str) -> Optional[str]:
    if summary_key.endswith("/summary.json"):
        base = summary_key[:-len("summary.json")]
        return base + "overlay.png"
    return None


def fallback_collect(
    *,
    bucket: str,
    region: Optional[str],
    env: str,
    days: int,
    sample_size: int,
    video_expiration: int,
    viz_expiration: int,
    client=None,
    current_time: Optional[datetime] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    start = time.perf_counter()
    client = client or (boto3.client("s3", region_name=region) if boto3 else None)
    keys = list_summary_objects(
        bucket=bucket,
        region=region,
        days=days,
        client=client,
        current_time=current_time,
    )
    summaries: List[Dict[str, Any]] = []
    for key in keys:
        try:
            data = load_summary(bucket=bucket, key=key, region=region, client=client)
        except Exception as exc:  # pragma: no cover - defensive
            log(NAMESPACE, status="summary_load_failed", key=key, error=str(exc))
            continue
        entry = {
            "summary_key": key,
            "session_id": data.get("session_id"),
            "test_code": data.get("test_type") or data.get("test_code"),
            "ai_score": data.get("score_primary") or data.get("score"),
        }
        summaries.append(entry)

    sampled = sample_entries(summaries, sample_size)
    signed: List[Dict[str, Any]] = []
    for entry in sampled:
        summary_key = entry["summary_key"]
        summary_url = generate_signed_url(
            bucket=bucket,
            key=summary_key,
            expiration=viz_expiration,
            region=region,
            client=client,
        )
        video_key = summary_key.replace("summary.json", "score.json")
        try:
            video_url = generate_signed_url(
                bucket=bucket,
                key=video_key,
                expiration=video_expiration,
                region=region,
                client=client,
            )
        except ClientError:
            video_url = ""
        viz_key = derive_visualization_key(summary_key)
        viz_url = ""
        if viz_key:
            try:
                viz_url = generate_signed_url(
                    bucket=bucket,
                    key=viz_key,
                    expiration=viz_expiration,
                    region=region,
                    client=client,
                )
            except ClientError:
                viz_url = ""

        signed.append(
            {
                "session_id": entry.get("session_id"),
                "test_code": entry.get("test_code"),
                "ai_score": entry.get("ai_score"),
                "summary_url": summary_url,
                "video_url": video_url,
                "viz_url": viz_url,
            }
        )

    duration = round((time.perf_counter() - start) * 1000, 2)
    log(
        NAMESPACE,
        status="fallback_complete",
        method="s3_fallback",
        sampled=len(signed),
        duration_ms=duration,
    )
    return "s3_fallback", signed


def output_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["session_id", "test_code", "ai_score", "summary_url", "video_url", "viz_url"]
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if boto3 is None:
        print("boto3 is required for this script", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=args.days)

    method = "s3_fallback"
    entries: List[Dict[str, Any]] = []

    if not args.force_s3:
        try:
            if describe_table_has_gsi(args.table_name, args.region):
                items = query_recent_sessions(
                    table_name=args.table_name,
                    env=args.env,
                    start=start,
                    end=now,
                    region=args.region,
                    limit=200,
                )
                if items:
                    method = "dynamodb_gsi"
                    sampled = sample_entries(items, args.sample_size)
                    for item in sampled:
                        video_key = item.get("video_key", "")
                        viz_key = item.get("viz_key", "")
                        video_url = generate_signed_url(
                            bucket=args.results_bucket,
                            key=video_key,
                            expiration=args.video_expiration,
                            region=args.region,
                        ) if video_key else ""
                        viz_url = generate_signed_url(
                            bucket=args.results_bucket,
                            key=viz_key,
                            expiration=args.viz_expiration,
                            region=args.region,
                        ) if viz_key else ""
                        entries.append(
                            {
                                "session_id": item.get("session_id"),
                                "test_code": item.get("test_type") or item.get("test_code"),
                                "ai_score": item.get("ai_score"),
                                "summary_url": "",
                                "video_url": video_url,
                                "viz_url": viz_url,
                            }
                        )
        except Exception as exc:  # pragma: no cover - defensive
            log(NAMESPACE, status="gsi_query_failed", error=str(exc))

    if method != "dynamodb_gsi":
        method, entries = fallback_collect(
            bucket=args.results_bucket,
            region=args.region,
            env=args.env,
            days=args.days,
            sample_size=args.sample_size,
            video_expiration=args.video_expiration,
            viz_expiration=args.viz_expiration,
        )

    output_csv(args.output, entries)
    log(NAMESPACE, status="completed", method=method, sampled=len(entries), output=str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
