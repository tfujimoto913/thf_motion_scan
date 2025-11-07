"""
Purpose: Unit tests for validator_rep and validator_session
Responsibility: Test rep-level validation, session aggregation, majority rule, statistics
Dependencies: pytest, json
Created: 2025-11-03 by Claude Code
Decision Log: Phase 5 - Validation System Integration (validator tests)

CRITICAL:
- Test all scenarios: all OK, ERROR mixed, WARN mixed, insufficient
- Verify p95 calculation (nearest-rank: 5 reps → sorted[3])
- Verify majority rule (3+ OK/WARN required)
"""

import json
from pathlib import Path

import pytest

from src.validation_engine.validator_rep import validate_rep
from src.validation_engine.validator_session import aggregate_session

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_jsonl(filepath: Path):
    """Load JSONL file and return list of dicts."""
    results = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            results.append(json.loads(line))
    return results


class TestValidatorRep:
    """Test rep-level validation."""

    def test_validate_rep_ok(self):
        """Test rep validation with OK state (all checks pass)."""
        rep_data = {
            "session_id": "session-001",
            "rep_index": 0,
            "test_code": "T02_B2",
            "rules_version": "2.1.0",
            "thresholds_version": "1.0.0",
            "normalization_version": "none",
            "metrics": {"score": 75.5},
            "validation": {"state": "OK", "violations": []},
        }
        expected_versions = {
            "rules_version": "2.1.0",
            "thresholds_version": "1.0.0",
            "normalization_version": "none",
        }

        result = validate_rep(rep_data, expected_versions)

        assert result["state"] == "OK"
        assert result["violations"] == []

    def test_validate_rep_missing_key(self):
        """Test rep validation with missing required key."""
        rep_data = {
            "session_id": "session-001",
            "rep_index": 0,
            # Missing test_code
            "rules_version": "2.1.0",
            "thresholds_version": "1.0.0",
            "metrics": {"score": 75.5},
            "validation": {"state": "OK", "violations": []},
        }

        result = validate_rep(rep_data)

        assert result["state"] == "ERROR"
        assert len(result["violations"]) == 1
        assert result["violations"][0]["category"] == "missing_key"
        assert "test_code" in result["violations"][0]["message"]

    def test_validate_rep_type_error(self):
        """Test rep validation with type error."""
        rep_data = {
            "session_id": "session-001",
            "rep_index": "0",  # Should be int, not str
            "test_code": "T02_B2",
            "rules_version": "2.1.0",
            "thresholds_version": "1.0.0",
            "metrics": {"score": 75.5},
            "validation": {"state": "OK", "violations": []},
        }

        result = validate_rep(rep_data)

        assert result["state"] == "ERROR"
        assert any(v["category"] == "type_error" for v in result["violations"])

    def test_validate_rep_version_major_diff(self):
        """Test rep validation with MAJOR version difference (ERROR)."""
        rep_data = {
            "session_id": "session-001",
            "rep_index": 0,
            "test_code": "T02_B2",
            "rules_version": "3.0.0",  # MAJOR diff from 2.1.0
            "thresholds_version": "1.0.0",
            "normalization_version": "none",
            "metrics": {"score": 75.5},
            "validation": {"state": "OK", "violations": []},
        }
        expected_versions = {
            "rules_version": "2.1.0",
            "thresholds_version": "1.0.0",
            "normalization_version": "none",
        }

        result = validate_rep(rep_data, expected_versions)

        assert result["state"] == "ERROR"
        assert any(
            v["category"] == "version_compatibility" and v["severity"] == "ERROR"
            for v in result["violations"]
        )

    def test_validate_rep_version_minor_diff(self):
        """Test rep validation with MINOR version difference (WARN)."""
        rep_data = {
            "session_id": "session-001",
            "rep_index": 0,
            "test_code": "T02_B2",
            "rules_version": "2.2.0",  # MINOR diff from 2.1.0
            "thresholds_version": "1.0.0",
            "normalization_version": "none",
            "metrics": {"score": 75.5},
            "validation": {"state": "OK", "violations": []},
        }
        expected_versions = {
            "rules_version": "2.1.0",
            "thresholds_version": "1.0.0",
            "normalization_version": "none",
        }

        result = validate_rep(rep_data, expected_versions)

        assert result["state"] == "WARN"
        assert any(
            v["category"] == "version_compatibility" and v["severity"] == "WARN"
            for v in result["violations"]
        )


