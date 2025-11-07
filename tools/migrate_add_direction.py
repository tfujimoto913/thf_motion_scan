#!/usr/bin/env python3
"""
Purpose: Migrate thresholds_v2.json to add direction field based on operator inference
Responsibility: Automate direction field addition with manual review for edge cases
Dependencies: json, pathlib, datetime
Created: 2025-11-04 by Claude Code
Decision Log: Stage 3 - PR#3 Migration script implementation

CRITICAL:
- Inference rules: lt/lte → lower, gt/gte → higher
- Special ops (eq, ne, range_*) require manual review
- Dry-run mode preserves original file
- Actual execution creates timestamped backup

Usage:
    # Preview migration (dry-run)
    python tools/migrate_add_direction.py --dry-run config/thresholds_v2.json

    # Execute migration (creates backup)
    python tools/migrate_add_direction.py config/thresholds_v2.json

    # Extract manual review cases to JSON
    python tools/migrate_add_direction.py --extract-manual-review config/thresholds_v2.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Operator to direction mapping
# CRITICAL: Only non-special operators have clear directional meaning
OP_TO_DIRECTION = {
    "lt": "lower",   # value < threshold → lower values pass
    "lte": "lower",  # value <= threshold → lower values pass
    "gt": "higher",  # value > threshold → higher values pass
    "gte": "higher", # value >= threshold → higher values pass
}

# Special operators that require manual review
SPECIAL_OPS = ["eq", "ne", "range_inc", "range_exc"]


def infer_direction(bands: list[dict[str, Any]]) -> tuple[str | None, str]:
    """
    What: Infer direction from band operators
    Why: Automate direction field addition where intent is clear
    Design Decision: Use first non-special operator, flag special ops for review

    Args:
        bands: List of band definitions with "op" field

    Returns:
        Tuple of (inferred_direction, reason)
        - direction: "lower" | "higher" | None (if manual review needed)
        - reason: Human-readable explanation

    CRITICAL:
    - Special ops (eq, ne, range_*) → None (manual review)
    - Empty bands → None (manual review)
    - Mixed non-special ops → use first occurrence

    Examples:
        >>> infer_direction([{"op": "lt", "name": "pass"}])
        ("lower", "Inferred from operator: lt")

        >>> infer_direction([{"op": "eq", "name": "pass"}])
        (None, "Manual review required: special operator 'eq' found")

        >>> infer_direction([{"op": "gte", "name": "pass"}, {"op": "lt", "name": "fail"}])
        ("higher", "Inferred from operator: gte")
    """
    if not bands:
        return None, "Manual review required: no bands defined"

    # Check for special operators first
    for band in bands:
        op = band.get("op")
        if op in SPECIAL_OPS:
            return None, f"Manual review required: special operator '{op}' found"

    # Find first non-special operator
    for band in bands:
        op = band.get("op")
        if op in OP_TO_DIRECTION:
            direction = OP_TO_DIRECTION[op]
            return direction, f"Inferred from operator: {op}"

    # No recognizable operators
    return None, "Manual review required: no recognizable operators found"


def migrate_thresholds(
    thresholds_path: Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    What: Migrate thresholds_v2.json to add direction field
    Why: Enable direction-aware threshold evaluation
    Design Decision: Non-destructive (backup + dry-run), skip existing direction

    Args:
        thresholds_path: Path to thresholds_v2.json
        dry_run: If True, preview only (do not modify file)

    Returns:
        Migration report dict with keys:
        - dry_run: bool
        - backup_path: str (only if not dry_run)
        - migrated: list of migrated test info
        - skipped: list of skipped test info
        - manual_review: list of tests requiring manual review

    CRITICAL:
    - Dry-run does NOT modify file
    - Actual execution creates timestamped backup
    - Tests with existing direction field are skipped
    - Special operators trigger manual review flag

    Examples:
        >>> result = migrate_thresholds(Path("config.json"), dry_run=True)
        >>> result["dry_run"]
        True
        >>> result["migrated"][0]["code"]
        "test_lower"
    """
    if not thresholds_path.exists():
        raise FileNotFoundError(f"Thresholds file not found: {thresholds_path}")

    # Load thresholds data
    data = json.loads(thresholds_path.read_text(encoding="utf-8"))

    # Migration report
    report = {
        "dry_run": dry_run,
        "migrated": [],
        "skipped": [],
        "manual_review": [],
    }

    # Process each test
    for test in data.get("tests", []):
        code = test["code"]

        # Skip if direction already exists
        if "direction" in test:
            report["skipped"].append({
                "code": code,
                "reason": "already has direction",
            })
            continue

        # Infer direction from bands
        bands = test.get("primary", {}).get("bands", [])
        direction, reason = infer_direction(bands)

        if direction is None:
            # Manual review required
            report["manual_review"].append({
                "code": code,
                "reason": reason,
                "bands": bands,
            })
        else:
            # Add direction field (in-memory only if dry_run)
            if not dry_run:
                test["direction"] = direction

            report["migrated"].append({
                "code": code,
                "inferred_direction": direction,
                "inference_reason": reason,
            })

    # Save changes (if not dry-run)
    if not dry_run:
        # Create backup with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = thresholds_path.with_suffix(f".backup_{timestamp}.json")
        backup_path.write_text(
            thresholds_path.read_text(encoding="utf-8"),
            encoding="utf-8"
        )
        report["backup_path"] = str(backup_path)

        # Write modified data
        thresholds_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    return report


