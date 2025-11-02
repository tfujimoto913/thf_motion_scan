"""
Structured logging and custom metric emission utilities shared across Lambda functions.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _epoch_millis() -> int:
    return int(time.time() * 1000)


@dataclass
class LoggerContext:
    """Holds per-invocation context for structured log entries."""

    request_id: Optional[str] = None
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "dev"))
    test_code: Optional[str] = None
    athlete_id: Optional[str] = None
    session_id: Optional[str] = None
    function_name: Optional[str] = field(
        default_factory=lambda: os.getenv("AWS_LAMBDA_FUNCTION_NAME", "local-worker")
    )
    rules_version: Optional[str] = field(default_factory=lambda: os.getenv("RULES_VERSION"))
    artifact_sha: Optional[str] = field(default_factory=lambda: os.getenv("ARTIFACT_SHA"))
    log_streams: Dict[str, str] = field(default_factory=dict)
    sequence_tokens: Dict[str, str] = field(default_factory=dict)


class StructuredLogger:
    """Emit structured logs and CloudWatch custom metrics."""

    def __init__(self) -> None:
        self._context = threading.local()
        self._logs_client = None  # lazy init
        self._metrics_client = None  # lazy init
        self._namespace = os.getenv("METRICS_NAMESPACE", "THF/MotionScan")
        self._log_groups = {
            "INFO": os.getenv("LOG_GROUP_INFO"),
            "WARNING": os.getenv("LOG_GROUP_WARN"),
            "ERROR": os.getenv("LOG_GROUP_ERROR"),
        }
        self._metrics_log_group = os.getenv("LOG_GROUP_METRICS")

    # ------------------------------------------------------------------ context
    def _get_context(self) -> LoggerContext:
        if not hasattr(self._context, "value"):
            self._context.value = LoggerContext()
        return self._context.value  # type: ignore[return-value]

    def set_context(
        self,
        *,
        request_id: Optional[str] = None,
        environment: Optional[str] = None,
        test_code: Optional[str] = None,
        athlete_id: Optional[str] = None,
        session_id: Optional[str] = None,
        function_name: Optional[str] = None,
    ) -> None:
        ctx = self._get_context()
        if request_id is not None:
            ctx.request_id = request_id
        if environment is not None:
            ctx.environment = environment
        if test_code is not None:
            ctx.test_code = test_code
        if athlete_id is not None:
            ctx.athlete_id = athlete_id
        if session_id is not None:
            ctx.session_id = session_id
        if function_name is not None:
            ctx.function_name = function_name

    def clear_context(self) -> None:
        self._context.value = LoggerContext()  # type: ignore[attr-defined]

    # -------------------------------------------------------------------- logging
    def _logs(self):
        if self._logs_client is None:
            self._logs_client = boto3.client("logs")
        return self._logs_client

    def _metrics(self):
        if self._metrics_client is None:
            self._metrics_client = boto3.client("cloudwatch")
        return self._metrics_client

    def log(
        self,
        level: str,
        message: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        exc_info: Optional[BaseException] = None,
    ) -> None:
        ctx = self._get_context()
        body: Dict[str, Any] = {
            "timestamp": _now_iso(),
            "level": level,
            "message": message,
            "requestId": ctx.request_id,
            "environment": ctx.environment,
            "testCode": ctx.test_code,
            "athleteId": ctx.athlete_id,
            "sessionId": ctx.session_id,
            "functionName": ctx.function_name,
        }
        if ctx.rules_version:
            body["rulesVersion"] = ctx.rules_version
        if ctx.artifact_sha:
            body["artifactSha"] = ctx.artifact_sha
        if payload:
            body.update(payload)
        if exc_info:
            body["error"] = {
                "type": type(exc_info).__name__,
                "message": str(exc_info),
            }

        message_str = json.dumps(body, ensure_ascii=False, default=str)

        # Always print to stdout for the default Lambda log group.
        print(message_str)

        log_group = self._log_groups.get(level.upper())
        if not log_group:
            return

        try:
            self._put_log_event(log_group, level.upper(), message_str)
        except Exception:
            # Fail silently to avoid impacting the Lambda invocation.
            pass

    def info(self, message: str, *, payload: Optional[Dict[str, Any]] = None) -> None:
        self.log("INFO", message, payload=payload)

    def warning(self, message: str, *, payload: Optional[Dict[str, Any]] = None) -> None:
        self.log("WARNING", message, payload=payload)

    def error(
        self,
        message: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        exc_info: Optional[BaseException] = None,
    ) -> None:
        self.log("ERROR", message, payload=payload, exc_info=exc_info)

    def _put_log_event(self, log_group: str, level: str, message: str) -> None:
        ctx = self._get_context()
        log_key = f"{log_group}:{level}"
        stream_name = ctx.log_streams.get(log_key)
        if stream_name is None:
            base = ctx.request_id or uuid.uuid4().hex
            stream_name = f"{base}-{level.lower()}"
            ctx.log_streams[log_key] = stream_name
            try:
                self._logs().create_log_stream(
                    logGroupName=log_group,
                    logStreamName=stream_name,
                )
            except self._logs().exceptions.ResourceAlreadyExistsException:
                pass

        token_key = f"{log_group}:{stream_name}"
        kwargs: Dict[str, Any] = {
            "logGroupName": log_group,
            "logStreamName": stream_name,
            "logEvents": [
                {
                    "timestamp": _epoch_millis(),
                    "message": message,
                }
            ],
        }
        if token_key in ctx.sequence_tokens:
            kwargs["sequenceToken"] = ctx.sequence_tokens[token_key]

        try:
            response = self._logs().put_log_events(**kwargs)
            token = response.get("nextSequenceToken")
            if token:
                ctx.sequence_tokens[token_key] = token
        except self._logs().exceptions.InvalidSequenceTokenException as exc:
            expected = exc.response["expectedSequenceToken"]
            kwargs["sequenceToken"] = expected
            response = self._logs().put_log_events(**kwargs)
            token = response.get("nextSequenceToken")
            if token:
                ctx.sequence_tokens[token_key] = token
        except ClientError:
            # Log group permissions or throttling – suppress to keep invocation healthy.
            pass

    # --------------------------------------------------------------------- metrics
    def metric(
        self,
        name: str,
        value: float,
        *,
        unit: str = "Count",
        dimensions: Optional[Dict[str, str]] = None,
    ) -> None:
        ctx = self._get_context()
        metric_dimensions = [
            {"Name": "Environment", "Value": ctx.environment},
        ]
        if ctx.test_code:
            metric_dimensions.append({"Name": "TestCode", "Value": ctx.test_code})
        if ctx.function_name:
            metric_dimensions.append({"Name": "FunctionName", "Value": ctx.function_name})

        if dimensions:
            for key, val in dimensions.items():
                metric_dimensions.append({"Name": key, "Value": val})

        data = {
            "MetricName": name,
            "Timestamp": datetime.utcnow(),
            "Value": float(value),
            "Unit": unit,
            "Dimensions": metric_dimensions,
        }

        try:
            self._metrics().put_metric_data(Namespace=self._namespace, MetricData=[data])
        except ClientError:
            pass

        if self._metrics_log_group:
            metrics_payload = {
                "timestamp": _now_iso(),
                "metric_name": name,
                "metric_value": value,
                "unit": unit,
                "environment": ctx.environment,
                "test_code": ctx.test_code,
                "function_name": ctx.function_name,
            }
            if dimensions:
                metrics_payload["dimensions"] = dimensions
            try:
                self._put_log_event(
                    self._metrics_log_group,
                    "INFO",
                    json.dumps(metrics_payload, ensure_ascii=False, default=str),
                )
            except Exception:
                pass


structured_logger = StructuredLogger()


def get_logger() -> StructuredLogger:
    return structured_logger
