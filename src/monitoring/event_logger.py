"""
Purpose: Monitoring event logger for billing and UI alerts
Responsibility: Record alarm triggers, threshold breaches, rollback events
Created: 2025-11-04 by Claude Code
Decision Log: ADR-TBD (UI Monitoring System v1)

CRITICAL:
- JSONL format for append-friendly logging
- Idempotency key to prevent duplicate entries
- CloudWatch Logs integration for Lambda
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Optional


class MonitoringEventLogger:
    """
    What: Logger for monitoring events (alarms, thresholds, rollbacks)
    Why: Audit trail for operational events and incident investigation
    Design Decision: JSONL format, idempotency protection, local + CloudWatch

    Log Path: logs/monitoring_events.jsonl
    """

    def __init__(
        self,
        log_path: Path = Path("logs/monitoring_events.jsonl"),
        cache_size: int = 50,
    ):
        """
        Args:
            log_path: Path to JSONL log file
            cache_size: Number of recent event IDs to cache for deduplication
        """
        self.log_path = log_path
        self.cache_size = cache_size

        # What: Deduplication cache (recent event idempotency keys)
        # Why: Prevent duplicate logging of same event
        self._event_cache: Deque[str] = deque(maxlen=cache_size)

        # Load recent event IDs from log file
        self._load_recent_event_ids()

    def _load_recent_event_ids(self) -> None:
        """
        What: Load recent event IDs from log file to initialize cache
        Why: Prevent duplicates across process restarts
        """
        if not self.log_path.exists():
            return

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[-self.cache_size :]:
                    if line.strip():
                        entry = json.loads(line)
                        if "event_id" in entry:
                            self._event_cache.append(entry["event_id"])
        except (json.JSONDecodeError, IOError):
            # File corruption or access error - continue with empty cache
            pass

    def _generate_event_id(
        self,
        event_type: str,
        component: str,
        severity: str,
        threshold: float,
        actual_value: float,
    ) -> str:
        """
        What: Generate idempotency key for event
        Why: Prevent duplicate logging of same event
        Design Decision: sha256 hash of normalized event data

        Args:
            event_type: alarm_triggered, threshold_breached, rollback_initiated, etc.
            component: billing, ui, validation
            severity: info, warn, fail
            threshold: Threshold value
            actual_value: Actual measured value

        Returns:
            str: SHA256 hash (first 16 chars)
        """
        normalized = json.dumps(
            {
                "event_type": event_type,
                "component": component,
                "severity": severity,
                "threshold": threshold,
                "actual_value": actual_value,
            },
            sort_keys=True,
        )
        full_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return full_hash[:16]  # Use first 16 chars for brevity

    def log_event(
        self,
        event_type: str,
        component: str,
        severity: str,
        threshold: float,
        actual_value: float,
        action_taken: str,
        actor: str = "system",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        What: Log a monitoring event to JSONL file
        Why: Create audit trail for alarms, rollbacks, and operational actions
        Design Decision: Idempotency protection, structured schema

        Args:
            event_type: alarm_triggered, threshold_breached, rollback_initiated, etc.
            component: billing, ui, validation
            severity: info, warn, fail
            threshold: Threshold value that was compared
            actual_value: Actual measured value
            action_taken: Description of action (acknowledged, rollback, etc.)
            actor: User or system that took action
            metadata: Additional context (alarm_name, state_reason, etc.)

        Returns:
            Optional[str]: Event ID if logged, None if duplicate
        """
        # Generate event ID for idempotency
        event_id = self._generate_event_id(
            event_type, component, severity, threshold, actual_value
        )

        # Check for duplicate
        if event_id in self._event_cache:
            return None

        # Build log entry
        timestamp = datetime.now(timezone.utc)
        entry = {
            "event_id": event_id,
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
            "component": component,
            "severity": severity,
            "threshold": threshold,
            "actual_value": actual_value,
            "action_taken": action_taken,
            "actor": actor,
            "metadata": metadata or {},
        }

        # Append to log file
        self._append_to_log(entry)

        # Update cache
        self._event_cache.append(event_id)

        return event_id

    def _append_to_log(self, entry: dict[str, Any]) -> None:
        """
        What: Append entry to JSONL log file
        Why: Persist event for audit trail

        Args:
            entry: Log entry dictionary
        """
        # Ensure log directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Append to file
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_recent_events(self, n: int = 20) -> list[dict[str, Any]]:
        """
        What: Load recent N events from log file
        Why: Display in UI or for analysis

        Args:
            n: Number of recent events to retrieve

        Returns:
            list[dict]: Recent events (newest first)
        """
        if not self.log_path.exists():
            return []

        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                recent = [json.loads(line) for line in lines[-n:] if line.strip()]
                return list(reversed(recent))
        except (json.JSONDecodeError, IOError):
            return []


