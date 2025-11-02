"""
Purpose: ValidationEngine package initialization
Responsibility: Provide public API for validation state computations
Dependencies: apply, compat
Created: 2025-11-03 by Codex
Decision Log: Task B - ValidationEngine 中間層化

CRITICAL: Do not add heavy logic here; keep top-level imports lightweight
"""

from .apply import apply_rep, apply_session

__all__ = ["apply_rep", "apply_session"]
