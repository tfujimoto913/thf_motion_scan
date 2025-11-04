"""
Purpose: Monitoring and alerting infrastructure
Responsibility: Event logging, alarm state tracking, incident reporting
Created: 2025-11-04 by Claude Code
Decision Log: ADR-TBD (UI Monitoring System v1)

CRITICAL:
- JSONL format for monitoring_events.jsonl
- CloudWatch Logs integration (Lambda layer)
- Idempotency for event deduplication
"""

from .event_logger import MonitoringEventLogger, get_event_logger

__all__ = ["MonitoringEventLogger", "get_event_logger"]
