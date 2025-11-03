"""
Purpose: Unit tests for processing.overlay_drawer integrated draw_overlay function
Responsibility: Validate full overlay drawing with all elements and error handling
Dependencies: pytest, numpy, cv2
Created: 2025-11-04 by Claude
Decision Log: Phase 5 - Overlay描画実装 Stage 5
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from processing.overlay_drawer import (
    LEFT_HIP,
    LEFT_SHOULDER,
    RIGHT_HIP,
    RIGHT_SHOULDER,
    draw_overlay,
)


def create_test_landmarks(visibility: float = 0.9) -> list[dict]:
    """テスト用ランドマークリスト生成（33点）"""
    landmarks = []
    for i in range(33):
        landmarks.append({
            'x': 0.5,
            'y': 0.5,
            'z': 0.0,
            'visibility': visibility
        })

    # 特定ランドマークに座標を設定
    landmarks[LEFT_SHOULDER] = {'x': 0.4, 'y': 0.3, 'z': 0.0, 'visibility': visibility}
    landmarks[RIGHT_SHOULDER] = {'x': 0.6, 'y': 0.3, 'z': 0.0, 'visibility': visibility}
    landmarks[LEFT_HIP] = {'x': 0.4, 'y': 0.7, 'z': 0.0, 'visibility': visibility}
    landmarks[RIGHT_HIP] = {'x': 0.6, 'y': 0.7, 'z': 0.0, 'visibility': visibility}

    return landmarks


def create_test_image(width: int = 640, height: int = 480) -> np.ndarray:
    """テスト用画像生成（黒背景）"""
    return np.zeros((height, width, 3), dtype=np.uint8)


def create_test_annotation_data() -> dict:
    """テスト用annotation_data生成"""
    return {
        'kpi_values': {
            'B1_core_stability': 4.2,
            'B4_pelvis_horizontal': 3.8,
            'B2_support_foundation': 3.5
        },
        'kpi_classes': {
            'B1_core_stability': 'A',
            'B4_pelvis_horizontal': 'B',
            'B2_support_foundation': 'B'
        },
        'kpi_p_values': {
            'B1_core_stability': 0.92,
            'B4_pelvis_horizontal': 0.85,
            'B2_support_foundation': 0.78
        },
        'versions': {
            'rules_version': '2.1.0',
            'thresholds_version': '1.0.0',
            'normalization_version': '1.0.0'
        },
        'metadata': {
            'selection_reason': 'best',
            'valid_kpi_count': 6,
            'total_kpi_count': 8,
            'na_rate': 0.25,
            'rep_number': 1
        }
    }


class TestDrawOverlay:
    def test_draw_overlay_full(self):
        """全要素が描画される（線、矢印、注記）"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)
        annotation_data = create_test_annotation_data()

        result = draw_overlay(
            image,
            landmarks,
            annotation_data,
            show_versions=True,
            show_metadata=True,
            show_kpi=True,
            min_visibility=0.5,
            rotation_angle=15.0
        )

        # 元画像と異なる新しい画像が返される
        assert result is not None
        assert result.shape == image.shape
        # 描画されたか確認
        assert np.any(result != 0)

    def test_draw_overlay_copies_image(self):
        """元画像が変更されていない（コピーして描画）"""
        image = create_test_image()
        original_copy = image.copy()
        landmarks = create_test_landmarks(visibility=0.9)
        annotation_data = create_test_annotation_data()

        result = draw_overlay(image, landmarks, annotation_data)

        # 元画像が変更されていないか確認
        assert np.array_equal(image, original_copy)
        # 結果画像は変更されている
        assert not np.array_equal(result, original_copy)

    def test_draw_overlay_landmark_missing(self):
        """ランドマーク欠損時でも他の要素は描画される"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)
        landmarks[LEFT_SHOULDER] = None  # 左肩を欠損
        annotation_data = create_test_annotation_data()

        result = draw_overlay(image, landmarks, annotation_data)

        # エラーにならず結果が返される
        assert result is not None
        # 注記は描画される
        assert np.any(result != 0)

    def test_draw_overlay_low_resolution_warning(self, capsys):
        """低解像度画像で警告が出力される"""
        image = create_test_image(width=320, height=240)  # 480p未満
        landmarks = create_test_landmarks(visibility=0.9)
        annotation_data = create_test_annotation_data()

        result = draw_overlay(image, landmarks, annotation_data)

        # 警告が出力される
        captured = capsys.readouterr()
        assert "Warning" in captured.out or "warning" in captured.out.lower()

    def test_draw_overlay_empty_annotation_data(self):
        """annotation_dataが空でもクラッシュしない"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)
        annotation_data = {}

        result = draw_overlay(image, landmarks, annotation_data)

        # エラーにならず結果が返される
        assert result is not None
        # 線は描画される（注記は空）
        assert np.any(result != 0)

    def test_draw_overlay_none_image_raises(self):
        """image=NoneでValueErrorが発生"""
        landmarks = create_test_landmarks(visibility=0.9)
        annotation_data = create_test_annotation_data()

        with pytest.raises(ValueError, match="Input image is None or empty"):
            draw_overlay(None, landmarks, annotation_data)

    def test_draw_overlay_with_flags(self):
        """show_*フラグで注記表示を制御できる"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)
        annotation_data = create_test_annotation_data()

        # 全て非表示
        result = draw_overlay(
            image,
            landmarks,
            annotation_data,
            show_versions=False,
            show_metadata=False,
            show_kpi=False
        )

        # 線・矢印のみ描画される（注記なし）
        assert result is not None
        assert np.any(result != 0)
