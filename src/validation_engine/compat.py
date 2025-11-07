"""
Purpose: SemVer compatibility checking between evaluation artifacts
Responsibility: Provide utilities to compare version metadata (rules, thresholds, normalization)
Dependencies: typing
Created: 2025-11-03 by Codex
Decision Log: Task B - ValidationEngine 中間層化

CRITICAL: Only parse SemVer strings matching MAJOR.MINOR.PATCH (numeric segments)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

_SEMVER_PATTERN = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "SemVer":
        match = _SEMVER_PATTERN.match(value)
        if not match:
            raise ValueError(f"Invalid SemVer value: '{value}'")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
        )


class CompatibilityStatus:
    OK = "OK"
    WARN = "WARN"
    ERROR = "ERROR"


def compare_versions(current: str, expected: str) -> str:
    """
    What: Compare two SemVer strings and return compatibility status.
    Why: ValidationEngine must flag MAJOR or MINOR gaps before evaluation.
    Design Decision: Reuse simple tuple comparison; MAJOR diff => ERROR, MINOR diff => WARN, PATCH diff => OK.

    Args:
        current: Version string reported by runtime artifact.
        expected: Version string from thresholds_v2 metadata.

    Returns:
        CompatibilityStatus.{OK,WARN,ERROR}
    """
    current_semver = SemVer.parse(current)
    expected_semver = SemVer.parse(expected)

    if current_semver.major != expected_semver.major:
        return CompatibilityStatus.ERROR
    if current_semver.minor != expected_semver.minor:
        return CompatibilityStatus.WARN
    return CompatibilityStatus.OK


def aggregate_status(statuses: Iterable[str]) -> str:
    """
    What: Aggregate multiple compatibility results into a single status.
    Why: validation_state derives severity from worst-case outcome.
    Design Decision: severity order ERROR > WARN > OK
    """
    has_warn = False
    for status in statuses:
        if status == CompatibilityStatus.ERROR:
            return CompatibilityStatus.ERROR
        if status == CompatibilityStatus.WARN:
            has_warn = True
    return CompatibilityStatus.WARN if has_warn else CompatibilityStatus.OK


def compare_version_map(current: Dict[str, str], expected: Dict[str, str]) -> Dict[str, str]:
    """
    What: Compare multiple versions (rules, thresholds, normalization) at once.
    Why: ValidationEngine must report each mismatch separately.
    """
    results: Dict[str, str] = {}
    for key in ("rules_version", "thresholds_version", "normalization_version"):
        current_value = current.get(key)
        expected_value = expected.get(key)
        if not current_value or not expected_value:
            # Missing data is treated as ERROR to force investigation
            results[key] = CompatibilityStatus.ERROR
            continue
        results[key] = compare_versions(current_value, expected_value)
    return results
