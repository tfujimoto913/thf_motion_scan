"""
Purpose: Billing guardrail Lambda package (auto-suspend / cleanup / billing guard)
Responsibility: Shared utilities and handlers for cost-control automation.
Dependencies: boto3, botocore
Created: 2025-11-04 by Codex (GPT-5)
Decision Log: Phase 5 - Billing Guardrails v0.1

CRITICAL: Keep helper functions lightweight; SAM builds the whole lambda/ package.
"""

__all__ = [
    "auto_suspend",
    "auto_cleanup",
    "billing_guard",
    "common",
]