def extract_manual_review_cases(thresholds_path: Path) -> list[dict[str, Any]]:
    """
    What: Extract tests requiring manual review for direction assignment
    Why: Support manual review workflow
    Design Decision: Return structured JSON for human processing

    Args:
        thresholds_path: Path to thresholds_v2.json

    Returns:
        List of test cases requiring manual review, each with:
        - code: test code
        - reason: why manual review is needed
        - bands: band configuration for context

    CRITICAL:
    - Only returns tests WITHOUT existing direction field
    - Includes all special operator cases (eq, ne, range_*)

    Examples:
        >>> cases = extract_manual_review_cases(Path("config.json"))
        >>> cases[0]["code"]
        "overall_score"
        >>> "range_inc" in cases[0]["reason"]
        True
    """
    if not thresholds_path.exists():
        raise FileNotFoundError(f"Thresholds file not found: {thresholds_path}")

    data = json.loads(thresholds_path.read_text(encoding="utf-8"))
    manual_cases = []

    for test in data.get("tests", []):
        code = test["code"]

        # Skip if direction already exists
        if "direction" in test:
            continue

        # Check if manual review needed
        bands = test.get("primary", {}).get("bands", [])
        direction, reason = infer_direction(bands)

        if direction is None:
            manual_cases.append({
                "code": code,
                "reason": reason,
                "bands": bands,
            })

    return manual_cases


def format_report(report: dict[str, Any]) -> str:
    """
    What: Format migration report for CLI output
    Why: Human-readable summary with actionable info

    Args:
        report: Migration report from migrate_thresholds()

    Returns:
        Formatted string for CLI output
    """
    lines = []

    # Header
    mode = "DRY-RUN" if report["dry_run"] else "ACTUAL MIGRATION"
    lines.append(f"{'=' * 60}")
    lines.append(f"Migration Report - {mode}")
    lines.append(f"{'=' * 60}\n")

    # Summary
    lines.append(f"✅ Migrated: {len(report['migrated'])} tests")
    lines.append(f"⏭  Skipped: {len(report['skipped'])} tests")
    lines.append(f"⚠️  Manual Review: {len(report['manual_review'])} tests\n")

    # Migrated tests
    if report["migrated"]:
        lines.append("Migrated tests:")
        for item in report["migrated"]:
            lines.append(
                f"  - {item['code']}: direction={item['inferred_direction']} "
                f"({item['inference_reason']})"
            )
        lines.append("")

    # Skipped tests
    if report["skipped"]:
        lines.append("Skipped tests:")
        for item in report["skipped"]:
            lines.append(f"  - {item['code']}: {item['reason']}")
        lines.append("")

    # Manual review cases
    if report["manual_review"]:
        lines.append("⚠️  Manual review required:")
        for item in report["manual_review"]:
            lines.append(f"  - {item['code']}: {item['reason']}")
        lines.append("")

    # Backup info
    if not report["dry_run"] and "backup_path" in report:
        lines.append(f"💾 Backup created: {report['backup_path']}")

    return "\n".join(lines)


def main() -> int:
    """
    What: CLI entry point for migration script
    Why: Support dry-run, actual migration, and manual review extraction

    Returns:
        Exit code (0 = success, 1 = error)
    """
    parser = argparse.ArgumentParser(
        description="Migrate thresholds_v2.json to add direction field",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview migration
  python tools/migrate_add_direction.py --dry-run config/thresholds_v2.json

  # Execute migration (creates backup)
  python tools/migrate_add_direction.py config/thresholds_v2.json

  # Extract manual review cases
  python tools/migrate_add_direction.py --extract-manual-review config/thresholds_v2.json
        """,
    )

    parser.add_argument(
        "thresholds_path",
        type=Path,
        help="Path to thresholds_v2.json",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migration without modifying file",
    )

    parser.add_argument(
        "--extract-manual-review",
        action="store_true",
        help="Extract tests requiring manual review (JSON output)",
    )

    args = parser.parse_args()

    try:
        if args.extract_manual_review:
            # Extract and print manual review cases as JSON
            cases = extract_manual_review_cases(args.thresholds_path)
            print(json.dumps(cases, indent=2, ensure_ascii=False))
            return 0

        # Execute migration
        report = migrate_thresholds(args.thresholds_path, dry_run=args.dry_run)

        # Print formatted report
        print(format_report(report))

        # Exit with error if manual review cases exist
        if report["manual_review"]:
            print("\n⚠️  Manual review required for some tests.")
            print("Use --extract-manual-review to see details.")
            return 1

        return 0

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
