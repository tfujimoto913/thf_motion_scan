"""
Purpose: Check version compatibility between current and required thresholds
Responsibility: SemVer parsing, comparison, and compatibility determination
Dependencies: re, typing
Created: 2025-11-03
Decision Log: ADR-031 (thresholds.json compatibility checker)

CRITICAL: MAJOR diff = ERROR, MINOR diff = WARN, PATCH diff = OK
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple

# Setup logger for structured logging
logger = logging.getLogger(__name__)


def parse_semver(version: str) -> Optional[Tuple[int, int, int]]:
    """
    Parse semantic version string into (major, minor, patch) tuple.

    What: Extract numeric components from version string
    Why: Enable numeric comparison of versions
    Design Decision: Support 'vX.Y.Z' and 'X.Y.Z' formats

    Args:
        version: Version string (e.g., 'v2.1.0' or '2.1.0')

    Returns:
        Tuple of (major, minor, patch) or None if invalid format

    CRITICAL: Returns None for invalid formats (caller must handle)
    """
    # Remove 'v' prefix if present
    version_clean = version.strip().lower()
    if version_clean.startswith('v'):
        version_clean = version_clean[1:]

    # Match X.Y.Z pattern
    pattern = r'^(\d+)\.(\d+)\.(\d+)$'
    match = re.match(pattern, version_clean)

    if not match:
        return None

    major, minor, patch = match.groups()
    return (int(major), int(minor), int(patch))


def compare_versions(current: str, required: str) -> Dict[str, Any]:
    """
    Compare two semantic versions and determine compatibility.

    What: Parse and compare version strings
    Why: Determine if current version is compatible with required version
    Design Decision: MAJOR diff blocks, MINOR diff warns, PATCH diff OK

    Compatibility rules:
    - Same MAJOR, same MINOR, any PATCH → OK
    - Same MAJOR, different MINOR → WARN (backward compatible)
    - Different MAJOR → ERROR (breaking change)
    - "none" value → Skip check (OK)

    Args:
        current: Current version string
        required: Required version string

    Returns:
        Dict with keys:
        - compatible: bool (True if OK or WARN, False if ERROR)
        - status: str ('OK', 'WARN', 'ERROR')
        - reason: str (explanation)
        - current: str (original current version)
        - required: str (original required version)

    CRITICAL: Invalid version formats return ERROR status
    """
    # Special case: "none" means no version control → skip check
    if current.lower() == "none" and required.lower() == "none":
        return {
            "compatible": True,
            "status": "OK",
            "reason": "Version not applicable (both 'none')",
            "current": current,
            "required": required
        }

    current_parsed = parse_semver(current)
    required_parsed = parse_semver(required)

    # Handle parse failures
    if current_parsed is None:
        return {
            "compatible": False,
            "status": "ERROR",
            "reason": f"Invalid current version format: {current}",
            "current": current,
            "required": required
        }

    if required_parsed is None:
        return {
            "compatible": False,
            "status": "ERROR",
            "reason": f"Invalid required version format: {required}",
            "current": current,
            "required": required
        }

    curr_major, curr_minor, curr_patch = current_parsed
    req_major, req_minor, req_patch = required_parsed

    # MAJOR version difference → ERROR
    if curr_major != req_major:
        return {
            "compatible": False,
            "status": "ERROR",
            "reason": f"MAJOR version mismatch (breaking change): current={current}, required={required}",
            "current": current,
            "required": required
        }

    # Same MAJOR, different MINOR → WARN
    if curr_minor != req_minor:
        return {
            "compatible": True,
            "status": "WARN",
            "reason": f"MINOR version difference (backward compatible): current={current}, required={required}",
            "current": current,
            "required": required
        }

    # Same MAJOR, same MINOR (any PATCH) → OK
    return {
        "compatible": True,
        "status": "OK",
        "reason": f"Versions compatible: current={current}, required={required}",
        "current": current,
        "required": required
    }


def check_compat(current: Dict[str, str], required: Dict[str, str]) -> Dict[str, Any]:
    """
    Check compatibility between current and required version sets.

    What: Compare multiple version fields and aggregate results
    Why: Ensure all version fields are compatible before execution
    Design Decision: Worst status wins (ERROR > WARN > OK)

    Args:
        current: Dict with version fields (rules_version, normalization_version, etc.)
        required: Dict with required version fields

    Returns:
        Dict with keys:
        - status: str ('OK', 'WARN', 'ERROR')
        - reason: str (explanation)
        - details: Dict[field_name, comparison_result]

    CRITICAL: Missing required fields return ERROR status
    """
    details = {}
    statuses = []

    # Check each required field
    for field, required_version in required.items():
        current_version = current.get(field)

        # Missing field → ERROR
        if current_version is None:
            details[field] = {
                "compatible": False,
                "status": "ERROR",
                "reason": f"Missing required field: {field}",
                "current": None,
                "required": required_version
            }
            statuses.append("ERROR")
            continue

        # Compare versions
        comparison = compare_versions(current_version, required_version)
        details[field] = comparison
        statuses.append(comparison["status"])

    # Determine overall status (worst wins)
    if "ERROR" in statuses:
        overall_status = "ERROR"
        # Build specific reason mentioning MAJOR version issues or missing fields
        error_fields = [field for field, detail in details.items() if detail["status"] == "ERROR"]
        error_reasons = [details[field]["reason"] for field in error_fields]
        overall_reason = "; ".join(error_reasons)
    elif "WARN" in statuses:
        overall_status = "WARN"
        overall_reason = "MINOR version differences detected (backward compatible)"
    else:
        overall_status = "OK"
        overall_reason = "All version fields are compatible"

    result = {
        "status": overall_status,
        "reason": overall_reason,
        "details": details
    }

    # Structured logging
    logger.info(
        "Compatibility check completed",
        extra={
            "compat_status": overall_status,
            "current_versions": current,
            "required_versions": required,
            "details": details
        }
    )

    return result
