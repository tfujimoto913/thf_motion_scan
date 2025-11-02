"""
Purpose: Apply Phase 0-4 QC gates against evaluator outputs
Responsibility: Load qc_gate rules and evaluate repetition level gating
Dependencies: json, pathlib
Created: 2025-11-03 by Codex
Decision Log: Phase 0-4 適用ルール運用開始

CRITICAL:
- Rules are optional per test_type; absence must not block pipeline
- Missing metric values are treated as violations (appears in log)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class QCGate:
    """Evaluate evaluator output against QC gate rules."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._rules: Dict[str, List[Dict[str, Any]]] = {}
        if not config_path:
            return

        config_path = Path(config_path)
        if not config_path.exists():
            return

        with config_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        for test_type, payload in raw.items():
            rules = payload.get("rules", [])
            if isinstance(rules, list):
                self._rules[test_type] = rules

    def evaluate(self, test_type: str, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """Return QC gate result for a given evaluation output."""

        rules = self._rules.get(test_type, [])
        violations: List[Dict[str, Any]] = []
        for rule in rules:
            path = rule.get("path")
            operator = rule.get("operator", "gte")
            threshold = rule.get("value")
            severity = rule.get("severity", "WARN")
            message = rule.get("message")
            rule_id = rule.get("id")

            value = _resolve_path(evaluation, path) if path else None
            passed = _compare(value, threshold, operator)
            if not passed:
                violations.append(
                    {
                        "id": rule_id,
                        "path": path,
                        "operator": operator,
                        "expected": threshold,
                        "observed": value,
                        "severity": severity,
                        "message": message,
                    }
                )

        return {"passed": not violations, "violations": violations}


def _resolve_path(payload: Dict[str, Any], path: Optional[str]) -> Any:
    if not path:
        return None
    current: Any = payload
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _compare(value: Any, threshold: Any, operator: str) -> bool:
    if value is None or threshold is None:
        return False

    try:
        if operator == "gte":
            return value >= threshold
        if operator == "lte":
            return value <= threshold
        if operator == "gt":
            return value > threshold
        if operator == "lt":
            return value < threshold
        if operator == "eq":
            return value == threshold
    except TypeError:
        return False

    # Unknown operator defaults to failure to surface misconfiguration.
    return False
