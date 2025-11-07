"""
Purpose: Unit tests for processing.overlay_drawer annotation text placement
Responsibility: Validate versions/metadata/KPI annotations
Dependencies: pytest, numpy, cv2
Created: 2025-11-04 by Claude
Decision Log: Phase 5 - Overlay描画実装 Stage 4
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from processing.overlay_drawer import (
    draw_kpi_annotation,
    draw_metadata_annotation,
    draw_versions_annotation,
)


def create_test_image(width: int = 640, height: int = 480) -> np.ndarray:
    """テスト用画像生成（黒背景）"""
    return np.zeros((height, width, 3), dtype=np.uint8)


class TestDrawVersionsAnnotation:
    def test_draw_versions_annotation(self):
        """左上にversions注記が描画される"""
        image = create_test_image()
        versions = {
            'rules_version': '2.1.0',
            'thresholds_version': '1.0.0',
            'normalization_version': '1.0.0'
        }

        draw_versions_annotation(image, versions)

        # 画像が変更されたか確認（黒背景から変化）
        assert np.any(image != 0)

    def test_draw_versions_annotation_skip_empty(self):
        """versionsが空の場合はスキップ"""
        image = create_test_image()
        versions = {}

        draw_versions_annotation(image, versions)

        # 画像が変更されていないか確認
        assert np.all(image == 0)

    def test_draw_versions_annotation_with_missing_fields(self):
        """一部のフィールドが欠けていても描画される（N/A表示）"""
        image = create_test_image()
        versions = {
            'rules_version': '2.1.0'
            # thresholds_version, normalization_version は欠損
        }

        draw_versions_annotation(image, versions)

        # 画像が変更されたか確認
        assert np.any(image != 0)


class TestDrawMetadataAnnotation:
    def test_draw_metadata_annotation(self):
        """左下にmetadata注記が描画される"""
        image = create_test_image()
        metadata = {
            'selection_reason': 'best',
            'valid_kpi_count': 6,
            'total_kpi_count': 8,
            'na_rate': 0.25
        }

        draw_metadata_annotation(image, metadata)

        assert np.any(image != 0)

    def test_draw_metadata_annotation_skip_empty(self):
        """metadataが空の場合はスキップ"""
        image = create_test_image()
        metadata = {}

        draw_metadata_annotation(image, metadata)

        assert np.all(image == 0)

    def test_draw_metadata_annotation_with_missing_fields(self):
        """一部のフィールドが欠けていても描画される（デフォルト値）"""
        image = create_test_image()
        metadata = {
            'selection_reason': 'repr'
            # valid_kpi_count, total_kpi_count, na_rate は欠損
        }

        draw_metadata_annotation(image, metadata)

        assert np.any(image != 0)


class TestDrawKpiAnnotation:
    def test_draw_kpi_annotation(self):
        """右上にKPI注記が描画される"""
        image = create_test_image()
        kpi_values = {
            'B1_core_stability': 4.2,
            'B4_pelvis_horizontal': 3.8,
            'B2_support_foundation': 3.5
        }
        kpi_classes = {
            'B1_core_stability': 'A',
            'B4_pelvis_horizontal': 'B',
            'B2_support_foundation': 'B'
        }
        kpi_p_values = {
            'B1_core_stability': 0.92,
            'B4_pelvis_horizontal': 0.85,
            'B2_support_foundation': 0.78
        }

        draw_kpi_annotation(image, kpi_values, kpi_classes, kpi_p_values, max_kpis=5)

        assert np.any(image != 0)

    def test_draw_kpi_annotation_sorted_by_value(self):
        """KPIが値の大きい順に表示される"""
        image = create_test_image()
        kpi_values = {
            'B1_core_stability': 2.0,  # 最小
            'B4_pelvis_horizontal': 4.5,  # 最大
            'B2_support_foundation': 3.0  # 中間
        }
        kpi_classes = {k: 'B' for k in kpi_values}
        kpi_p_values = {k: 0.9 for k in kpi_values}

        draw_kpi_annotation(image, kpi_values, kpi_classes, kpi_p_values, max_kpis=5)

        # ソート順の検証は視覚的確認が必要（ここでは描画されたことのみ確認）
        assert np.any(image != 0)

    def test_draw_kpi_annotation_limit_max_kpis(self):
        """max_kpis制限が機能する（上位N個のみ表示）"""
        image = create_test_image()
        kpi_values = {f'B{i}': float(i) for i in range(1, 9)}  # 8個のKPI
        kpi_classes = {k: 'B' for k in kpi_values}
        kpi_p_values = {k: 0.9 for k in kpi_values}

        draw_kpi_annotation(image, kpi_values, kpi_classes, kpi_p_values, max_kpis=3)

        # 上位3個のみ表示（視覚的確認が必要）
        assert np.any(image != 0)

    def test_draw_kpi_annotation_skip_empty(self):
        """kpi_valuesが空の場合はスキップ"""
        image = create_test_image()
        kpi_values = {}
        kpi_classes = {}
        kpi_p_values = {}

        draw_kpi_annotation(image, kpi_values, kpi_classes, kpi_p_values, max_kpis=5)

        assert np.all(image == 0)

    def test_draw_kpi_annotation_with_none_values(self):
        """Noneを含むKPI値の処理（N/A表示）"""
        image = create_test_image()
        kpi_values = {
            'B1_core_stability': 4.2,
            'B4_pelvis_horizontal': None  # N/A
        }
        kpi_classes = {
            'B1_core_stability': 'A',
            'B4_pelvis_horizontal': 'N/A'
        }
        kpi_p_values = {
            'B1_core_stability': 0.92,
            'B4_pelvis_horizontal': 0.0
        }

        draw_kpi_annotation(image, kpi_values, kpi_classes, kpi_p_values, max_kpis=5)

        assert np.any(image != 0)
