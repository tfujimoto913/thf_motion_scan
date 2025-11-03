"""
Purpose: Unit tests for KPI-based frame selection (Phase2: 静止画選出ロジック)
Responsibility: Validate B1-B8 KPI extraction, best/worst/repr selection, composite scoring
Dependencies: pytest, numpy
Created: 2025-11-04 by Claude Code
Decision Log: Phase2 Static Frame Selection - Implementation Plan Stage 1-5

CRITICAL:
- Tests follow TDD - Red → Green → Refactor
- Deterministic tests with fixed random seeds where applicable
- N/A handling patterns (None, float('nan'), missing keys)
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from processing.frame_selector import extract_frame_kpis

# ========== Stage 1: データ準備とKPI取得 ==========


class TestExtractFrameKpis:
    """
    Stage 1: Test KPI extraction from evaluator output.

    What: Extract B1-B8 KPI vectors from evaluator frames_data.
    Why: Provide clean KPI vectors for selection algorithms.
    Design Decision: N/A represented as None or float('nan'), 0.0 is valid.
    """

    def test_extract_all_valid_kpis_eccentric_phase(self):
        """
        Test: B1-B8が全て有効な場合（eccentric phase）
        Expected: 全KPIが正しく抽出され、N/A検出なし
        """
        # Red: This test will fail because extract_frame_kpis() doesn't exist yet
        frames_data = [
            {
                "frame_idx": 0,
                "B_principles": {
                    "eccentric": {
                        "B1_core_stability": 4.0,
                        "B2_support_foundation": 9.5,
                        "B3_3joint_coordination": 3.2,
                        "B4_pelvis_horizontal": 8.0,
                        "B5_knee_stability": 5.5,
                        "B6_ankle_mobility": 6.0,
                        "B7_upper_body_control": 2.5,
                        "B8_breathing_pattern": 3.0,
                    }
                },
            },
            {
                "frame_idx": 1,
                "B_principles": {
                    "eccentric": {
                        "B1_core_stability": 3.5,
                        "B2_support_foundation": 8.0,
                        "B3_3joint_coordination": 2.8,
                        "B4_pelvis_horizontal": 7.5,
                        "B5_knee_stability": 5.0,
                        "B6_ankle_mobility": 5.5,
                        "B7_upper_body_control": 2.0,
                        "B8_breathing_pattern": 2.5,
                    }
                },
            },
        ]

        result = extract_frame_kpis(frames_data, phase="eccentric")

        assert len(result) == 2

        # Frame 0
        assert result[0]["frame_idx"] == 0
        assert result[0]["kpis"]["B1_core_stability"] == 4.0
        assert result[0]["kpis"]["B2_support_foundation"] == 9.5
        assert result[0]["kpis"]["B8_breathing_pattern"] == 3.0
        assert result[0]["na_count"] == 0
        assert result[0]["na_rate"] == 0.0

        # Frame 1
        assert result[1]["frame_idx"] == 1
        assert result[1]["kpis"]["B1_core_stability"] == 3.5
        assert result[1]["na_count"] == 0

    def test_extract_single_kpi_missing_as_none(self):
        """
        Test: 単一KPI欠損（B3がNone）
        Expected: B3がNoneとして記録され、na_count=1, na_rate=1/8=0.125
        """
        frames_data = [
            {
                "frame_idx": 0,
                "B_principles": {
                    "eccentric": {
                        "B1_core_stability": 4.0,
                        "B2_support_foundation": 9.5,
                        "B3_3joint_coordination": None,  # N/A
                        "B4_pelvis_horizontal": 8.0,
                        "B5_knee_stability": 5.5,
                        "B6_ankle_mobility": 6.0,
                        "B7_upper_body_control": 2.5,
                        "B8_breathing_pattern": 3.0,
                    }
                },
            }
        ]

        result = extract_frame_kpis(frames_data, phase="eccentric")

        assert len(result) == 1
        assert result[0]["kpis"]["B3_3joint_coordination"] is None
        assert result[0]["na_count"] == 1
        assert result[0]["na_rate"] == pytest.approx(1 / 8)

    def test_extract_single_kpi_missing_as_nan(self):
        """
        Test: 単一KPI欠損（B4がNaN）
        Expected: B4がNoneに変換され、na_count=1
        """
        frames_data = [
            {
                "frame_idx": 0,
                "B_principles": {
                    "eccentric": {
                        "B1_core_stability": 4.0,
                        "B2_support_foundation": 9.5,
                        "B3_3joint_coordination": 3.2,
                        "B4_pelvis_horizontal": float("nan"),  # N/A as NaN
                        "B5_knee_stability": 5.5,
                        "B6_ankle_mobility": 6.0,
                        "B7_upper_body_control": 2.5,
                        "B8_breathing_pattern": 3.0,
                    }
                },
            }
        ]

        result = extract_frame_kpis(frames_data, phase="eccentric")

        assert len(result) == 1
        assert result[0]["kpis"]["B4_pelvis_horizontal"] is None
        assert result[0]["na_count"] == 1

    def test_extract_missing_key_as_na(self):
        """
        Test: KPIキー欠損（B5, B6が存在しない）
        Expected: B5, B6がNoneとして記録、na_count=2
        """
        frames_data = [
            {
                "frame_idx": 0,
                "B_principles": {
                    "eccentric": {
                        "B1_core_stability": 4.0,
                        "B2_support_foundation": 9.5,
                        "B3_3joint_coordination": 3.2,
                        "B4_pelvis_horizontal": 8.0,
                        # B5, B6 missing
                        "B7_upper_body_control": 2.5,
                        "B8_breathing_pattern": 3.0,
                    }
                },
            }
        ]

        result = extract_frame_kpis(frames_data, phase="eccentric")

        assert len(result) == 1
        assert result[0]["kpis"]["B5_knee_stability"] is None
        assert result[0]["kpis"]["B6_ankle_mobility"] is None
        assert result[0]["na_count"] == 2
        assert result[0]["na_rate"] == pytest.approx(2 / 8)

    def test_extract_major_kpis_all_missing(self):
        """
        Test: 主要KPI全欠損（B1, B4, B2が全てNone）
        Expected: 警告フラグが立つ、na_count=3
        """
        frames_data = [
            {
                "frame_idx": 0,
                "B_principles": {
                    "eccentric": {
                        "B1_core_stability": None,  # Major KPI
                        "B2_support_foundation": None,  # Major KPI
                        "B3_3joint_coordination": 3.2,
                        "B4_pelvis_horizontal": None,  # Major KPI
                        "B5_knee_stability": 5.5,
                        "B6_ankle_mobility": 6.0,
                        "B7_upper_body_control": 2.5,
                        "B8_breathing_pattern": 3.0,
                    }
                },
            }
        ]

        result = extract_frame_kpis(frames_data, phase="eccentric")

        assert len(result) == 1
        assert result[0]["na_count"] == 3
        assert result[0]["major_kpis_missing"] is True  # Warning flag

    def test_extract_all_kpis_missing_raises_error(self):
        """
        Test: 全KPI欠損（エラー）
        Expected: ValueError例外
        """
        frames_data = [
            {
                "frame_idx": 0,
                "B_principles": {
                    "eccentric": {
                        "B1_core_stability": None,
                        "B2_support_foundation": None,
                        "B3_3joint_coordination": None,
                        "B4_pelvis_horizontal": None,
                        "B5_knee_stability": None,
                        "B6_ankle_mobility": None,
                        "B7_upper_body_control": None,
                        "B8_breathing_pattern": None,
                    }
                },
            }
        ]

        with pytest.raises(ValueError, match="All KPIs are N/A"):
            extract_frame_kpis(frames_data, phase="eccentric")

    def test_extract_concentric_phase(self):
        """
        Test: phase='concentric' 指定
        Expected: concentricフェーズのKPIを抽出
        """
        frames_data = [
            {
                "frame_idx": 0,
                "B_principles": {
                    "eccentric": {
                        "B1_core_stability": 4.0,
                        # ... other KPIs
                    },
                    "concentric": {
                        "B1_core_stability": 3.0,  # Different from eccentric
                        "B2_support_foundation": 7.5,
                        "B3_3joint_coordination": 2.5,
                        "B4_pelvis_horizontal": 6.0,
                        "B5_knee_stability": 4.5,
                        "B6_ankle_mobility": 5.0,
                        "B7_upper_body_control": 2.0,
                        "B8_breathing_pattern": 2.5,
                    },
                },
            }
        ]

        result = extract_frame_kpis(frames_data, phase="concentric")

        assert len(result) == 1
        assert result[0]["kpis"]["B1_core_stability"] == 3.0  # concentric value
        assert result[0]["kpis"]["B2_support_foundation"] == 7.5

    def test_extract_overall_na_rate_warning(self):
        """
        Test: 全体の欠損率>50%で警告ログ
        Expected: 欠損率50%超でwarning_flagがTrue
        """
        frames_data = [
            {
                "frame_idx": 0,
                "B_principles": {
                    "eccentric": {
                        "B1_core_stability": 4.0,
                        "B2_support_foundation": None,
                        "B3_3joint_coordination": None,
                        "B4_pelvis_horizontal": None,
                        "B5_knee_stability": None,
                        "B6_ankle_mobility": 6.0,
                        "B7_upper_body_control": None,
                        "B8_breathing_pattern": None,
                    }
                },
            }
        ]

        result = extract_frame_kpis(frames_data, phase="eccentric")

        assert result[0]["na_count"] == 6  # 6/8 = 75%
        assert result[0]["na_rate"] > 0.5
        # Note: Actual warning log will be checked in implementation

    def test_extract_zero_is_valid_value(self):
        """
        Test: 0.0は有効値として扱う
        Expected: 0.0がそのまま記録され、N/Aとしてカウントされない
        """
        frames_data = [
            {
                "frame_idx": 0,
                "B_principles": {
                    "eccentric": {
                        "B1_core_stability": 0.0,  # Explicitly 0.0 (valid)
                        "B2_support_foundation": 0.0,
                        "B3_3joint_coordination": 0.0,
                        "B4_pelvis_horizontal": 0.0,
                        "B5_knee_stability": 0.0,
                        "B6_ankle_mobility": 0.0,
                        "B7_upper_body_control": 0.0,
                        "B8_breathing_pattern": 0.0,
                    }
                },
            }
        ]

        result = extract_frame_kpis(frames_data, phase="eccentric")

        assert len(result) == 1
        assert result[0]["kpis"]["B1_core_stability"] == 0.0
        assert result[0]["na_count"] == 0  # 0.0 is NOT N/A
        assert result[0]["na_rate"] == 0.0

    def test_extract_reproducibility_fixed_seed(self):
        """
        Test: 再現性確認（決定論的テスト）
        Expected: 同じ入力で同じ出力
        """
        random.seed(20251104)
        np.random.seed(20251104)

        frames_data = [
            {
                "frame_idx": i,
                "B_principles": {
                    "eccentric": {
                        f"B{j}_{kpi_name}": random.uniform(0, 10)
                        for j, kpi_name in enumerate(
                            [
                                "core_stability",
                                "support_foundation",
                                "3joint_coordination",
                                "pelvis_horizontal",
                                "knee_stability",
                                "ankle_mobility",
                                "upper_body_control",
                                "breathing_pattern",
                            ],
                            start=1,
                        )
                    }
                },
            }
            for i in range(10)
        ]

        # Run twice with same seed
        random.seed(20251104)
        np.random.seed(20251104)
        result1 = extract_frame_kpis(frames_data, phase="eccentric")

        random.seed(20251104)
        np.random.seed(20251104)
        result2 = extract_frame_kpis(frames_data, phase="eccentric")

        # Should produce identical results
        assert len(result1) == len(result2)
        for i in range(len(result1)):
            assert result1[i]["frame_idx"] == result2[i]["frame_idx"]
            assert result1[i]["na_count"] == result2[i]["na_count"]


# ========== Stage 4: 複合スコア設計 ==========


class TestCalculateCompositeScore:
    """
    Stage 4: Test composite score calculation with weights.

    What: Calculate weighted composite score from KPI values.
    Why: Provide tiebreak mechanism and overall quality metric.
    Design Decision: Default equal weights (1/8 each), customizable via parameter.
    """

    def test_calculate_default_equal_weights(self):
        """
        Test: デフォルト均等重み（1/8）での計算
        Expected: sum(kpis) / 8
        """
        # Red: calculate_composite_score() doesn't exist yet
        from processing.frame_selector import calculate_composite_score

        kpis = {
            "B1_core_stability": 4.0,
            "B2_support_foundation": 9.5,
            "B3_3joint_coordination": 3.2,
            "B4_pelvis_horizontal": 8.0,
            "B5_knee_stability": 5.5,
            "B6_ankle_mobility": 6.0,
            "B7_upper_body_control": 2.5,
            "B8_breathing_pattern": 3.0,
        }

        score = calculate_composite_score(kpis)

        # Expected: (4.0 + 9.5 + 3.2 + 8.0 + 5.5 + 6.0 + 2.5 + 3.0) / 8 = 41.7 / 8 = 5.2125
        expected = sum(kpis.values()) / 8
        assert score == pytest.approx(expected)

    def test_calculate_custom_weights(self):
        """
        Test: カスタム重み指定
        Expected: sum(w_i * kpi_i)
        """
        from processing.frame_selector import calculate_composite_score

        kpis = {
            "B1_core_stability": 4.0,
            "B2_support_foundation": 9.5,
            "B3_3joint_coordination": 3.2,
            "B4_pelvis_horizontal": 8.0,
            "B5_knee_stability": 5.5,
            "B6_ankle_mobility": 6.0,
            "B7_upper_body_control": 2.5,
            "B8_breathing_pattern": 3.0,
        }

        # Custom weights (major KPIs have higher weights)
        weights = {
            "B1_core_stability": 0.3,  # Major
            "B2_support_foundation": 0.2,  # Major
            "B3_3joint_coordination": 0.1,
            "B4_pelvis_horizontal": 0.2,  # Major
            "B5_knee_stability": 0.05,
            "B6_ankle_mobility": 0.05,
            "B7_upper_body_control": 0.05,
            "B8_breathing_pattern": 0.05,
        }

        score = calculate_composite_score(kpis, weights=weights)

        # Expected: 4.0*0.3 + 9.5*0.2 + 3.2*0.1 + 8.0*0.2 + 5.5*0.05 + 6.0*0.05 + 2.5*0.05 + 3.0*0.05
        expected = sum(kpis[k] * weights[k] for k in kpis)
        assert score == pytest.approx(expected)

    def test_calculate_with_na_values_excluded(self):
        """
        Test: N/A値除外時の挙動
        Expected: N/A（None）を除外して有効KPIのみで計算
        """
        from processing.frame_selector import calculate_composite_score

        kpis = {
            "B1_core_stability": 4.0,
            "B2_support_foundation": 9.5,
            "B3_3joint_coordination": None,  # N/A
            "B4_pelvis_horizontal": 8.0,
            "B5_knee_stability": None,  # N/A
            "B6_ankle_mobility": 6.0,
            "B7_upper_body_control": 2.5,
            "B8_breathing_pattern": 3.0,
        }

        score = calculate_composite_score(kpis)

        # Only 6 valid KPIs, so weight becomes 1/6 for each valid KPI
        valid_kpis = [v for v in kpis.values() if v is not None]
        expected = sum(valid_kpis) / len(valid_kpis)
        assert score == pytest.approx(expected)

    def test_calculate_all_na_returns_zero(self):
        """
        Test: 全KPIがN/Aの場合
        Expected: 0.0を返す
        """
        from processing.frame_selector import calculate_composite_score

        kpis = {
            "B1_core_stability": None,
            "B2_support_foundation": None,
            "B3_3joint_coordination": None,
            "B4_pelvis_horizontal": None,
            "B5_knee_stability": None,
            "B6_ankle_mobility": None,
            "B7_upper_body_control": None,
            "B8_breathing_pattern": None,
        }

        score = calculate_composite_score(kpis)

        assert score == 0.0

    def test_calculate_sigma_margin_warning(self):
        """
        Test: σマージン（0.18）判定
        Expected: スコア差が0.18未満の場合は「実質同値」として判定可能
        """
        from processing.frame_selector import calculate_composite_score

        kpis1 = {
            "B1_core_stability": 4.0,
            "B2_support_foundation": 9.5,
            "B3_3joint_coordination": 3.2,
            "B4_pelvis_horizontal": 8.0,
            "B5_knee_stability": 5.5,
            "B6_ankle_mobility": 6.0,
            "B7_upper_body_control": 2.5,
            "B8_breathing_pattern": 3.0,
        }

        kpis2 = {
            "B1_core_stability": 4.1,  # Slightly different
            "B2_support_foundation": 9.6,
            "B3_3joint_coordination": 3.3,
            "B4_pelvis_horizontal": 8.1,
            "B5_knee_stability": 5.6,
            "B6_ankle_mobility": 6.1,
            "B7_upper_body_control": 2.6,
            "B8_breathing_pattern": 3.1,
        }

        score1 = calculate_composite_score(kpis1)
        score2 = calculate_composite_score(kpis2)

        # Check if difference is less than sigma margin (0.18)
        diff = abs(score1 - score2)
        # This test just verifies the scores are calculable; actual margin check
        # will be done in selection logic (Stage 2)
        assert diff < 0.18  # Should be a small difference

    def test_calculate_normalized_kpis(self):
        """
        Test: 正規化されたKPI値での計算
        Expected: 0.0-1.0範囲の値で正しく計算
        """
        from processing.frame_selector import calculate_composite_score

        # Normalized KPIs (0.0-1.0 range)
        kpis = {
            "B1_core_stability": 0.5,
            "B2_support_foundation": 0.8,
            "B3_3joint_coordination": 0.3,
            "B4_pelvis_horizontal": 0.7,
            "B5_knee_stability": 0.6,
            "B6_ankle_mobility": 0.65,
            "B7_upper_body_control": 0.4,
            "B8_breathing_pattern": 0.45,
        }

        score = calculate_composite_score(kpis)

        expected = sum(kpis.values()) / 8
        assert score == pytest.approx(expected)
        assert 0.0 <= score <= 1.0  # Score should be in normalized range

    def test_calculate_zero_values_valid(self):
        """
        Test: 0.0は有効値として扱う
        Expected: 0.0がそのまま計算に含まれる
        """
        from processing.frame_selector import calculate_composite_score

        kpis = {
            "B1_core_stability": 0.0,  # Valid zero
            "B2_support_foundation": 0.0,
            "B3_3joint_coordination": 0.0,
            "B4_pelvis_horizontal": 0.0,
            "B5_knee_stability": 0.0,
            "B6_ankle_mobility": 0.0,
            "B7_upper_body_control": 0.0,
            "B8_breathing_pattern": 0.0,
        }

        score = calculate_composite_score(kpis)

        assert score == 0.0  # All zeros should result in 0.0 score

    def test_calculate_reproducibility_fixed_seed(self):
        """
        Test: 再現性確認（決定論的テスト）
        Expected: 同じ入力で同じ出力
        """
        from processing.frame_selector import calculate_composite_score

        random.seed(20251104)
        np.random.seed(20251104)

        kpis = {
            f"B{i}_{name}": random.uniform(0, 10)
            for i, name in enumerate(
                [
                    "core_stability",
                    "support_foundation",
                    "3joint_coordination",
                    "pelvis_horizontal",
                    "knee_stability",
                    "ankle_mobility",
                    "upper_body_control",
                    "breathing_pattern",
                ],
                start=1,
            )
        }

        # Run twice with same seed
        random.seed(20251104)
        score1 = calculate_composite_score(kpis)

        random.seed(20251104)
        score2 = calculate_composite_score(kpis)

        assert score1 == score2  # Should be deterministic


# ========== Stage 2: best/worst選出 ==========


class TestSelectBestWorstFrames:
    """
    Stage 2: Test best/worst frame selection based on major KPI priority.

    What: Select best (minimum KPIs) and worst (maximum KPIs) frames.
    Why: Provide objective basis for coaching feedback.
    Design Decision: Priority B1 > B4 > B2, composite score tiebreak, timestamp fallback.
    """

    def test_select_best_by_b1_minimum(self):
        """
        Test: B1が最小のフレームがbestとして選出される
        Expected: frame 1 (B1=3.0)
        """
        # Red: select_best_worst_frames() doesn't exist yet
        from processing.frame_selector import select_best_worst_frames

        frame_kpis = [
            {
                "frame_idx": 0,
                "kpis": {
                    "B1_core_stability": 4.0,
                    "B2_support_foundation": 9.5,
                    "B3_3joint_coordination": 3.2,
                    "B4_pelvis_horizontal": 8.0,
                    "B5_knee_stability": 5.5,
                    "B6_ankle_mobility": 6.0,
                    "B7_upper_body_control": 2.5,
                    "B8_breathing_pattern": 3.0,
                },
            },
            {
                "frame_idx": 1,
                "kpis": {
                    "B1_core_stability": 3.0,  # Minimum B1
                    "B2_support_foundation": 8.0,
                    "B3_3joint_coordination": 2.8,
                    "B4_pelvis_horizontal": 7.5,
                    "B5_knee_stability": 5.0,
                    "B6_ankle_mobility": 5.5,
                    "B7_upper_body_control": 2.0,
                    "B8_breathing_pattern": 2.5,
                },
            },
        ]

        result = select_best_worst_frames(frame_kpis)

        assert result["best"]["frame_idx"] == 1
        assert result["worst"]["frame_idx"] == 0

    def test_select_best_by_b4_when_b1_equal(self):
        """
        Test: B1同値時にB4で判定
        Expected: frame 1 (B1=4.0, B4=7.0)
        """
        from processing.frame_selector import select_best_worst_frames

        frame_kpis = [
            {
                "frame_idx": 0,
                "kpis": {
                    "B1_core_stability": 4.0,
                    "B2_support_foundation": 9.5,
                    "B3_3joint_coordination": 3.2,
                    "B4_pelvis_horizontal": 8.0,  # Higher B4
                    "B5_knee_stability": 5.5,
                    "B6_ankle_mobility": 6.0,
                    "B7_upper_body_control": 2.5,
                    "B8_breathing_pattern": 3.0,
                },
            },
            {
                "frame_idx": 1,
                "kpis": {
                    "B1_core_stability": 4.0,  # Same B1
                    "B2_support_foundation": 8.0,
                    "B3_3joint_coordination": 2.8,
                    "B4_pelvis_horizontal": 7.0,  # Lower B4 (better)
                    "B5_knee_stability": 5.0,
                    "B6_ankle_mobility": 5.5,
                    "B7_upper_body_control": 2.0,
                    "B8_breathing_pattern": 2.5,
                },
            },
        ]

        result = select_best_worst_frames(frame_kpis)

        assert result["best"]["frame_idx"] == 1  # B4 is lower

    def test_select_with_na_values_excluded(self):
        """
        Test: N/A値除外時の挙動
        Expected: N/Aを除外して残りのKPIで判定
        """
        from processing.frame_selector import select_best_worst_frames

        frame_kpis = [
            {
                "frame_idx": 0,
                "kpis": {
                    "B1_core_stability": 4.0,
                    "B2_support_foundation": None,  # N/A
                    "B3_3joint_coordination": 3.2,
                    "B4_pelvis_horizontal": 8.0,
                    "B5_knee_stability": None,  # N/A
                    "B6_ankle_mobility": 6.0,
                    "B7_upper_body_control": 2.5,
                    "B8_breathing_pattern": 3.0,
                },
            },
            {
                "frame_idx": 1,
                "kpis": {
                    "B1_core_stability": 3.0,  # Lower (better)
                    "B2_support_foundation": 8.0,
                    "B3_3joint_coordination": 2.8,
                    "B4_pelvis_horizontal": 7.5,
                    "B5_knee_stability": 5.0,
                    "B6_ankle_mobility": 5.5,
                    "B7_upper_body_control": 2.0,
                    "B8_breathing_pattern": None,  # N/A
                },
            },
        ]

        result = select_best_worst_frames(frame_kpis)

        assert result["best"]["frame_idx"] == 1  # B1 is lower despite N/A

    def test_select_all_major_kpis_missing_uses_composite_score(self):
        """
        Test: 主要KPI全欠損時は複合スコアで判定
        Expected: 複合スコアが低いフレームがbest
        """
        from processing.frame_selector import select_best_worst_frames

        frame_kpis = [
            {
                "frame_idx": 0,
                "kpis": {
                    "B1_core_stability": None,  # N/A
                    "B2_support_foundation": None,  # N/A
                    "B3_3joint_coordination": 3.2,
                    "B4_pelvis_horizontal": None,  # N/A
                    "B5_knee_stability": 8.0,  # Higher
                    "B6_ankle_mobility": 9.0,
                    "B7_upper_body_control": 7.5,
                    "B8_breathing_pattern": 8.5,
                },
            },
            {
                "frame_idx": 1,
                "kpis": {
                    "B1_core_stability": None,  # N/A
                    "B2_support_foundation": None,  # N/A
                    "B3_3joint_coordination": 2.8,
                    "B4_pelvis_horizontal": None,  # N/A
                    "B5_knee_stability": 5.0,  # Lower (better composite)
                    "B6_ankle_mobility": 5.5,
                    "B7_upper_body_control": 4.0,
                    "B8_breathing_pattern": 4.5,
                },
            },
        ]

        result = select_best_worst_frames(frame_kpis)

        # Frame 1 has lower composite score
        assert result["best"]["frame_idx"] == 1
        assert result["worst"]["frame_idx"] == 0


# ========== Stage 3: representative選出 + Stage 5: 統合テスト ==========


class TestSelectRepresentativeFrame:
    """
    Stage 3: Test representative frame selection (closest to median).

    What: Select frame closest to median KPI vector.
    Why: Provide typical performance reference for coaching.
    Design Decision: Min-max normalization, L2 distance, N/A dimension exclusion.
    """

    def test_select_representative_closest_to_median(self):
        """
        Test: 中央値に最も近いフレームが選出される
        Expected: frame 1 (median values)
        """
        # Red: select_representative_frame() doesn't exist yet
        from processing.frame_selector import select_representative_frame

        frame_kpis = [
            {
                "frame_idx": 0,
                "kpis": {
                    "B1_core_stability": 2.0,  # Low
                    "B2_support_foundation": 8.0,
                    "B3_3joint_coordination": 3.0,
                    "B4_pelvis_horizontal": 7.0,
                    "B5_knee_stability": 5.0,
                    "B6_ankle_mobility": 5.5,
                    "B7_upper_body_control": 2.0,
                    "B8_breathing_pattern": 2.5,
                },
            },
            {
                "frame_idx": 1,
                "kpis": {
                    "B1_core_stability": 4.0,  # Median
                    "B2_support_foundation": 9.0,
                    "B3_3joint_coordination": 3.5,
                    "B4_pelvis_horizontal": 8.0,
                    "B5_knee_stability": 5.5,
                    "B6_ankle_mobility": 6.0,
                    "B7_upper_body_control": 2.5,
                    "B8_breathing_pattern": 3.0,
                },
            },
            {
                "frame_idx": 2,
                "kpis": {
                    "B1_core_stability": 6.0,  # High
                    "B2_support_foundation": 10.0,
                    "B3_3joint_coordination": 4.0,
                    "B4_pelvis_horizontal": 9.0,
                    "B5_knee_stability": 6.0,
                    "B6_ankle_mobility": 6.5,
                    "B7_upper_body_control": 3.0,
                    "B8_breathing_pattern": 3.5,
                },
            },
        ]

        result = select_representative_frame(frame_kpis)

        # Frame 1 should be closest to median
        assert result["frame_idx"] == 1
        assert "repr_distance" in result
        assert result["repr_distance"] >= 0.0

    def test_select_with_na_dimensions_excluded(self):
        """
        Test: N/A次元除外時のL2距離計算
        Expected: N/A次元を除外して距離計算
        """
        from processing.frame_selector import select_representative_frame

        frame_kpis = [
            {
                "frame_idx": 0,
                "kpis": {
                    "B1_core_stability": 4.0,
                    "B2_support_foundation": None,  # N/A
                    "B3_3joint_coordination": 3.2,
                    "B4_pelvis_horizontal": 8.0,
                    "B5_knee_stability": None,  # N/A
                    "B6_ankle_mobility": 6.0,
                    "B7_upper_body_control": 2.5,
                    "B8_breathing_pattern": 3.0,
                },
            },
            {
                "frame_idx": 1,
                "kpis": {
                    "B1_core_stability": 4.5,
                    "B2_support_foundation": 8.5,
                    "B3_3joint_coordination": 3.5,
                    "B4_pelvis_horizontal": 8.5,
                    "B5_knee_stability": 5.5,
                    "B6_ankle_mobility": 6.5,
                    "B7_upper_body_control": 2.7,
                    "B8_breathing_pattern": None,  # N/A
                },
            },
        ]

        result = select_representative_frame(frame_kpis)

        # Should successfully select despite N/A values
        assert result["frame_idx"] in [0, 1]
        assert "repr_distance" in result


class TestSelectFrameTriplet:
    """
    Stage 5: Integrated test for best/worst/repr selection.

    What: Test full pipeline from KPI extraction to selection.
    Why: Verify end-to-end functionality and metadata output.
    """

    def test_select_frame_triplet_integration(self):
        """
        Test: 3枚（best/worst/repr）の統合選出
        Expected: 全てのメタデータが正しく出力される
        """
        from processing.frame_selector import select_frame_triplet

        frame_kpis = [
            {
                "frame_idx": 0,
                "kpis": {
                    "B1_core_stability": 5.0,
                    "B2_support_foundation": 9.5,
                    "B3_3joint_coordination": 3.8,
                    "B4_pelvis_horizontal": 8.5,
                    "B5_knee_stability": 5.8,
                    "B6_ankle_mobility": 6.2,
                    "B7_upper_body_control": 2.8,
                    "B8_breathing_pattern": 3.2,
                },
            },
            {
                "frame_idx": 1,
                "kpis": {
                    "B1_core_stability": 3.0,  # Best (lowest B1)
                    "B2_support_foundation": 8.0,
                    "B3_3joint_coordination": 2.8,
                    "B4_pelvis_horizontal": 7.5,
                    "B5_knee_stability": 5.0,
                    "B6_ankle_mobility": 5.5,
                    "B7_upper_body_control": 2.0,
                    "B8_breathing_pattern": 2.5,
                },
            },
            {
                "frame_idx": 2,
                "kpis": {
                    "B1_core_stability": 7.0,  # Worst (highest B1)
                    "B2_support_foundation": 10.0,
                    "B3_3joint_coordination": 4.5,
                    "B4_pelvis_horizontal": 9.5,
                    "B5_knee_stability": 6.5,
                    "B6_ankle_mobility": 7.0,
                    "B7_upper_body_control": 3.5,
                    "B8_breathing_pattern": 4.0,
                },
            },
        ]

        result = select_frame_triplet(frame_kpis)

        # Check structure
        assert "best" in result
        assert "worst" in result
        assert "repr" in result
        assert "metrics" in result

        # Check best/worst
        assert result["best"]["frame_idx"] == 1
        assert result["worst"]["frame_idx"] == 2

        # Check metrics
        metrics = result["metrics"]
        assert "best_worst_gap" in metrics
        assert "repr_distance" in metrics
        assert metrics["best_worst_gap"] > 0.0  # Should be different

    def test_select_frame_triplet_with_na_values(self):
        """
        Test: N/A値を含む統合テスト
        Expected: N/A処理が正しく動作し、3枚が選出される
        """
        from processing.frame_selector import select_frame_triplet

        frame_kpis = [
            {
                "frame_idx": 0,
                "kpis": {
                    "B1_core_stability": 4.0,
                    "B2_support_foundation": None,
                    "B3_3joint_coordination": 3.2,
                    "B4_pelvis_horizontal": 8.0,
                    "B5_knee_stability": None,
                    "B6_ankle_mobility": 6.0,
                    "B7_upper_body_control": 2.5,
                    "B8_breathing_pattern": 3.0,
                },
                "na_count": 2,
            },
            {
                "frame_idx": 1,
                "kpis": {
                    "B1_core_stability": 3.0,
                    "B2_support_foundation": 8.0,
                    "B3_3joint_coordination": 2.8,
                    "B4_pelvis_horizontal": 7.5,
                    "B5_knee_stability": 5.0,
                    "B6_ankle_mobility": 5.5,
                    "B7_upper_body_control": 2.0,
                    "B8_breathing_pattern": None,
                },
                "na_count": 1,
            },
        ]

        result = select_frame_triplet(frame_kpis)

        # Should successfully select all 3 despite N/A
        assert result["best"]["frame_idx"] in [0, 1]
        assert result["worst"]["frame_idx"] in [0, 1]
        assert result["repr"]["frame_idx"] in [0, 1]


# Final integration test
