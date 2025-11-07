"""
Purpose: Test direction field (lower/higher) in thresholds_v2
Responsibility: Ensure direction field is properly handled by ValidationEngine
Dependencies: src.validation_engine.apply, tools.build_thresholds
Created: 2025-11-04 by Claude Code
Decision Log: direction回帰フィクスチャ＋CI配線（higher_is_better）

CRITICAL:
- direction field is optional (backward compatibility)
- direction defaults to "higher" if not specified
- direction is added to violation metadata for transparency
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.validation_engine.apply import apply_rep
from tools.build_thresholds import convert_to_thresholds_v2, load_notion_templates


class TestDirectionField:
    """Test direction field in thresholds_v2."""

    def test_direction_lower_is_preserved(self):
        """
        What: Verify direction="lower" is preserved through build pipeline
        Why: Ensure lower-is-better metrics are correctly tagged
        """
        fixture_path = Path("tests/fixtures/thresholds_v2/notion_exports/direction_lower.json")
        notion_data = load_notion_templates(fixture_path)
        versions = {
            "rules_version": "0.2.0",
            "thresholds_version": "2.0.0",
            "normalization_version": "none",
            "artifact_sha": "test-sha",
        }

        thresholds = convert_to_thresholds_v2(notion_data["templates"], versions)

        # Verify direction is preserved
        assert thresholds["tests"][0]["direction"] == "lower"
        assert thresholds["tests"][0]["code"] == "T01_B1_pelvis_drop"

    def test_direction_higher_is_preserved(self):
        """
        What: Verify direction="higher" is preserved through build pipeline
        Why: Ensure higher-is-better metrics are correctly tagged
        """
        fixture_path = Path("tests/fixtures/thresholds_v2/notion_exports/direction_higher.json")
        notion_data = load_notion_templates(fixture_path)
        versions = {
            "rules_version": "0.2.0",
            "thresholds_version": "2.0.0",
            "normalization_version": "none",
            "artifact_sha": "test-sha",
        }

        thresholds = convert_to_thresholds_v2(notion_data["templates"], versions)

        # Verify direction is preserved
        assert thresholds["tests"][0]["direction"] == "higher"
        assert thresholds["tests"][0]["code"] == "T02_B2_stability_score"

    def test_direction_none_backward_compatibility(self):
        """
        What: Verify thresholds without direction field work (backward compatibility)
        Why: Existing templates must continue to function
        """
        fixture_path = Path("tests/fixtures/thresholds_v2/notion_exports/direction_none_backward_compat.json")
        notion_data = load_notion_templates(fixture_path)
        versions = {
            "rules_version": "0.2.0",
            "thresholds_version": "2.0.0",
            "normalization_version": "none",
            "artifact_sha": "test-sha",
        }

        thresholds = convert_to_thresholds_v2(notion_data["templates"], versions)

        # Verify direction is NOT present (backward compatibility)
        assert "direction" not in thresholds["tests"][0]
        assert thresholds["tests"][0]["code"] == "T03_legacy"

    def test_direction_invalid_value_raises_error(self):
        """
        What: Verify invalid direction value raises ValueError
        Why: Prevent invalid direction values from entering the system
        """
        fixture_path = Path("tests/fixtures/thresholds_v2/notion_exports/direction_invalid_value.json")
        notion_data = load_notion_templates(fixture_path)
        versions = {
            "rules_version": "0.2.0",
            "thresholds_version": "2.0.0",
            "normalization_version": "none",
            "artifact_sha": "test-sha",
        }

        with pytest.raises(ValueError, match="Invalid direction value"):
            convert_to_thresholds_v2(notion_data["templates"], versions)

    def test_direction_added_to_violation_metadata(self):
        """
        What: Verify direction is added to violation metadata
        Why: Transparency - violations should indicate direction for debugging
        """
        thresholds = {
            "versions": {
                "rules_version": "0.2.0",
                "thresholds_version": "2.0.0",
                "normalization_version": "1.0.0",
            },
            "tests": [
                {
                    "code": "T01_test",
                    "metric": "test_metric",
                    "unit": "unit",
                    "direction": "lower",
                    "primary": {
                        "bands": [
                            {"name": "pass", "op": "lt", "value": 5},
                            {"name": "fail", "op": "gte", "value": 5},
                        ]
                    },
                }
            ],
        }

        rep_metrics = {"T01_test": 10}  # Violates fail band
        rep_meta = {
            "rules_version": "0.2.0",
            "thresholds_version": "2.0.0",
            "normalization_version": "1.0.0",
        }

        result = apply_rep(rep_metrics, rep_meta, thresholds)

        # Verify direction is in violation metadata
        assert len(result["validation"]["violations"]) == 1
        assert result["validation"]["violations"][0]["direction"] == "lower"

    def test_direction_defaults_to_higher_in_apply(self):
        """
        What: Verify direction defaults to "higher" if not specified in thresholds
        Why: Backward compatibility - existing thresholds without direction should work
        """
        thresholds = {
            "versions": {
                "rules_version": "0.2.0",
                "thresholds_version": "2.0.0",
                "normalization_version": "1.0.0",
            },
            "tests": [
                {
                    "code": "T01_test",
                    "metric": "test_metric",
                    "unit": "unit",
                    # No direction field
                    "primary": {
                        "bands": [
                            {"name": "pass", "op": "gte", "value": 80},
                            {"name": "fail", "op": "lt", "value": 80},
                        ]
                    },
                }
            ],
        }

        rep_metrics = {"T01_test": 50}  # Violates fail band
        rep_meta = {
            "rules_version": "0.2.0",
            "thresholds_version": "2.0.0",
            "normalization_version": "1.0.0",
        }

        result = apply_rep(rep_metrics, rep_meta, thresholds)

        # Verify direction defaults to "higher"
        assert len(result["validation"]["violations"]) == 1
        assert result["validation"]["violations"][0]["direction"] == "higher"
