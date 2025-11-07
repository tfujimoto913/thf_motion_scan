"""
Monitoring shared utilities package.

Exports:
    aws   - AWS service wrappers with retry/backoff and structured logs.
    io    - JSON/Markdown helpers for metric reports.
    stats - Statistical utilities for GT metrics (BCR, kappa, override rate).
"""

from . import aws, io, stats

__all__ = ["aws", "io", "stats"]
