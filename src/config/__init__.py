"""
Purpose: Config module for thresholds.json loading and compatibility checking
Responsibility: Centralize config loading and version management
Dependencies: None
Created: 2025-11-03
Decision Log: ADR-031 (thresholds.json compatibility checker)

CRITICAL: This module provides core config infrastructure for the project
"""

from .loader import load_thresholds
from .compat import check_compat

__all__ = ["load_thresholds", "check_compat"]
