#!/usr/bin/env python3
"""
Purpose: Test migration script for adding direction field to thresholds_v2.json
Responsibility: Verify op-to-direction inference logic and exception handling
Dependencies: pytest, json, pathlib
Created: 2025-11-04 by Claude Code
Decision Log: Stage 3 - PR#3 Migration script testing

CRITICAL:
- Tests written BEFORE implementation (TDD)
- Verify inference: lt/lte → lower, gt/gte → higher
- Verify exceptions: eq/ne/range → manual review
- Verify dry-run mode preserves original file
- Verify backup creation on actual execution
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Add tools directory to path for importing migrate_add_direction
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from migrate_add_direction import (
    OP_TO_DIRECTION,
    extract_manual_review_cases,
    infer_direction,
    migrate_thresholds,
)


def test_op_to_direction_mapping():
    """Verify OP_TO_DIRECTION mapping is correct"""
    assert OP_TO_DIRECTION == {
        "lt": "lower",
        "lte": "lower",
        "gt": "higher",
        "gte": "higher",
    }


def test_infer_direction_lower_from_lt():
    """Verify direction inference from lt operator"""
    bands = [
        {"name": "pass", "op": "lt", "value": 10},
        {"name": "fail", "op": "gte", "value": 10},
    ]
    direction, reason = infer_direction(bands)
    assert direction == "lower"
    assert "lt" in reason


def test_infer_direction_lower_from_lte():
    """Verify direction inference from lte operator"""
    bands = [
        {"name": "pass", "op": "lte", "value": 10},
        {"name": "fail", "op": "gt", "value": 10},
    ]
    direction, reason = infer_direction(bands)
    assert direction == "lower"
    assert "lte" in reason


def test_infer_direction_higher_from_gt():
    """Verify direction inference from gt operator"""
    bands = [
        {"name": "pass", "op": "gt", "value": 60},
        {"name": "fail", "op": "lte", "value": 60},
    ]
    direction, reason = infer_direction(bands)
    assert direction == "higher"
    assert "gt" in reason


def test_infer_direction_higher_from_gte():
    """Verify direction inference from gte operator"""
    bands = [
        {"name": "pass", "op": "gte", "value": 60},
        {"name": "fail", "op": "lt", "value": 60},
    ]
    direction, reason = infer_direction(bands)
    assert direction == "higher"
    assert "gte" in reason


def test_infer_direction_eq_requires_manual_review():
    """Verify eq operator triggers manual review"""
    bands = [
        {"name": "pass", "op": "eq", "value": 0},
        {"name": "fail", "op": "ne", "value": 0},
    ]
    direction, reason = infer_direction(bands)
    assert direction is None
    assert "manual review" in reason.lower()
    assert "eq" in reason


def test_infer_direction_ne_requires_manual_review():
    """Verify ne operator triggers manual review"""
    bands = [
        {"name": "pass", "op": "ne", "value": 999},
        {"name": "fail", "op": "eq", "value": 999},
    ]
    direction, reason = infer_direction(bands)
    assert direction is None
    assert "manual review" in reason.lower()
    assert "ne" in reason


def test_infer_direction_range_requires_manual_review():
    """Verify range operators trigger manual review"""
    bands = [
        {"name": "pass", "op": "gte", "value": 60},
        {"name": "border", "op": "range_inc", "value": [40, 60]},
        {"name": "fail", "op": "lt", "value": 40},
    ]
    direction, reason = infer_direction(bands)
    assert direction is None
    assert "manual review" in reason.lower()
    assert "range_inc" in reason


def test_infer_direction_mixed_non_special_ops():
    """Verify mixed non-special ops use first occurrence"""
    bands = [
        {"name": "pass", "op": "lt", "value": 10},
        {"name": "warn", "op": "gte", "value": 10},  # Opposite op (fail band)
    ]
    direction, reason = infer_direction(bands)
    # Should infer from first non-special op
    assert direction == "lower"
    assert "lt" in reason


def test_migrate_thresholds_dry_run_preserves_file(tmp_path):
    """Verify dry-run mode does NOT modify the original file"""
    original = {
        "versions": {"rules_version": "2.1.0"},
        "tests": [
            {
                "code": "test1",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "lt", "value": 10},
                    ]
                },
            }
        ],
    }

    thresholds_path = tmp_path / "thresholds.json"
    thresholds_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

    # Execute dry-run
    result = migrate_thresholds(thresholds_path, dry_run=True)

    # Verify file is unchanged
    unchanged = json.loads(thresholds_path.read_text(encoding="utf-8"))
    assert unchanged == original

    # Verify result contains migration plan
    assert result["dry_run"] is True
    assert len(result["migrated"]) == 1
    assert result["migrated"][0]["code"] == "test1"
    assert result["migrated"][0]["inferred_direction"] == "lower"


def test_migrate_thresholds_actual_adds_direction(tmp_path):
    """Verify actual migration adds direction field"""
    original = {
        "versions": {"rules_version": "2.1.0"},
        "tests": [
            {
                "code": "test_lower",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "lt", "value": 10},
                    ]
                },
            },
            {
                "code": "test_higher",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "gte", "value": 60},
                    ]
                },
            },
        ],
    }

    thresholds_path = tmp_path / "thresholds.json"
    thresholds_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

    # Execute migration
    result = migrate_thresholds(thresholds_path, dry_run=False)

    # Verify file is modified
    migrated = json.loads(thresholds_path.read_text(encoding="utf-8"))
    assert migrated["tests"][0]["direction"] == "lower"
    assert migrated["tests"][1]["direction"] == "higher"

    # Verify result
    assert result["dry_run"] is False
    assert len(result["migrated"]) == 2
    assert result["migrated"][0]["inferred_direction"] == "lower"
    assert result["migrated"][1]["inferred_direction"] == "higher"


def test_migrate_thresholds_creates_backup(tmp_path):
    """Verify migration creates backup file"""
    original = {
        "versions": {"rules_version": "2.1.0"},
        "tests": [
            {
                "code": "test1",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "lt", "value": 10},
                    ]
                },
            }
        ],
    }

    thresholds_path = tmp_path / "thresholds.json"
    thresholds_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

    # Execute migration
    result = migrate_thresholds(thresholds_path, dry_run=False)

    # Verify backup exists
    backup_path = Path(result["backup_path"])
    assert backup_path.exists()

    # Verify backup content is identical to original
    backup_content = json.loads(backup_path.read_text(encoding="utf-8"))
    assert backup_content == original


def test_migrate_thresholds_skips_tests_with_existing_direction(tmp_path):
    """Verify tests with existing direction field are skipped"""
    original = {
        "versions": {"rules_version": "2.1.0"},
        "tests": [
            {
                "code": "test_already_has_direction",
                "direction": "lower",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "lt", "value": 10},
                    ]
                },
            },
            {
                "code": "test_needs_direction",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "gte", "value": 60},
                    ]
                },
            },
        ],
    }

    thresholds_path = tmp_path / "thresholds.json"
    thresholds_path.write_text(json.dumps(original, indent=2), encoding="utf-8")

    # Execute migration
    result = migrate_thresholds(thresholds_path, dry_run=False)

    # Verify only 1 test was migrated
    assert len(result["migrated"]) == 1
    assert result["migrated"][0]["code"] == "test_needs_direction"

    # Verify 1 test was skipped
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["code"] == "test_already_has_direction"
    assert result["skipped"][0]["reason"] == "already has direction"


def test_extract_manual_review_cases_identifies_special_ops(tmp_path):
    """Verify manual review extraction identifies special operators"""
    data = {
        "versions": {"rules_version": "2.1.0"},
        "tests": [
            {
                "code": "test_eq",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "eq", "value": 0},
                    ]
                },
            },
            {
                "code": "test_range",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "gte", "value": 60},
                        {"name": "border", "op": "range_inc", "value": [40, 60]},
                    ]
                },
            },
            {
                "code": "test_auto_lower",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "lt", "value": 10},
                    ]
                },
            },
        ],
    }

    thresholds_path = tmp_path / "thresholds.json"
    thresholds_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Extract manual review cases
    manual_cases = extract_manual_review_cases(thresholds_path)

    # Verify 2 cases require manual review
    assert len(manual_cases) == 2
    assert manual_cases[0]["code"] == "test_eq"
    assert "eq" in manual_cases[0]["reason"]
    assert manual_cases[1]["code"] == "test_range"
    assert "range_inc" in manual_cases[1]["reason"]


def test_infer_direction_empty_bands():
    """Verify empty bands list requires manual review"""
    bands = []
    direction, reason = infer_direction(bands)
    assert direction is None
    assert "manual review" in reason.lower()
    assert "no bands" in reason.lower()
