"""Developer environment safeguards for threshold updates."""

from __future__ import annotations


class EnvironmentError(RuntimeError):
    """Raised when an operation is attempted outside the allowed environment."""


class ConfirmationError(RuntimeError):
    """Raised when the apply confirmation token is missing or invalid."""


def ensure_dev_environment(env: str) -> None:
    if env != "dev":
        raise EnvironmentError("Threshold changes can only be applied in the dev environment.")


def require_apply_confirmation(token: str) -> None:
    if token.strip() != "APPLY":
        raise ConfirmationError("To proceed, type APPLY in uppercase (safety confirmation).")


def should_block_apply(reclassified_rate: float, *, limit: float = 0.35, admin_override: bool = False) -> bool:
    if admin_override:
        return False
    return reclassified_rate > limit
