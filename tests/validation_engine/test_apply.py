"""
Purpose: Test ValidationEngine apply functions for reps and sessions
Responsibility: Ensure validation_state outputs correct severity/violations
Dependencies: src.validation_engine.apply, src.validation_engine.compat
Created: 2025-11-03 by Codex
Decision Log: Task B - ValidationEngine 中間層化

CRITICAL: validation_state.state must reflect worst severity (ERROR > WARN > OK)
"""

import pytest

from src.validation_engine.apply import apply_rep, apply_session
from src.validation_engine.compat import CompatibilityStatus


def _baseline_thresholds():
    return {
        "versions": {
            "rules_version": "0.2.0",
            "thresholds_version": "2.0.0",
            "normalization_version": "1.0.0",
        },
        "tests": [
            {
                "code": "T01_B1",
                "metric": "hip_external_rotation_deg",
                "unit": "deg",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "lt", "value": 15},
                        {"name": "border", "op": "range_inc", "value": [15, 25]},
                        {"name": "fail", "op": "gte", "value": 25},
                    ]
                },
            },
            {
                "code": "T02_B2",
                "metric": "bos_mediolateral_excursion_norm",
                "unit": "norm",
                "primary": {
                    "bands": [
                        {"name": "pass", "op": "lt", "value": 0.1},
                        {"name": "border", "op": "range_inc", "value": [0.1, 0.2]},
                        {"name": "fail", "op": "gt", "value": 0.2},
                    ]
                },
            },
        ],
    }


class TestApplyRep:
    def test_identical_versions_returns_ok(self):
        thresholds = _baseline_thresholds()
        rep_metrics = {"T01_B1": 10}
        rep_meta = {
            "rules_version": "0.2.0",
            "thresholds_version": "2.0.0",
            "normalization_version": "1.0.0",
        }

        result = apply_rep(rep_metrics, rep_meta, thresholds)

        assert result["validation"]["state"] == CompatibilityStatus.OK
        assert result["validation"]["violations"] == []

    def test_minor_version_warn(self):
        thresholds = _baseline_thresholds()
        rep_metrics = {"T01_B1": 10}
        rep_meta = {
            "rules_version": "0.3.0",  # MINOR diff
            "thresholds_version": "2.0.0",
            "normalization_version": "1.0.0",
        }

        result = apply_rep(rep_metrics, rep_meta, thresholds)

        assert result["validation"]["state"] == CompatibilityStatus.WARN
        assert result["validation"]["violations"][0]["field"] == "rules_version"

    def test_major_version_error(self):
        thresholds = _baseline_thresholds()
        rep_metrics = {"T01_B1": 10}
        rep_meta = {
            "rules_version": "1.0.0",
            "thresholds_version": "1.0.0",  # MAJOR diff
            "normalization_version": "1.0.0",
        }

        result = apply_rep(rep_metrics, rep_meta, thresholds)

        assert result["validation"]["state"] == CompatibilityStatus.ERROR
        fields = [v["field"] for v in result["validation"]["violations"]]
        assert "thresholds_version" in fields

    def test_metric_violation_escalates_to_error(self):
        thresholds = _baseline_thresholds()
        rep_metrics = {"T01_B1": 30}  # beyond fail band
        rep_meta = {
            "rules_version": "0.2.0",
            "thresholds_version": "2.0.0",
            "normalization_version": "1.0.0",
        }

        result = apply_rep(rep_metrics, rep_meta, thresholds)

        assert result["validation"]["state"] == CompatibilityStatus.ERROR
        violation = result["validation"]["violations"][-1]
        assert violation["test_code"] == "T01_B1"
        assert violation["severity"] == "fail"


class TestApplySession:
    def test_session_reuses_rep_logic(self):
        thresholds = _baseline_thresholds()
        session_metrics = {"T02_B2": 0.05}
        session_meta = {
            "rules_version": "0.2.0",
            "thresholds_version": "2.0.0",
            "normalization_version": "1.0.0",
        }

        result = apply_session(session_metrics, session_meta, thresholds)
        assert result["validation"]["state"] == CompatibilityStatus.OK

    def test_session_minor_warn(self):
        thresholds = _baseline_thresholds()
        session_metrics = {"T02_B2": 0.05}
        session_meta = {
            "rules_version": "0.2.0",
            "thresholds_version": "2.1.0",  # MINOR diff
            "normalization_version": "1.0.0",
        }

        result = apply_session(session_metrics, session_meta, thresholds)
        assert result["validation"]["state"] == CompatibilityStatus.WARN
        assert any(v["field"] == "thresholds_version" for v in result["validation"]["violations"])
