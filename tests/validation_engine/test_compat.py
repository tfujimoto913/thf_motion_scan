"""
Purpose: Test thresholds_v2 SemVer compatibility helpers
Responsibility: Ensure ValidationEngine compatibility checks follow severity rules
Dependencies: src.validation_engine.compat
Created: 2025-11-03 by Codex
Decision Log: Task B - ValidationEngine 中間層化

CRITICAL: MAJOR diff => ERROR, MINOR diff => WARN, PATCH diff => OK
"""

import pytest

from src.validation_engine.compat import (
    CompatibilityStatus,
    aggregate_status,
    compare_version_map,
    compare_versions,
)


class TestCompareVersions:
    def test_identical_versions(self):
        assert compare_versions("1.2.3", "1.2.3") == CompatibilityStatus.OK

    def test_patch_difference_ok(self):
        assert compare_versions("1.2.5", "1.2.3") == CompatibilityStatus.OK

    def test_minor_difference_warn(self):
        assert compare_versions("1.3.0", "1.2.5") == CompatibilityStatus.WARN

    def test_major_difference_error(self):
        assert compare_versions("2.0.0", "1.9.9") == CompatibilityStatus.ERROR

    def test_invalid_semver_raises(self):
        with pytest.raises(ValueError):
            compare_versions("v1.2.3", "1.2.3")


class TestAggregateStatus:
    def test_all_ok(self):
        assert aggregate_status([CompatibilityStatus.OK, CompatibilityStatus.OK]) == CompatibilityStatus.OK

    def test_warn_overrides_ok(self):
        assert aggregate_status([CompatibilityStatus.OK, CompatibilityStatus.WARN]) == CompatibilityStatus.WARN

    def test_error_overrides_all(self):
        assert aggregate_status(
            [CompatibilityStatus.WARN, CompatibilityStatus.ERROR, CompatibilityStatus.OK]
        ) == CompatibilityStatus.ERROR


class TestCompareVersionMap:
    def test_missing_fields_mark_error(self):
        result = compare_version_map({}, {"rules_version": "1.0.0", "thresholds_version": "2.0.0"})
        assert result["rules_version"] == CompatibilityStatus.ERROR

    def test_all_fields_eval(self):
        current = {
            "rules_version": "1.2.3",
            "thresholds_version": "2.0.1",
            "normalization_version": "1.0.0",
        }
        expected = {
            "rules_version": "1.2.4",        # PATCH diff
            "thresholds_version": "2.1.0",   # MINOR diff
            "normalization_version": "2.0.0" # MAJOR diff
        }
        result = compare_version_map(current, expected)
        assert result["rules_version"] == CompatibilityStatus.OK
        assert result["thresholds_version"] == CompatibilityStatus.WARN
        assert result["normalization_version"] == CompatibilityStatus.ERROR
