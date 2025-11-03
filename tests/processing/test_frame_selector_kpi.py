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


# TODO: Stage 2-5 tests will be added after Stage 1 implementation
