#!/usr/bin/env python3
"""
Fetch CloudWatch metrics and persist JSON / Markdown reports.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from scripts.monitoring.lib import aws, io

DEFAULT_METRICS = [
    "LandmarkDetectionRate:Average",
    "LandmarkDetectionFailures:Sum",
    "AnalysesCompleted:Sum",
]


def _structured_log(action: str, **payload: object) -> None:
    entry = {"action": action, "timestamp": datetime.now(timezone.utc).isoformat()}
    entry.update(payload)
    print(json.dumps(entry, ensure_ascii=False, default=str))


def _parse_metric_arg(arg: str) -> Tuple[str, str]:
    parts = arg.split(":")
    if len(parts) == 1:
        return parts[0], "Average"
    if len(parts) == 2:
        metric, statistic = parts
        if not metric or not statistic:
            raise argparse.ArgumentTypeError("Metric specification must be NAME[:STATISTIC]")
        return metric, statistic
    raise argparse.ArgumentTypeError("Metric specification must be NAME or NAME:STATISTIC")


def _parse_dimensions(dimensions: Sequence[str]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for dim in dimensions:
        if "=" not in dim:
            raise argparse.ArgumentTypeError("Dimensions must be formatted as Name=Value")
        name, value = dim.split("=", 1)
        if not name or not value:
            raise argparse.ArgumentTypeError("Dimensions must be formatted as Name=Value")
        parsed[name] = value
    return parsed


def _parse_period(value: str) -> int:
    value = value.strip().lower()
    if value.endswith("h"):
        hours = float(value[:-1])
        return int(hours * 3600)
    if value.endswith("d"):
        days = float(value[:-1])
        return int(days * 86400)
    raise argparse.ArgumentTypeError("Period must end with 'h' or 'd' (e.g., 24h, 7d)")


def _latest_datapoint(datapoints: List[Dict[str, object]], statistic: str):
    if not datapoints:
        return None
    sorted_points = sorted(datapoints, key=lambda d: d.get("Timestamp"))
    latest = sorted_points[-1]
    value = latest.get(statistic)
    timestamp = latest.get("Timestamp")
    return value, timestamp


def collect_metric(
    *,
    metric_name: str,
    statistic: str,
    namespace: str,
    environment: str,
    start_time: datetime,
    end_time: datetime,
    resolution_seconds: int,
    extra_dimensions: Dict[str, str],
    region: Optional[str],
) -> Dict[str, object]:
    dimensions = {"Environment": environment}
    dimensions.update(extra_dimensions)
    response = aws.get_metric_statistics(
        namespace=namespace,
        metric_name=metric_name,
        start_time=start_time,
        end_time=end_time,
        period=resolution_seconds,
        statistics=[statistic],
        dimensions=[{"Name": key, "Value": value} for key, value in sorted(dimensions.items())],
        region=region,
    )
    datapoints: List[Dict[str, object]] = response.get("Datapoints", [])
    result: Dict[str, object] = {
        "metric": metric_name,
        "statistic": statistic,
        "datapoint_count": len(datapoints),
        "unit": datapoints[0].get("Unit") if datapoints else None,
        "dimensions": dimensions,
    }
    latest = _latest_datapoint(datapoints, statistic)
    if latest is not None:
        value, timestamp = latest
        result["latest_value"] = value
        if hasattr(timestamp, "isoformat"):
            result["timestamp"] = timestamp.isoformat()
        else:
            result["timestamp"] = timestamp
    return result


def write_reports(
    *,
    output_dir: Path,
    env: str,
    period_label: str,
    generated_at: datetime,
    successes: List[Dict[str, object]],
    failures: List[str],
    retry_args: Sequence[str],
) -> None:
    base_name = f"cloudwatch_metrics_{env}_{period_label}"
    json_path = output_dir / f"{base_name}.json"
    md_path = output_dir / f"{base_name}.md"

    payload = {
        "environment": env,
        "period": period_label,
        "generated_at": generated_at.isoformat(),
        "metrics": successes,
        "failed_metrics": failures,
    }
    io.write_json(json_path, payload)

    table_rows = [
        {
            "metric": entry.get("metric", "-"),
            "value": entry.get("latest_value", "-"),
            "timestamp": entry.get("timestamp", "-"),
        }
        for entry in successes
    ]
    retry_command = None
    if failures:
        retry_command = "python scripts/monitoring/get_metrics_cli.py " + " ".join(retry_args)
    io.write_markdown(md_path, table_rows, partial=bool(failures), retry_command=retry_command)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch CloudWatch monitoring metrics")
    parser.add_argument("--env", default="dev", help="Environment dimension value (default: dev)")
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (defaults to AWS_REGION / AWS_DEFAULT_REGION environment variables)",
    )
    parser.add_argument(
        "--period",
        default="24h",
        help="Lookback period (e.g., 24h, 7d)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=300,
        help="CloudWatch period in seconds (default: 300)",
    )
    parser.add_argument(
        "--metric",
        dest="metrics",
        action="append",
        default=None,
        help="Metric specification NAME[:STATISTIC]. Repeatable.",
    )
    parser.add_argument(
        "--dimension",
        action="append",
        default=[],
        help="Additional dimension in the form Name=Value. Repeatable.",
    )
    parser.add_argument(
        "--namespace",
        default="THF/MotionScan",
        help="CloudWatch namespace (default: THF/MotionScan)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/monitoring"),
        help="Directory for JSON/Markdown reports (default: docs/monitoring)",
    )
    parser.add_argument(
        "--end-time",
        default=None,
        help="End time ISO8601 (defaults to current UTC time)",
    )
    return parser


def run_cli(args: argparse.Namespace, *, current_time: Optional[datetime] = None) -> int:
    start_perf = time.perf_counter()
    now = current_time or datetime.now(timezone.utc)
    lookback_seconds = _parse_period(args.period)
    metric_specs = args.metrics or DEFAULT_METRICS
    parsed_metrics: List[Tuple[str, str, str]] = []
    for spec in metric_specs:
        name, stat = _parse_metric_arg(spec)
        parsed_metrics.append((name, stat, spec))
    extra_dimensions = _parse_dimensions(args.dimension)

    end_time = (
        datetime.fromisoformat(args.end_time) if args.end_time else now
    )
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    start_time = end_time - timedelta(seconds=lookback_seconds)

    _structured_log(
        "get_metrics",
        status="start",
        environment=args.env,
        period_seconds=lookback_seconds,
        resolution=args.resolution,
        metric_count=len(parsed_metrics),
    )

    successes: List[Dict[str, object]] = []
    failures: List[str] = []

    for metric_name, statistic, spec in parsed_metrics:
        metric_start = time.perf_counter()
        try:
            result = collect_metric(
                metric_name=metric_name,
                statistic=statistic,
                namespace=args.namespace,
                environment=args.env,
                start_time=start_time,
                end_time=end_time,
                resolution_seconds=args.resolution,
                extra_dimensions=extra_dimensions,
                region=args.region,
            )
            successes.append(result)
            _structured_log(
                "get_metrics",
                status="metric_success",
                metric=metric_name,
                statistic=statistic,
                datapoints=result["datapoint_count"],
                duration_ms=round((time.perf_counter() - metric_start) * 1000, 2),
            )
        except Exception as exc:  # pragma: no cover - defensive
            failures.append(spec)
            _structured_log(
                "get_metrics",
                status="metric_failure",
                metric=metric_name,
                statistic=statistic,
                error=str(exc),
                duration_ms=round((time.perf_counter() - metric_start) * 1000, 2),
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    retry_args: List[str] = [
        f"--env {args.env}",
        f"--period {args.period}",
    ]
    if args.region:
        retry_args.insert(0, f"--region {args.region}")
    if args.namespace != "THF/MotionScan":
        retry_args.append(f"--namespace {args.namespace}")
    for dim in args.dimension:
        retry_args.append(f"--dimension {dim}")
    for spec in failures:
        retry_args.append(f"--metric {spec}")

    write_reports(
        output_dir=args.output_dir,
        env=args.env,
        period_label=args.period,
        generated_at=end_time,
        successes=successes,
        failures=failures,
        retry_args=retry_args,
    )

    total_duration = round((time.perf_counter() - start_perf) * 1000, 2)
    if failures:
        _structured_log(
            "get_metrics",
            status="partial",
            failed_metrics=failures,
            exit_code=2,
            total_duration_ms=total_duration,
        )
        return 2

    _structured_log(
        "get_metrics",
        status="success",
        exit_code=0,
        total_duration_ms=total_duration,
        metric_count=len(successes),
    )
    return 0


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run_cli(args)
    except KeyboardInterrupt:  # pragma: no cover - user cancelled
        _structured_log("get_metrics", status="interrupted")
        return 130
    except Exception as exc:  # pragma: no cover - unexpected error
        _structured_log("get_metrics", status="failure", error=str(exc))
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