class TestValidatorSession:
    """Test session-level aggregation."""

    def test_aggregate_session_all_ok(self):
        """Test session aggregation with all OK reps."""
        reps = load_jsonl(FIXTURES_DIR / "all_ok.jsonl")

        result = aggregate_session(reps)

        assert result["qc_pass_count"] == 5
        assert result["total_reps"] == 5
        assert result["validation"]["state"] == "OK"

        # Verify statistics
        agg = result["aggregates"]
        assert agg["mean"] == 80.24  # (75.5 + 78.2 + 80.0 + 82.5 + 85.0) / 5
        assert agg["sd"] > 0  # Should have some variance
        # p95 for 5 reps: sorted[3] = 82.5
        assert agg["p95"] == 82.5
        assert agg["rep_states"] == ["OK", "OK", "OK", "OK", "OK"]

    def test_aggregate_session_error_mixed(self):
        """Test session aggregation with ERROR mixed (2 OK, 1 WARN, 2 ERROR)."""
        reps = load_jsonl(FIXTURES_DIR / "error_mixed.jsonl")

        result = aggregate_session(reps)

        assert result["qc_pass_count"] == 3  # 2 OK + 1 WARN
        assert result["total_reps"] == 5
        # Session state should be ERROR because at least one rep is ERROR
        assert result["validation"]["state"] == "ERROR"

        # Verify statistics (WARN included, ERROR excluded)
        # Valid scores: 75.5, 78.2, 70.0 (3 values)
        agg = result["aggregates"]
        assert agg["mean"] is not None
        # p95 for 3 values: sorted[2] = 78.2
        assert agg["p95"] == 78.2
        assert agg["rep_states"] == ["OK", "OK", "WARN", "ERROR", "ERROR"]

    def test_aggregate_session_warn_mixed(self):
        """Test session aggregation with WARN mixed (3 OK, 2 WARN)."""
        reps = load_jsonl(FIXTURES_DIR / "warn_mixed.jsonl")

        result = aggregate_session(reps)

        assert result["qc_pass_count"] == 5  # 3 OK + 2 WARN
        assert result["total_reps"] == 5
        # Session state should be WARN because at least one rep is WARN
        assert result["validation"]["state"] == "WARN"

        # Verify statistics (all 5 scores included)
        # Scores: 75.5, 78.2, 80.0, 72.0, 68.5
        # Sorted: 68.5, 72.0, 75.5, 78.2, 80.0
        # p95: sorted[3] = 78.2
        agg = result["aggregates"]
        assert agg["p95"] == 78.2
        assert agg["rep_states"] == ["OK", "OK", "OK", "WARN", "WARN"]

    def test_aggregate_session_insufficient(self):
        """Test session aggregation with insufficient valid reps (2 OK, 3 ERROR)."""
        reps = load_jsonl(FIXTURES_DIR / "insufficient.jsonl")

        result = aggregate_session(reps)

        assert result["qc_pass_count"] == 2  # Only 2 OK
        assert result["total_reps"] == 5
        # Session state should be INSUFFICIENT (< 3 OK/WARN)
        assert result["validation"]["state"] == "INSUFFICIENT"

        # Verify no statistics calculated
        agg = result["aggregates"]
        assert agg["mean"] is None
        assert agg["sd"] is None
        assert agg["p95"] is None
        assert agg["rep_states"] == ["OK", "OK", "ERROR", "ERROR", "ERROR"]

        # Verify insufficient violation message
        violations = result["validation"]["violations"]
        assert any(
            v["category"] == "insufficient_reps" and v["severity"] == "ERROR"
            for v in violations
        )

    def test_p95_calculation_nearest_rank(self):
        """Test p95 calculation using nearest-rank method for 5 reps."""
        # Manually create reps with known scores
        reps = []
        scores = [60.0, 65.0, 70.0, 75.0, 80.0]  # Sorted
        for i, score in enumerate(scores):
            reps.append(
                {
                    "session_id": "session-test",
                    "rep_index": i,
                    "metrics": {"score": score},
                    "validation": {"state": "OK", "violations": []},
                }
            )

        result = aggregate_session(reps)

        # p95 for 5 reps: sorted[3] = 75.0
        assert result["aggregates"]["p95"] == 75.0
