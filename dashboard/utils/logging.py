"""
Structured logging utilities for the dashboard.

Purpose:
  - Emit JSON-formatted logs to STDOUT so that CloudWatch Logs などの集約レイヤーで扱いやすくする
  - Provide helper to annotate events with dashboard-specific metadata

Usage:
    from utils.logging import configure_structured_logging, emit_structured_log

    configure_structured_logging()
    emit_structured_log({"event_type": "view_list", ...})

Design Notes:
  - Only adds a handler once (safe to call configure multiple times)
  - Message payloads are dictionaries; the formatter merges base fields
"""

from __future__ import annotations

import json
import logging
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import boto3
import streamlit as st

from config import PERFORMANCE_LIMITS


LOGGER_NAME = "thf.motion_scan.dashboard"


class JsonFormatter(logging.Formatter):
    """Serialize log records as compact JSON."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - inherited docstring
        base: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
        }

        if isinstance(record.msg, dict):
            base.update(record.msg)
        else:
            base["message"] = record.getMessage()

        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(base, ensure_ascii=False, separators=(",", ":"))


def configure_structured_logging() -> logging.Logger:
    """Ensure the dashboard logger is configured for JSON output."""

    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


_metrics_client: Optional[boto3.client] = None


def _get_metrics_client():
    global _metrics_client
    if _metrics_client is None:
        _metrics_client = boto3.client("cloudwatch")
    return _metrics_client


def emit_structured_log(payload: Dict[str, Any], level: int = logging.INFO) -> None:
    """Emit a JSON structured log entry.

    Args:
        payload: JSON serialisable dictionary to log
        level: Logging level (defaults to INFO)
    """

    logger = configure_structured_logging()
    logger.log(level, payload)


def log_dashboard_event(event_type: str, level: int = logging.INFO, **payload: Any) -> None:
    """Emit a structured log enriched with dashboard metadata."""

    request_id = st.session_state.get('request_id') if 'request_id' in st.session_state else None
    environment = st.session_state.get('selected_env', None)
    base_payload: Dict[str, Any] = {
        'event_type': event_type,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'request_id': request_id,
        'environment': environment,
    }

    for key, value in payload.items():
        if isinstance(value, (dict, list, tuple, str, int, float, bool)) or value is None:
            base_payload[key] = value
        else:
            base_payload[key] = str(value)

    emit_structured_log(base_payload, level=level)


class ExecutionStats:
    """Holds timing information for a measured block."""

    def __init__(self) -> None:
        self.duration_ms: Optional[float] = None


@contextmanager
def execution_timer(event_type: str, **metadata: Any):
    """Measure execution time, log it, and warn on threshold breach."""

    stats = ExecutionStats()
    start = time.perf_counter()

    try:
        yield stats
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        stats.duration_ms = duration_ms

        payload = dict(metadata)
        payload['execution_time_ms'] = round(duration_ms, 2)
        log_dashboard_event(event_type, **payload)

        threshold = PERFORMANCE_LIMITS.get('slow_query_threshold_ms', 800)
        if duration_ms > threshold:
            log_dashboard_event(
                f"{event_type}_slow",
                level=logging.WARNING,
                execution_time_ms=round(duration_ms, 2),
                threshold_ms=threshold,
                **metadata,
            )


def record_error(context: str, error: str) -> None:
    """Append an error entry to session state with bounded history."""

    entry = {
        'context': context,
        'error': error,
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }
    error_log = st.session_state.setdefault('error_log', [])
    error_log.append(entry)
    if len(error_log) > 20:
        del error_log[0]


def emit_ui_metric(
    event_type: str,
    *,
    value: float = 1.0,
    test_code: Optional[str] = None,
    session_id: Optional[str] = None,
    environment: Optional[str] = None,
    debounce_seconds: float = 1.0,
) -> None:
    """
    Emit a CloudWatch custom metric for dashboard UI events.

    Args:
        event_type: Logical UI event (e.g., env_switch, cache_clear, compare_run)
        value: Metric value (default 1.0)
        test_code: Optional test identifier; defaults to '-' when omitted
        session_id: Optional session identifier; defaults to '-' when omitted
        environment: Deployment environment; falls back to sidebar selection
        debounce_seconds: Minimum seconds between identical emissions
    """

    if not event_type:
        return

    env_value = environment or st.session_state.get('selected_env') or "unknown"
    env_value_str = str(env_value)
    test_value = str(test_code) if test_code else "-"
    session_value = str(session_id) if session_id else "-"
    state_key = "_ui_metric_last_emission"
    emission_state: Dict[Tuple[str, str, str, str], float] = st.session_state.setdefault(state_key, {})
    dedupe_key = (
        event_type,
        test_value,
        session_value,
        env_value_str,
    )
    now = time.time()
    last_emission = emission_state.get(dedupe_key)
    if last_emission is not None and now - last_emission < debounce_seconds:
        return

    dimensions = [
        {"Name": "Environment", "Value": env_value_str},
        {"Name": "EventType", "Value": event_type},
        {"Name": "TestCode", "Value": test_value},
        {"Name": "SessionId", "Value": session_value},
    ]

    try:
        _get_metrics_client().put_metric_data(
            Namespace="THF/MotionScan",
            MetricData=[
                {
                    "MetricName": "UIEvent",
                    "Timestamp": datetime.utcnow(),
                    "Value": float(value),
                    "Unit": "Count",
                    "Dimensions": dimensions,
                }
            ],
        )
        emission_state[dedupe_key] = now
    except Exception as exc:  # noqa: BLE001
        log_dashboard_event(
            "ui_metric_emit_failed",
            level=logging.WARNING,
            event_type=event_type,
            error=str(exc),
        )
