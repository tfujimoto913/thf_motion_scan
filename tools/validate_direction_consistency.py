#!/usr/bin/env python3
"""
Purpose: Validate direction and op consistency in thresholds_v2.json
Responsibility: Detect configuration errors (direction vs op mismatch)
Dependencies: json, pathlib
Created: 2025-11-04 by Claude Code
Decision Log: Stage 3 - Direction integrity validation

CRITICAL:
- direction="lower" should use lt/lte ops (lower values are better)
- direction="higher" should use gt/gte ops (higher values are better)
- Special ops (eq, ne, range_*) are skipped from validation

Usage:
    python tools/validate_direction_consistency.py config/thresholds_v2.json

    Exit codes:
    0: All OK
    1: Inconsistencies found
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Expected operators for each direction
EXPECTED_OPS = {
    "lower": ["lt", "lte"],      # Lower is better: value < threshold
    "higher": ["gt", "gte"],     # Higher is better: value > threshold
}

# Special operators that are direction-agnostic
SPECIAL_OPS = ["eq", "ne", "range_inc", "range_exc"]


def validate_consistency(thresholds_path: Path) -> dict[str, Any]:
    """
    What: Validate direction-op consistency in thresholds_v2.json
    Why: Detect configuration errors that could cause incorrect evaluation
    Design Decision: Fail-fast on inconsistencies, skip special ops

    Args:
        thresholds_path: Path to thresholds_v2.json

    Returns:
        Dict with keys:
        - ok: List of test codes that passed validation
        - inconsistent: List of dicts with inconsistency details
        - skipped: List of test codes without direction

    Examples:
        >>> results = validate_consistency(Path("config/thresholds_v2.json"))
        >>> results["ok"]
        ['T01_B1', 'T02_B2']
        >>> results["inconsistent"]
        [{"code": "T03", "direction": "lower", "op": "gte", "expected_ops": ["lt", "lte"]}]
    """
    if not thresholds_path.exists():
        raise FileNotFoundError(f"Thresholds file not found: {thresholds_path}")

    data = json.loads(thresholds_path.read_text(encoding="utf-8"))
    results = {"ok": [], "inconsistent": [], "skipped": []}

    for test in data.get("tests", []):
        code = test["code"]
        direction = test.get("direction")

        # Skip if no direction specified
        if not direction:
            results["skipped"].append(code)
            continue

        # Validate primary bands
        bands = test.get("primary", {}).get("bands", [])
        expected = EXPECTED_OPS.get(direction, [])

        # Collect all non-special ops used in this test
        used_ops = []
        for band in bands:
            op = band["op"]
            if op not in SPECIAL_OPS:
                used_ops.append(op)

        # Check if at least one band uses the expected direction
        has_expected_op = any(op in expected for op in used_ops)

        # Also check if all ops are opposite to expected (clear misconfiguration)
        opposite_ops = EXPECTED_OPS.get("higher" if direction == "lower" else "lower", [])
        all_opposite = all(op in opposite_ops for op in used_ops) if used_ops else False

        if all_opposite:
            # All ops are opposite to direction - clear inconsistency
            results["inconsistent"].append({
                "code": code,
                "direction": direction,
                "ops_used": used_ops,
                "expected_ops": expected,
                "reason": "All operators are opposite to direction",
            })
        elif not has_expected_op and used_ops:
            # No expected op found, but not all opposite either - potential issue
            results["inconsistent"].append({
                "code": code,
                "direction": direction,
                "ops_used": used_ops,
                "expected_ops": expected,
                "reason": "No operators match the expected direction",
            })
        else:
            results["ok"].append(code)

    return results


def format_results(results: dict[str, Any]) -> str:
    """
    What: Format validation results for CLI output
    Why: Human-readable summary with color coding

    Args:
        results: Validation results from validate_consistency()

    Returns:
        Formatted string for CLI output
    """
    lines = []

    # Summary
    lines.append(f"✅ OK: {len(results['ok'])} tests")
    lines.append(f"⏭  Skipped (no direction): {len(results['skipped'])} tests")
    lines.append(f"❌ Inconsistent: {len(results['inconsistent'])} tests")

    # Details for inconsistencies
    if results["inconsistent"]:
        lines.append("\n🚨 Inconsistencies found:")
        for item in results["inconsistent"]:
            lines.append(
                f"  - {item['code']}: direction={item['direction']}, "
                f"ops_used={item['ops_used']}, expected={item['expected_ops']}"
            )
            lines.append(f"    Reason: {item['reason']}")

    return "\n".join(lines)


def main() -> int:
    """
    What: CLI entry point for validation script
    Why: Allow execution from command line and CI

    Returns:
        Exit code (0 = success, 1 = inconsistencies found)
    """
    if len(sys.argv) < 2:
        print("Usage: python tools/validate_direction_consistency.py <thresholds_v2.json>")
        print("\nExample:")
        print("  python tools/validate_direction_consistency.py config/thresholds_v2.json")
        return 1

    thresholds_path = Path(sys.argv[1])

    try:
        results = validate_consistency(thresholds_path)
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return 1

    # Print results
    print(format_results(results))

    # Exit with error if inconsistencies found
    if results["inconsistent"]:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
