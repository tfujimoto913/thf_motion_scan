#!/usr/bin/env python3
"""
Diff thresholds.json between two versions and classify changes by SemVer severity.

Purpose: Compare thresholds.json versions and output change summary
Responsibility: Detect added/changed/deleted thresholds, classify by MAJOR/MINOR/PATCH
Created: 2025-11-02
Decision Log: ADR-028 (thresholds.json v1.0.0 export)

Usage:
    python scripts/diff-thresholds.py old.json new.json
    python scripts/diff-thresholds.py --format=table old.json new.json

SemVer Classification Rules:
    - MAJOR: Band deleted, op changed, value range narrowed (breaking change)
    - MINOR: Band added, value range expanded (backward compatible)
    - PATCH: Only metadata (notes, refs) changed (non-breaking)
"""

import argparse
import json
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Tuple


class Severity(Enum):
    """Change severity classification (SemVer-based)."""
    MAJOR = "MAJOR"  # Breaking change
    MINOR = "MINOR"  # Backward compatible addition
    PATCH = "PATCH"  # Non-breaking fix/metadata
    NONE = "NONE"    # No change


class Change:
    """Represents a single change between old and new versions."""

    def __init__(self, test_code: str, severity: Severity, description: str):
        self.test_code = test_code
        self.severity = severity
        self.description = description

    def __repr__(self):
        return f"[{self.severity.value}] {self.test_code}: {self.description}"


