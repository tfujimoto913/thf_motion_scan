"""Auto-suspend Lambda handler.

Stops tagged EC2 instances and throttles tagged Lambda functions when traffic
falls below the configured threshold within the lookback window.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import timedelta
from typing import Any, Dict, List, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from .common import (
    emit_billing_event,
    load_metric_sources,
    stop_tagged_instances,
    throttle_tagged_lambdas,
    utc_now,
)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

cloudwatch = boto3.client("cloudwatch")
ec2 = boto3.client("ec2")
lambda_client = boto3.client("lambda")
events = boto3.client("events")

REQ_THRESHOLD = int(os.getenv("REQ_THRESHOLD", "1"))
LOOKBACK_HOURS = max(int(os.getenv("LOOKBACK_H", "2")), 1)
METRIC_SOURCES_RAW = os.getenv("METRIC_SOURCES", "")
TAG_KEY = os.getenv("AUTOSUSPEND_TAG_KEY", "AutoSuspend")
TAG_VALUE = os.getenv("AUTOSUSPEND_TAG_VALUE", "true")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")


def _gather_metric_sum(metric: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """Fetch metric statistics and return aggregated sum for the period."""
    stat = metric.get("Stat", "Sum")
    period = int(metric.get("Period", 3600))
    lookback_seconds = LOOKBACK_HOURS * 3600
    period = max(60, min(period, lookback_seconds))

    end_time = utc_now()
    start_time = end_time - timedelta(seconds=lookback_seconds)

    response = cloudwatch.get_metric_statistics(
        Namespace=metric["Namespace"],
        MetricName=metric["MetricName"],
        Dimensions=metric.get("Dimensions", []),
        StartTime=start_time,
        EndTime=end_time,
        Period=period,
        Statistics=[stat],
    )

    datapoints = response.get("Datapoints", [])
    total = 0.0
    for dp in datapoints:
        value = dp.get(stat)
        if value is None:
            continue
        total += float(value)

    detail = {
        "namespace": metric["Namespace"],
        "metric": metric["MetricName"],
        "stat": stat,
        "period": period,
        "dimensions": metric.get("Dimensions", []),
        "sum": total,
        "datapoints": len(datapoints),
    }

    return total, detail


def _evaluate_traffic() -> Tuple[float, List[Dict[str, Any]]]:
    sources = load_metric_sources(METRIC_SOURCES_RAW)
    if not sources:
        LOGGER.warning("No metric sources configured; defaulting to zero traffic")
        return 0.0, []

    total = 0.0
    breakdown: List[Dict[str, Any]] = []

    for metric in sources:
        try:
            metric_total, detail = _gather_metric_sum(metric)
        except (ClientError, BotoCoreError) as exc:
            LOGGER.warning("Metric fetch failed for %s/%s: %s", metric["Namespace"], metric["MetricName"], exc)
            breakdown.append({
                "namespace": metric["Namespace"],
                "metric": metric["MetricName"],
                "error": str(exc),
            })
            continue

        total += metric_total
        breakdown.append(detail)

    return total, breakdown


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda entry point."""
    total, breakdown = _evaluate_traffic()
    force = isinstance(event, dict) and bool(event.get("force"))
    dry_run = isinstance(event, dict) and bool(event.get("dry_run"))

    summary = {
        "threshold": REQ_THRESHOLD,
        "lookback_hours": LOOKBACK_HOURS,
        "traffic_sum": total,
        "metrics": breakdown,
        "forced": force,
        "dry_run": dry_run,
    }

    if total > REQ_THRESHOLD and not force:
        emit_billing_event(
            kind="traffic_ok",
            source="auto_suspend",
            payload={**summary, "environment": ENVIRONMENT},
            context=context,
        )
        return {"ok": True, "reason": "traffic_ok", **summary}

    if dry_run:
        instances: List[str] = []
        throttled: List[Dict[str, Any]] = []
    else:
        instances = stop_tagged_instances(ec2, tag_key=TAG_KEY, tag_value=TAG_VALUE)
        throttled = throttle_tagged_lambdas(
            lambda_client,
            events,
            tag_key=TAG_KEY,
            tag_value=TAG_VALUE,
        )

    action_summary = {
        **summary,
        "instances_stopped": instances,
        "lambda_throttled": throttled,
        "environment": ENVIRONMENT,
    }

    emit_billing_event(
        kind="auto_suspend",
        source="auto_suspend",
        payload=action_summary,
        context=context,
    )

    return {
        "ok": True,
        "reason": "auto_suspended",
        "suspended": {
            "ec2": instances,
            "lambda": throttled,
        },
        **summary,
    }