# What: Global logger instance
# Why: Singleton pattern for shared cache across module
_global_logger: Optional[MonitoringEventLogger] = None


def get_event_logger(
    log_path: Path = Path("logs/monitoring_events.jsonl"),
    cache_size: int = 50,
) -> MonitoringEventLogger:
    """
    What: Get or create global MonitoringEventLogger instance
    Why: Singleton pattern for consistent event deduplication

    Args:
        log_path: Path to JSONL log file
        cache_size: Deduplication cache size

    Returns:
        MonitoringEventLogger: Global logger instance
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = MonitoringEventLogger(log_path=log_path, cache_size=cache_size)
    return _global_logger


# Convenience functions for common event types

def log_alarm_triggered(
    component: str,
    severity: str,
    threshold: float,
    actual_value: float,
    alarm_name: str,
    state_reason: str = "",
    actor: str = "cloudwatch",
) -> Optional[str]:
    """
    What: Log CloudWatch alarm trigger event
    Why: Record when alarms enter ALARM state

    Args:
        component: billing, ui, validation
        severity: warn, fail
        threshold: Alarm threshold
        actual_value: Measured value
        alarm_name: CloudWatch alarm name
        state_reason: Alarm state reason
        actor: Who/what triggered (default: cloudwatch)

    Returns:
        Optional[str]: Event ID if logged, None if duplicate
    """
    logger = get_event_logger()
    return logger.log_event(
        event_type="alarm_triggered",
        component=component,
        severity=severity,
        threshold=threshold,
        actual_value=actual_value,
        action_taken="acknowledged",
        actor=actor,
        metadata={"alarm_name": alarm_name, "state_reason": state_reason},
    )


def log_rollback(
    component: str,
    reason: str,
    rollback_to_version: str,
    actor: str,
) -> Optional[str]:
    """
    What: Log rollback event
    Why: Record when system reverts to previous version

    Args:
        component: billing, ui, validation, lambda, thresholds
        reason: Rollback reason (cost_overrun, performance_degradation, etc.)
        rollback_to_version: Version/commit hash rolled back to
        actor: User who initiated rollback

    Returns:
        Optional[str]: Event ID if logged, None if duplicate
    """
    logger = get_event_logger()
    return logger.log_event(
        event_type="rollback_initiated",
        component=component,
        severity="warn",
        threshold=0.0,  # N/A for rollback
        actual_value=0.0,  # N/A for rollback
        action_taken=f"rollback to {rollback_to_version}",
        actor=actor,
        metadata={"reason": reason, "rollback_to_version": rollback_to_version},
    )


def log_threshold_breach(
    component: str,
    severity: str,
    threshold: float,
    actual_value: float,
    metric_name: str,
    actor: str = "system",
) -> Optional[str]:
    """
    What: Log threshold breach event
    Why: Record when metrics exceed configured thresholds

    Args:
        component: billing, ui, validation
        severity: warn, fail
        threshold: Configured threshold
        actual_value: Measured value
        metric_name: Name of metric that breached
        actor: Who detected breach

    Returns:
        Optional[str]: Event ID if logged, None if duplicate
    """
    logger = get_event_logger()
    return logger.log_event(
        event_type="threshold_breached",
        component=component,
        severity=severity,
        threshold=threshold,
        actual_value=actual_value,
        action_taken="investigation_required",
        actor=actor,
        metadata={"metric_name": metric_name},
    )