def load_json(file_path: Path) -> Dict[str, Any]:
    """Load JSON file with error handling."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def compare_bands(old_bands: List[Dict], new_bands: List[Dict]) -> Tuple[Severity, List[str]]:
    """
    Compare two band lists and determine severity.

    What: Detect band additions, deletions, modifications
    Why: Classify impact on threshold evaluation behavior
    Design Decision: Conservative classification (any structural change = MAJOR)

    Returns: (max_severity, list_of_changes)
    """
    changes = []
    max_severity = Severity.NONE

    old_band_set = {json.dumps(b, sort_keys=True) for b in old_bands}
    new_band_set = {json.dumps(b, sort_keys=True) for b in new_bands}

    # Bands deleted (MAJOR)
    deleted = old_band_set - new_band_set
    if deleted:
        max_severity = Severity.MAJOR
        for band_json in deleted:
            band = json.loads(band_json)
            changes.append(f"Band deleted: {band.get('name')} (op={band.get('op')}, value={band.get('value')})")

    # Bands added (MINOR)
    added = new_band_set - old_band_set
    if added:
        if max_severity == Severity.NONE:
            max_severity = Severity.MINOR
        for band_json in added:
            band = json.loads(band_json)
            changes.append(f"Band added: {band.get('name')} (op={band.get('op')}, value={band.get('value')})")

    # Check for band modifications (comparing by index)
    for i, (old_band, new_band) in enumerate(zip(old_bands, new_bands)):
        if old_band != new_band:
            # op or value changed (MAJOR)
            if old_band.get('op') != new_band.get('op') or old_band.get('value') != new_band.get('value'):
                max_severity = Severity.MAJOR
                changes.append(
                    f"Band[{i}] modified: op={old_band.get('op')}→{new_band.get('op')}, "
                    f"value={old_band.get('value')}→{new_band.get('value')}"
                )
            # name changed only (MINOR)
            elif old_band.get('name') != new_band.get('name'):
                if max_severity == Severity.NONE:
                    max_severity = Severity.MINOR
                changes.append(f"Band[{i}] name changed: {old_band.get('name')}→{new_band.get('name')}")

    return max_severity, changes


def compare_test(old_test: Dict, new_test: Dict, test_code: str) -> List[Change]:
    """
    Compare a single test configuration between old and new versions.

    What: Detect changes in thresholds, features, refs, notes
    Why: Generate detailed change list for review

    Returns: List of Change objects
    """
    changes = []

    # Compare bands (primary thresholds)
    old_bands = old_test.get("thresholds", {}).get("primary", {}).get("bands", [])
    new_bands = new_test.get("thresholds", {}).get("primary", {}).get("bands", [])

    band_severity, band_changes = compare_bands(old_bands, new_bands)
    if band_severity != Severity.NONE:
        for change_desc in band_changes:
            changes.append(Change(test_code, band_severity, change_desc))

    # Compare hysteresis
    old_hyst = old_test.get("thresholds", {}).get("hysteresis")
    new_hyst = new_test.get("thresholds", {}).get("hysteresis")
    if old_hyst != new_hyst:
        severity = Severity.MAJOR if old_hyst is not None and new_hyst is None else Severity.MINOR
        changes.append(Change(test_code, severity, f"Hysteresis changed: {old_hyst}→{new_hyst}"))

    # Compare metadata (features, refs, notes) - PATCH level
    old_features = old_test.get("features", [])
    new_features = new_test.get("features", [])
    if old_features != new_features:
        changes.append(Change(test_code, Severity.PATCH, f"Features changed: {old_features}→{new_features}"))

    old_refs = old_test.get("refs", [])
    new_refs = new_test.get("refs", [])
    if old_refs != new_refs:
        changes.append(Change(test_code, Severity.PATCH, f"Refs changed: {old_refs}→{new_refs}"))

    old_notes = old_test.get("notes", "")
    new_notes = new_test.get("notes", "")
    if old_notes != new_notes:
        changes.append(Change(test_code, Severity.PATCH, f"Notes changed"))

    return changes


def diff_thresholds(old_path: Path, new_path: Path) -> List[Change]:
    """
    Compare two thresholds.json files and generate change list.

    What: Orchestrate diff logic for all tests
    Why: Single entry point for diff operation

    Returns: List of Change objects
    """
    old_data = load_json(old_path)
    new_data = load_json(new_path)

    changes = []

    old_tests = old_data.get("tests", {})
    new_tests = new_data.get("tests", {})

    all_test_codes = set(old_tests.keys()) | set(new_tests.keys())

    for test_code in sorted(all_test_codes):
        if test_code in old_tests and test_code not in new_tests:
            # Test deleted (MAJOR)
            changes.append(Change(test_code, Severity.MAJOR, "Test deleted"))
        elif test_code not in old_tests and test_code in new_tests:
            # Test added (MINOR)
            changes.append(Change(test_code, Severity.MINOR, "Test added"))
        else:
            # Test exists in both - compare details
            test_changes = compare_test(old_tests[test_code], new_tests[test_code], test_code)
            changes.extend(test_changes)

    # Compare versions
    old_version = old_data.get("versions", {}).get("rules_version", "unknown")
    new_version = new_data.get("versions", {}).get("rules_version", "unknown")
    if old_version != new_version:
        changes.append(Change("__meta__", Severity.PATCH, f"rules_version: {old_version}→{new_version}"))

    return changes


def format_output(changes: List[Change], format: str = "list") -> str:
    """
    Format changes for output.

    What: Convert changes to human-readable format
    Why: Support multiple output formats (list, table)

    Returns: Formatted string
    """
    if not changes:
        return "No changes detected."

    if format == "table":
        # Table format
        lines = []
        lines.append("| Severity | Test Code | Description |")
        lines.append("|----------|-----------|-------------|")
        for change in changes:
            lines.append(f"| {change.severity.value} | {change.test_code} | {change.description} |")
        return "\n".join(lines)
    else:
        # List format (default)
        lines = []
        for severity in [Severity.MAJOR, Severity.MINOR, Severity.PATCH]:
            severity_changes = [c for c in changes if c.severity == severity]
            if severity_changes:
                lines.append(f"\n{severity.value} changes:")
                for change in severity_changes:
                    lines.append(f"  [{change.test_code}] {change.description}")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Diff thresholds.json between versions")
    parser.add_argument("old", type=Path, help="Path to old thresholds.json")
    parser.add_argument("new", type=Path, help="Path to new thresholds.json")
    parser.add_argument(
        "--format",
        choices=["list", "table"],
        default="list",
        help="Output format (default: list)"
    )

    args = parser.parse_args()

    print(f"Comparing:")
    print(f"  Old: {args.old}")
    print(f"  New: {args.new}")
    print("-" * 60)

    changes = diff_thresholds(args.old, args.new)

    print(format_output(changes, args.format))

    # Exit with code based on max severity
    max_severity = max((c.severity for c in changes), default=Severity.NONE)
    if max_severity == Severity.MAJOR:
        print("\n⚠️  WARNING: MAJOR changes detected (breaking compatibility)")
        sys.exit(2)
    elif max_severity == Severity.MINOR:
        print("\nℹ️  INFO: MINOR changes detected (backward compatible)")
        sys.exit(0)
    else:
        print("\n✅ PATCH or no changes")
        sys.exit(0)


if __name__ == "__main__":
    main()
