"""
Lightweight AWS helpers for monitoring scripts.

Features:
    * CloudWatch get_metric_statistics wrapper
    * S3 list/get/put helpers
    * Exponential backoff with jitter on retryable errors
    * Structured logging (JSON lines) for observability tooling
"""

from __future__ import annotations

import json
import os
import random
import time
from typing import Any, Dict, Iterable, Optional

try:  # pragma: no cover - optional dependency for tests
    import boto3  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - fallback for missing boto3
    boto3 = None  # type: ignore

try:  # pragma: no cover - optional dependency for tests
    from botocore.exceptions import (
        BotoCoreError,
        ClientError,
        ConnectionClosedError,
        EndpointConnectionError,
    )
except ModuleNotFoundError:  # pragma: no cover - provide minimal stand-ins
    class _StubException(Exception):
        pass

    class ClientError(_StubException):  # type: ignore
        def __init__(self, response, operation_name):
            super().__init__(response)
            self.response = response
            self.operation_name = operation_name

    class BotoCoreError(_StubException):  # type: ignore
        pass

    class ConnectionClosedError(_StubException):  # type: ignore
        pass

    class EndpointConnectionError(_StubException):  # type: ignore
        pass

DEFAULT_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")

_SESSION = None

RETRYABLE_ERROR_CODES = {
    "SlowDown",
    "Throttling",
    "ThrottlingException",
    "RequestLimitExceeded",
    "ProvisionedThroughputExceededException",
    "InternalError",
    "InternalServerError",
    "ServiceUnavailable",
    "TooManyRequestsException",
}


def _structured_log(action: str, *, duration_ms: Optional[float] = None, error: Optional[str] = None, **context: Any) -> None:
    payload: Dict[str, Any] = {
        "action": action,
        "environment": ENVIRONMENT,
    }
    if duration_ms is not None:
        payload["duration_ms"] = round(duration_ms, 2)
    if error:
        payload["error"] = error
    if context:
        payload.update(context)
    print(json.dumps(payload, ensure_ascii=False, default=str))


def _get_client(service: str, region: Optional[str], client: Any = None):
    if client is not None:
        return client
    if boto3 is None:
        raise RuntimeError("boto3 is required when no client is provided")
    global _SESSION
    if _SESSION is None:
        _SESSION = boto3.session.Session()
    return _SESSION.client(service, region_name=region or DEFAULT_REGION)


def _is_retryable(exception: Exception) -> bool:
    if isinstance(exception, ClientError):
        code = (exception.response or {}).get("Error", {}).get("Code", "")
        return str(code) in RETRYABLE_ERROR_CODES
    if isinstance(exception, (EndpointConnectionError, ConnectionClosedError, BotoCoreError)):
        return True
    return False


def _execute_with_retry(
    action: str,
    func,
    *,
    max_attempts: int = 5,
    base_delay: float = 0.5,
    multiplier: float = 2.0,
    jitter: float = 0.3,
    log_context: Optional[Dict[str, Any]] = None,
):
    attempt = 0
    last_err: Optional[Exception] = None
    while attempt < max_attempts:
        start = time.perf_counter()
        try:
            result = func()
            duration = (time.perf_counter() - start) * 1000
            _structured_log(action, duration_ms=duration, attempt=attempt + 1, **(log_context or {}))
            return result
        except Exception as exc:  # pragma: no cover - fallback
            duration = (time.perf_counter() - start) * 1000
            should_retry = attempt < max_attempts - 1 and _is_retryable(exc)
            _structured_log(
                action,
                duration_ms=duration,
                error=str(exc),
                attempt=attempt + 1,
                **(log_context or {}),
            )
            if not should_retry:
                raise
            last_err = exc
            sleep_for = base_delay * (multiplier ** attempt)
            sleep_for += random.uniform(0, jitter)
            time.sleep(sleep_for)
            attempt += 1
    if last_err:
        raise last_err


def get_metric_statistics(
    *,
    namespace: str,
    metric_name: str,
    start_time,
    end_time,
    period: int,
    statistics: Iterable[str],
    dimensions: Optional[Iterable[Dict[str, str]]] = None,
    unit: Optional[str] = None,
    region: Optional[str] = None,
    client=None,
) -> Dict[str, Any]:
    """Fetch CloudWatch metric statistics with retry."""

    cloudwatch = _get_client("cloudwatch", region, client)

    params: Dict[str, Any] = {
        "Namespace": namespace,
        "MetricName": metric_name,
        "StartTime": start_time,
        "EndTime": end_time,
        "Period": int(period),
        "Statistics": list(statistics),
    }
    if dimensions:
        params["Dimensions"] = list(dimensions)
    if unit:
        params["Unit"] = unit

    return _execute_with_retry(
        "cloudwatch.get_metric_statistics",
        lambda: cloudwatch.get_metric_statistics(**params),
        log_context={"metric_name": metric_name, "namespace": namespace, "period": period},
    )


def list_s3_objects(
    *,
    bucket: str,
    prefix: Optional[str] = None,
    region: Optional[str] = None,
    client=None,
    **extra: Any,
) -> Dict[str, Any]:
    """List S3 objects with retry, returns raw response."""

    s3 = _get_client("s3", region, client)
    params: Dict[str, Any] = {"Bucket": bucket}
    if prefix:
        params["Prefix"] = prefix
    params.update(extra)

    return _execute_with_retry(
        "s3.list_objects_v2",
        lambda: s3.list_objects_v2(**params),
        log_context={"bucket": bucket, "prefix": prefix},
    )


def get_s3_object(
    *,
    bucket: str,
    key: str,
    region: Optional[str] = None,
    client=None,
    as_text: bool = False,
    encoding: str = "utf-8",
    **extra: Any,
):
    """Retrieve an S3 object (bytes or decoded text)."""

    s3 = _get_client("s3", region, client)
    params = {"Bucket": bucket, "Key": key}
    params.update(extra)

    response = _execute_with_retry(
        "s3.get_object",
        lambda: s3.get_object(**params),
        log_context={"bucket": bucket, "key": key},
    )
    body = response["Body"].read()
    return body.decode(encoding) if as_text else body


def put_s3_object(
    *,
    bucket: str,
    key: str,
    body: Any,
    region: Optional[str] = None,
    client=None,
    content_type: Optional[str] = None,
    encoding: str = "utf-8",
    **extra: Any,
) -> Dict[str, Any]:
    """Upload an object to S3 using retry/backoff."""

    s3 = _get_client("s3", region, client)
    if isinstance(body, str):
        data = body.encode(encoding)
    else:
        data = body

    params: Dict[str, Any] = {"Bucket": bucket, "Key": key, "Body": data}
    if content_type:
        params["ContentType"] = content_type
    params.update(extra)

    return _execute_with_retry(
        "s3.put_object",
        lambda: s3.put_object(**params),
        log_context={"bucket": bucket, "key": key, "size": len(data)},
    )


__all__ = [
    "get_metric_statistics",
    "list_s3_objects",
    "get_s3_object",
    "put_s3_object",
]
