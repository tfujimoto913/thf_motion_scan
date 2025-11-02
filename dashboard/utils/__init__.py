"""Dashboard utilities package."""

from .logging import (
    configure_structured_logging,
    emit_structured_log,
    execution_timer,
    record_error,
    log_dashboard_event,
    emit_ui_metric,
)
from .video_validator import VideoValidator

__all__ = [
    'VideoValidator',
    'configure_structured_logging',
    'emit_structured_log',
    'log_dashboard_event',
    'execution_timer',
    'record_error',
    'emit_ui_metric',
]
