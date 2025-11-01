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
from typing import Any, Dict, Optional

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
