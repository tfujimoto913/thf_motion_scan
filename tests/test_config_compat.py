"""
Purpose: Test thresholds.json version compatibility checking
Responsibility: Verify SemVer-based compatibility logic
Dependencies: src/config/compat.py (to be implemented)
Created: 2025-11-03
Decision Log: ADR-031 (thresholds.json compatibility checker)

CRITICAL: Tests must pass with strict SemVer rules (MAJOR blocks, MINOR warns)
"""

import pytest


class TestVersionCompatibility:
    """
    Test version compatibility checking logic.

    What: Verify SemVer-based compatibility rules
    Why: Ensure safe version migration and clear error messages
    Design Decision: MAJOR diff = ERROR, MINOR diff = WARN, PATCH diff = OK
    """

    def test_identical_versions_returns_ok(self):
        """
        Test: 同一バージョン → OK

        What: Same versions should be fully compatible
        Why: No migration risk when versions are identical
        Expected: status="OK", compatible=True for all fields
        """
        from src.config.compat import check_compat

        current = {
            "rules_version": "v2.1.0",
            "normalization_version": "v1.0.0"
        }
        required = {
            "rules_version": "v2.1.0",
            "normalization_version": "v1.0.0"
        }

        result = check_compat(current, required)

        assert result["status"] == "OK"
        assert result["details"]["rules_version"]["compatible"] is True
        assert result["details"]["normalization_version"]["compatible"] is True

    def test_major_version_diff_returns_error(self):
        """
        Test: MAJOR差異 → ERROR

        What: Major version mismatch should block execution
        Why: Breaking changes require explicit migration
        Expected: status="ERROR", compatible=False, clear reason
        """
        from src.config.compat import check_compat

        current = {
            "rules_version": "v2.1.0",
            "normalization_version": "v1.0.0"
        }
        required = {
            "rules_version": "v3.0.0",  # MAJOR bump: 2 → 3
            "normalization_version": "v1.0.0"
        }

        result = check_compat(current, required)

        assert result["status"] == "ERROR"
        assert result["details"]["rules_version"]["compatible"] is False
        assert "MAJOR" in result["reason"] or "breaking" in result["reason"].lower()

    def test_minor_version_diff_returns_warn(self):
        """
        Test: MINOR差異 → WARN

        What: Minor version mismatch should warn but allow execution
        Why: Backward-compatible changes should be safe with warning
        Expected: status="WARN", compatible=True, reason explains minor diff
        """
        from src.config.compat import check_compat

        current = {
            "rules_version": "v2.1.0",
            "normalization_version": "v1.0.0"
        }
        required = {
            "rules_version": "v2.0.0",  # MINOR backward: 2.1 → 2.0
            "normalization_version": "v1.0.0"
        }

        result = check_compat(current, required)

        assert result["status"] == "WARN"
        assert result["details"]["rules_version"]["compatible"] is True
        assert "MINOR" in result["reason"] or "minor" in result["reason"].lower()

    def test_missing_versions_returns_error(self):
        """
        Test: versions欠損 → ERROR

        What: Missing version fields should block execution
        Why: Cannot determine compatibility without version info
        Expected: status="ERROR", clear error about missing fields
        """
        from src.config.compat import check_compat

        current = {}  # Missing all version fields
        required = {
            "rules_version": "v2.0.0",
            "normalization_version": "v1.0.0"
        }

        result = check_compat(current, required)

        assert result["status"] == "ERROR"
        assert "missing" in result["reason"].lower() or "required" in result["reason"].lower()

    def test_patch_version_diff_returns_ok(self):
        """
        Test: PATCH差異 → OK

        What: Patch version differences should be fully compatible
        Why: Bug fixes should be transparent
        Expected: status="OK", compatible=True
        """
        from src.config.compat import check_compat

        current = {
            "rules_version": "v2.1.1",  # PATCH: 2.1.0 → 2.1.1
            "normalization_version": "v1.0.0"
        }
        required = {
            "rules_version": "v2.1.0",
            "normalization_version": "v1.0.0"
        }

        result = check_compat(current, required)

        assert result["status"] == "OK"
        assert result["details"]["rules_version"]["compatible"] is True

    def test_multiple_field_compatibility_check(self):
        """
        Test: 複数フィールドの互換性チェック

        What: Check compatibility across multiple version fields
        Why: Both rules_version and normalization_version must be compatible
        Expected: Worst status wins (ERROR > WARN > OK)
        """
        from src.config.compat import check_compat

        # rules_version: OK, normalization_version: ERROR → Overall ERROR
        current = {
            "rules_version": "v2.1.0",
            "normalization_version": "v1.0.0"
        }
        required = {
            "rules_version": "v2.1.0",
            "normalization_version": "v2.0.0"  # MAJOR: 1.x → 2.x
        }

        result = check_compat(current, required)

        assert result["status"] == "ERROR"
        assert result["details"]["rules_version"]["compatible"] is True
        assert result["details"]["normalization_version"]["compatible"] is False
