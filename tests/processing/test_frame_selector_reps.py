"""
Purpose: Unit tests for rep-level selection logic in frame_selector
Responsibility: Test select_representative_reps() with acceptance criteria cases
Dependencies: pytest
Created: 2025-11-03 by Claude Code
Decision Log: Phase 2 - Overlay仕様FIX & ベスト/ワースト抽出ロジック確定

CRITICAL:
- Test all 6 acceptance criteria cases (A-F)
- Verify N/A handling, tiebreak rules, empty data handling
"""

from __future__ import annotations

import pytest

from processing.frame_selector import (
    build_rep_annotation,
    select_representative_reps,
)


class TestSelectRepresentativeReps:
    """Test rep-level selection logic."""

    def test_case_a_normal(self):
        """
        ケースA：正常系
        10 reps、N/A率各10%、スコア均等分布 → best/worst/repr が正しく選定される
        """
        reps = []
        for i in range(10):
            # Scores from 50.0 to 95.0 (step 5.0)
            # N/A rate: 10% (1 out of 10 KPIs)
            kpi_scores = {
                f"kpi_{j}": (50.0 + i * 5.0) if j != 0 else None  # First KPI is N/A
                for j in range(10)
            }
            reps.append({
                "rep_number": i,
                "kpi_scores": kpi_scores,
                "versions": {
                    "rules_version": "v2.1",
                    "thresholds_version": "v2.0",
                    "normalization_version": "v1.0",
                },
            })

        result = select_representative_reps(reps)

        assert result["best"] is not None
        assert result["worst"] is not None
        assert result["repr"] is not None

        # Best should be rep 9 (highest score: 95.0)
        assert result["best"]["rep_number"] == 9
        assert result["best"]["normalized_score"] == pytest.approx(95.0, abs=0.1)

        # Worst should be rep 0 (lowest score: 50.0)
        assert result["worst"]["rep_number"] == 0
        assert result["worst"]["normalized_score"] == pytest.approx(50.0, abs=0.1)

        # Representative should be close to median (72.5)
        # Median of [50, 55, 60, 65, 70, 75, 80, 85, 90, 95] = 72.5
        # Rep 4 (70) or Rep 5 (75) should be closest
        repr_score = result["repr"]["normalized_score"]
        assert 70.0 <= repr_score <= 75.0

    def test_case_b_na_heavy(self):
        """
        ケースB：N/A多数
        10 reps、うち4 repsが有効項目40% → 4 repsが除外され、残り6から選定
        """
        reps = []
        for i in range(10):
            if i < 4:
                # First 4 reps: only 4 out of 10 KPIs valid (40%)
                kpi_scores = {f"kpi_{j}": 50.0 if j < 4 else None for j in range(10)}
            else:
                # Remaining 6 reps: 9 out of 10 KPIs valid (90%)
                kpi_scores = {f"kpi_{j}": (50.0 + i * 5.0) if j != 0 else None for j in range(10)}

            reps.append({
                "rep_number": i,
                "kpi_scores": kpi_scores,
                "versions": {
                    "rules_version": "v2.1",
                    "thresholds_version": "v2.0",
                    "normalization_version": "v1.0",
                },
            })

        result = select_representative_reps(reps)

        assert result["best"] is not None
        assert result["worst"] is not None
        assert result["repr"] is not None

        # First 4 reps should be excluded (40% < 50%)
        # Best should be from reps 4-9 (rep 9 has highest score)
        assert result["best"]["rep_number"] >= 4
        assert result["worst"]["rep_number"] >= 4

    def test_case_c_tie(self):
        """
        ケースC：同点
        3 reps全て同スコア → N/A率でタイブレーク、それも同じならrep_number順
        """
        reps = [
            {
                "rep_number": 0,
                "kpi_scores": {f"kpi_{j}": 70.0 if j < 8 else None for j in range(10)},  # N/A rate: 20%
                "versions": {"rules_version": "v2.1", "thresholds_version": "v2.0"},
            },
            {
                "rep_number": 1,
                "kpi_scores": {f"kpi_{j}": 70.0 if j < 9 else None for j in range(10)},  # N/A rate: 10%
                "versions": {"rules_version": "v2.1", "thresholds_version": "v2.0"},
            },
            {
                "rep_number": 2,
                "kpi_scores": {f"kpi_{j}": 70.0 for j in range(10)},  # N/A rate: 0%
                "versions": {"rules_version": "v2.1", "thresholds_version": "v2.0"},
            },
        ]

        result = select_representative_reps(reps)

        # All have same score (70.0), so tiebreak by N/A rate (lower is better)
        # rep 2 has lowest N/A rate (0%), so it should be selected for best
        assert result["best"]["rep_number"] == 2

        # For worst, still rep 2 (same score, lowest N/A rate)
        # Actually, worst selects by (score ASC, na_rate ASC, rep_number ASC)
        # All same score, so lowest N/A rate wins
        assert result["worst"]["rep_number"] == 2

    def test_case_d_empty_data(self):
        """
        ケースD：空データ
        0 reps → 空配列を返し、エラーにならない
        """
        reps = []

        result = select_representative_reps(reps)

        assert result["best"] is None
        assert result["worst"] is None
        assert result["repr"] is None

    def test_case_e_versions_inconsistent(self):
        """
        ケースE：versions不一致
        rules_version が2種類混在 → 選定は継続（Warningログは実装側で対応）
        """
        reps = [
            {
                "rep_number": 0,
                "kpi_scores": {f"kpi_{j}": 70.0 for j in range(10)},
                "versions": {"rules_version": "v2.1", "thresholds_version": "v2.0"},
            },
            {
                "rep_number": 1,
                "kpi_scores": {f"kpi_{j}": 75.0 for j in range(10)},
                "versions": {"rules_version": "v2.2", "thresholds_version": "v2.0"},  # Different version
            },
            {
                "rep_number": 2,
                "kpi_scores": {f"kpi_{j}": 80.0 for j in range(10)},
                "versions": {"rules_version": "v2.1", "thresholds_version": "v2.0"},
            },
        ]

        result = select_representative_reps(reps)

        # Selection should succeed despite version mismatch
        assert result["best"] is not None
        assert result["worst"] is not None
        assert result["repr"] is not None

        # Best should be rep 2 (highest score: 80.0)
        assert result["best"]["rep_number"] == 2

    def test_case_f_annotation_elements(self):
        """
        ケースF：注記要素
        選定結果のJSONにversions、N/A率、valid_kpi_countが全て含まれる
        """
        reps = [
            {
                "rep_number": 0,
                "kpi_scores": {f"kpi_{j}": 70.0 if j < 8 else None for j in range(10)},
                "kpi_classes": {f"kpi_{j}": "A" for j in range(8)},
                "kpi_p_values": {f"kpi_{j}": 0.85 for j in range(8)},
                "versions": {
                    "rules_version": "v2.1",
                    "thresholds_version": "v2.0",
                    "normalization_version": "v1.0",
                },
            },
        ]

        result = select_representative_reps(reps)

        assert result["best"] is not None

        # Check that computed fields are present
        best_rep = result["best"]
        assert "na_rate" in best_rep
        assert "valid_kpi_count" in best_rep
        assert "total_kpi_count" in best_rep
        assert "normalized_score" in best_rep

        # Build annotation
        annotation = build_rep_annotation(best_rep, selection_reason="best")

        # Verify annotation structure
        assert "kpi_values" in annotation
        assert "kpi_classes" in annotation
        assert "kpi_p_values" in annotation
        assert "versions" in annotation
        assert "metadata" in annotation

        # Verify metadata contents
        metadata = annotation["metadata"]
        assert "na_rate" in metadata
        assert "valid_kpi_count" in metadata
        assert "total_kpi_count" in metadata
        assert "selection_reason" in metadata
        assert "rep_number" in metadata

        # Verify versions
        versions = annotation["versions"]
        assert versions["rules_version"] == "v2.1"
        assert versions["thresholds_version"] == "v2.0"
        assert versions["normalization_version"] == "v1.0"

    def test_insufficient_valid_kpis_all_filtered(self):
        """
        Test edge case: all reps have < 50% valid KPIs → all filtered out
        """
        reps = [
            {
                "rep_number": i,
                "kpi_scores": {f"kpi_{j}": 50.0 if j < 4 else None for j in range(10)},  # 40% valid
                "versions": {"rules_version": "v2.1", "thresholds_version": "v2.0"},
            }
            for i in range(5)
        ]

        result = select_representative_reps(reps)

        # All reps should be filtered out
        assert result["best"] is None
        assert result["worst"] is None
        assert result["repr"] is None

    def test_tiebreak_na_rate_then_rep_number(self):
        """
        Test tiebreak logic: same score → lower N/A rate → earlier rep_number
        """
        reps = [
            {
                "rep_number": 2,
                "kpi_scores": {f"kpi_{j}": 70.0 if j < 9 else None for j in range(10)},  # N/A rate: 10%
                "versions": {"rules_version": "v2.1", "thresholds_version": "v2.0"},
            },
            {
                "rep_number": 0,
                "kpi_scores": {f"kpi_{j}": 70.0 if j < 9 else None for j in range(10)},  # N/A rate: 10%
                "versions": {"rules_version": "v2.1", "thresholds_version": "v2.0"},
            },
            {
                "rep_number": 1,
                "kpi_scores": {f"kpi_{j}": 70.0 if j < 9 else None for j in range(10)},  # N/A rate: 10%
                "versions": {"rules_version": "v2.1", "thresholds_version": "v2.0"},
            },
        ]

        result = select_representative_reps(reps)

        # All same score and N/A rate, so earliest rep_number (0) should win for both
        # For best: max by (score, -na_rate, -rep_number) → rep 0 wins (earliest rep_number)
        assert result["best"]["rep_number"] == 0

        # For worst: min by (score, na_rate, rep_number) → rep 0 wins (earliest rep_number)
        assert result["worst"]["rep_number"] == 0
