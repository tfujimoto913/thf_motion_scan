"""
Purpose: Apply thresholds_v2 validation rules to rep and session artifacts
Responsibility: Produce validation_state with compatibility/metric violations
Dependencies: json, typing, compat utilities
Created: 2025-11-03 by Codex
Decision Log: Task B - ValidationEngine 中間層化

CRITICAL:
- validation_state.state must use OK/WARN/ERROR (CompatibilityStatus)
- Callers provide metrics aggregated outside this module
- Violations array remains descriptive (code, message, severity)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .compat import CompatibilityStatus, aggregate_status, compare_version_map


@dataclass
class ValidationResult:
    state: str
    violations: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {"validation": {"state": self.state, "violations": self.violations}}


def _load_thresholds_v2(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"thresholds_v2 file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _build_threshold_index(thresholds: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for entry in thresholds.get("tests", []):
        code = entry["code"]
        index[code] = entry
    return index


def _compare_metrics(
    code: str,
    metric_name: str,
    metric_value: Any,
    bands: Iterable[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    What: Evaluate metric against ordered bands
    Why: Determine best-fit classification; return violation if not pass/border
    """
    # materialize to list in case caller passes generator
    band_list = list(bands)
    for band in band_list:
        op = band["op"]
        value = band["value"]
        name = band["name"]

        if op == "lt" and metric_value < value:
            return None if name == "pass" else {
                "test_code": code,
                "metric": metric_name,
                "band": name,
                "severity": name,
                "op": op,
                "threshold": value,
                "actual": metric_value,
            }
        if op == "lte" and metric_value <= value:
            return None if name == "pass" else {
                "test_code": code,
                "metric": metric_name,
                "band": name,
                "severity": name,
                "op": op,
                "threshold": value,
                "actual": metric_value,
            }
        if op == "gt" and metric_value > value:
            return None if name == "pass" else {
                "test_code": code,
                "metric": metric_name,
                "band": name,
                "severity": name,
                "op": op,
                "threshold": value,
                "actual": metric_value,
            }
        if op == "gte" and metric_value >= value:
            return None if name == "pass" else {
                "test_code": code,
                "metric": metric_name,
                "band": name,
                "severity": name,
                "op": op,
                "threshold": value,
                "actual": metric_value,
            }
        if op == "eq" and metric_value == value:
            return None if name == "pass" else {
                "test_code": code,
                "metric": metric_name,
                "band": name,
                "severity": name,
                "op": op,
                "threshold": value,
                "actual": metric_value,
            }
        if op == "range_inc" and value[0] <= metric_value <= value[1]:
            return None if name == "pass" else {
                "test_code": code,
                "metric": metric_name,
                "band": name,
                "severity": name,
                "op": op,
                "threshold": value,
                "actual": metric_value,
            }
        if op == "range_exc" and value[0] < metric_value < value[1]:
            return None if name == "pass" else {
                "test_code": code,
                "metric": metric_name,
                "band": name,
                "severity": name,
                "op": op,
                "threshold": value,
                "actual": metric_value,
            }

    # If no "pass/border" matched, mark highest severity (last band)
    last_band = band_list[-1]
    return {
        "test_code": code,
        "metric": metric_name,
        "band": last_band["name"],
        "severity": last_band["name"],
        "op": last_band["op"],
        "threshold": last_band["value"],
        "actual": metric_value,
    }


def _evaluate_metrics(
    rep_metrics: Dict[str, Any],
    threshold_index: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    violations: List[Dict[str, Any]] = []
    for code, metric_value in rep_metrics.items():
        thresholds_entry = threshold_index.get(code)
        if not thresholds_entry:
            continue  # Unknown metric; treat as informational
        primary_bands = thresholds_entry["primary"]["bands"]
        metric_name = thresholds_entry.get("metric", code)
        result = _compare_metrics(code, metric_name, metric_value, primary_bands)
        if result:
            violations.append(result)
    return violations


def _validation_state_from_versions(
    current_versions: Dict[str, str],
    threshold_versions: Dict[str, str],
) -> Tuple[str, List[Dict[str, str]]]:
    comparison = compare_version_map(current_versions, threshold_versions)
    status = aggregate_status(comparison.values())
    if status == CompatibilityStatus.OK:
        return status, []

    violations = [
        {
            "category": "compatibility",
            "field": key,
            "status": comparison[key],
            "current": current_versions.get(key),
            "expected": threshold_versions.get(key),
        }
        for key in sorted(comparison)
        if comparison[key] != CompatibilityStatus.OK
    ]
    return status, violations


def apply_rep(
    rep_metrics: Dict[str, Any],
    rep_metadata: Dict[str, str],
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """
    What: Compute validation state for a single rep evaluation.
    Why: Provide consistent validation vocabulary for downstream systems.
    """
    threshold_versions = thresholds["versions"]
    current_versions = {
        "rules_version": rep_metadata.get("rules_version", ""),
        "thresholds_version": rep_metadata.get("thresholds_version", ""),
        "normalization_version": rep_metadata.get("normalization_version", ""),
    }

    status, violations = _validation_state_from_versions(current_versions, threshold_versions)

    metric_violations = _evaluate_metrics(rep_metrics, _build_threshold_index(thresholds))
    if metric_violations:
        metric_statuses: List[str] = [
            CompatibilityStatus.ERROR if violation.get("band") == "fail" else CompatibilityStatus.WARN
            for violation in metric_violations
        ]
        status = aggregate_status([status] + metric_statuses)
        violations.extend(metric_violations)

    return ValidationResult(state=status, violations=violations).to_dict()


def apply_session(
    session_metrics: Dict[str, Any],
    session_metadata: Dict[str, str],
    thresholds: Dict[str, Any],
) -> Dict[str, Any]:
    """
    What: Compute validation state for session-level aggregates (e.g., best-of-three reps).
    """
    return apply_rep(session_metrics, session_metadata, thresholds)
