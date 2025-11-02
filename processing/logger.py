"""
Structured logging adapters for the motion scan processing pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from common.structured_logging import get_logger


logger = get_logger()


def set_request_context(
    *,
    request_id: Optional[str] = None,
    environment: Optional[str] = None,
    function_name: Optional[str] = None,
) -> None:
    """Seed per-invocation logging context (called from Lambda handler)."""

    logger.set_context(
        request_id=request_id,
        environment=environment,
        function_name=function_name,
    )


def set_processing_context(
    *,
    test_code: Optional[str] = None,
    athlete_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Augment context once the test metadata is available."""

    logger.set_context(test_code=test_code, athlete_id=athlete_id, session_id=session_id)


def clear_context() -> None:
    """Reset per-invocation context (mainly for tests)."""

    logger.clear_context()


def log_info(
    message: str,
    *,
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    if test_type:
        logger.set_context(test_code=test_type)
    payload: Dict[str, Any] = {}
    if video_id:
        payload["videoId"] = video_id
    if context:
        payload["context"] = context
    logger.info(message, payload=payload or None)


def log_warning(
    message: str,
    *,
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    if test_type:
        logger.set_context(test_code=test_type)
    payload: Dict[str, Any] = {}
    if video_id:
        payload["videoId"] = video_id
    if context:
        payload["context"] = context
    logger.warning(message, payload=payload or None)


def log_error(
    message: str,
    *,
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    exc_info: Optional[BaseException] = None,
) -> None:
    if test_type:
        logger.set_context(test_code=test_type)
    payload: Dict[str, Any] = {}
    if video_id:
        payload["videoId"] = video_id
    if context:
        payload["context"] = context
    logger.error(message, payload=payload or None, exc_info=exc_info)


def log_processing_start(video_path: str, test_type: str, video_id: Optional[str] = None) -> None:
    set_processing_context(test_code=test_type)
    log_info(
        "Processing started",
        video_id=video_id,
        test_type=test_type,
        context={"video_path": video_path},
    )


def log_processing_complete(
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    score: Optional[float] = None,
    max_score: Optional[float] = None,
) -> None:
    payload: Dict[str, Any] = {}
    if score is not None:
        payload["score"] = score
    if max_score is not None:
        payload["max_score"] = max_score
    log_info(
        "Processing completed successfully",
        video_id=video_id,
        test_type=test_type,
        context=payload or None,
    )


def log_quality_check(
    detection_rate: float,
    quality_score: int,
    *,
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    passed: bool = True,
) -> None:
    payload = {
        "detection_rate": detection_rate,
        "quality_score": quality_score,
        "passed": passed,
    }
    if video_id:
        payload["videoId"] = video_id
    log_info("Quality check evaluated", test_type=test_type, context=payload)


def emit_metric(
    name: str,
    value: float,
    *,
    unit: str = "Count",
    dimensions: Optional[Dict[str, str]] = None,
) -> None:
    logger.metric(name, value, unit=unit, dimensions=dimensions or None)
