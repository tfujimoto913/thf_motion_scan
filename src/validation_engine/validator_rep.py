"""
Purpose: Rep-level validation for single evaluation result
Responsibility: Validate required keys, types, versions compatibility, metrics ranges
Dependencies: typing, validation_engine.compat
Created: 2025-11-03 by Claude Code
Decision Log: Phase 5 - Validation System Integration (rep基盤実装)

CRITICAL:
- Must validate all required keys before processing
- Versions compatibility uses SemVer (MAJOR=ERROR, MINOR=WARN, PATCH=OK)
- Violations recorded with field, severity, message
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .compat import CompatibilityStatus, compare_versions

# Required keys for rep-level validation
REQUIRED_KEYS = {
    "session_id",
    "rep_index",
    "test_code",
    "metrics",
    "validation",
    "rules_version",
    "thresholds_version",
}


def validate_rep(
    rep_data: Dict[str, Any],
    expected_versions: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    What: Validate a single rep result and return validation state with violations.
    Why: Ensure rep data integrity before aggregation.
    Design Decision: Separate concerns - key validation, type validation, version compatibility.

    Args:
        rep_data: Single rep result dict (from JSONL line)
        expected_versions: Expected versions dict (rules_version, thresholds_version, normalization_version)

    Returns:
        Dict with:
            - state: OK | WARN | ERROR
            - violations: List[Dict] with field, severity, category, message

    CRITICAL:
    - Returns ERROR if any required key is missing
    - Returns ERROR if versions compatibility check fails (MAJOR diff)
    - Returns WARN if versions have MINOR diff
    - Returns OK if all checks pass
    """
    violations: List[Dict[str, Any]] = []

    # Step 1: Required keys validation
    missing_keys = REQUIRED_KEYS - set(rep_data.keys())
    if missing_keys:
        for key in missing_keys:
            violations.append(
                {
                    "field": key,
                    "severity": "ERROR",
                    "category": "missing_key",
                    "message": f"Required key '{key}' is missing",
                }
            )
        return {"state": CompatibilityStatus.ERROR, "violations": violations}

    # Step 2: Type validation
    type_checks = [
        ("session_id", str),
        ("rep_index", int),
        ("test_code", str),
        ("metrics", dict),
        ("validation", dict),
        ("rules_version", str),
        ("thresholds_version", str),
    ]

    for key, expected_type in type_checks:
        value = rep_data.get(key)
        if not isinstance(value, expected_type):
            violations.append(
                {
                    "field": key,
                    "severity": "ERROR",
                    "category": "type_error",
                    "message": f"Expected {expected_type.__name__}, got {type(value).__name__}",
                }
            )

    # If type errors exist, return ERROR immediately
    if violations:
        return {"state": CompatibilityStatus.ERROR, "violations": violations}

    # Step 3: Versions compatibility (if expected_versions provided)
    if expected_versions:
        current_versions = {
            "rules_version": rep_data.get("rules_version"),
            "thresholds_version": rep_data.get("thresholds_version"),
            "normalization_version": rep_data.get("normalization_version", "none"),
        }

        # Check each version field individually
        for key in ["rules_version", "thresholds_version", "normalization_version"]:
            current_val = current_versions.get(key)
            expected_val = expected_versions.get(key)

            # Skip if both are "none" (not version-managed)
            if current_val == "none" and expected_val == "none":
                continue

            # If only one is "none", it's an error
            if current_val == "none" or expected_val == "none":
                violations.append(
                    {
                        "field": key,
                        "severity": "ERROR",
                        "category": "version_compatibility",
                        "status": "ERROR",
                        "current": current_val,
                        "expected": expected_val,
                        "message": f"Version mismatch: one side is 'none', other is versioned.",
                    }
                )
                continue

            # If both are missing, treat as ERROR
            if not current_val or not expected_val:
                violations.append(
                    {
                        "field": key,
                        "severity": "ERROR",
                        "category": "version_compatibility",
                        "status": "ERROR",
                        "current": current_val,
                        "expected": expected_val,
                        "message": f"Missing version data for '{key}'.",
                    }
                )
                continue

            # Compare versions using SemVer
            try:
                status = compare_versions(current_val, expected_val)
                if status == CompatibilityStatus.ERROR:
                    violations.append(
                        {
                            "field": key,
                            "severity": "ERROR",
                            "category": "version_compatibility",
                            "status": "ERROR",
                            "current": current_val,
                            "expected": expected_val,
                            "message": f"MAJOR version difference detected (breaking change).",
                        }
                    )
                elif status == CompatibilityStatus.WARN:
                    violations.append(
                        {
                            "field": key,
                            "severity": "WARN",
                            "category": "version_compatibility",
                            "status": "WARN",
                            "current": current_val,
                            "expected": expected_val,
                            "message": f"MINOR version difference detected (backward compatible).",
                        }
                    )
            except ValueError as e:
                # Invalid SemVer format
                violations.append(
                    {
                        "field": key,
                        "severity": "ERROR",
                        "category": "version_compatibility",
                        "status": "ERROR",
                        "current": current_val,
                        "expected": expected_val,
                        "message": f"Invalid SemVer format: {e}",
                    }
                )

    # Step 4: Determine final state
    if any(v["severity"] == "ERROR" for v in violations):
        state = CompatibilityStatus.ERROR
    elif any(v["severity"] == "WARN" for v in violations):
        state = CompatibilityStatus.WARN
    else:
        state = CompatibilityStatus.OK

    return {"state": state, "violations": violations}
