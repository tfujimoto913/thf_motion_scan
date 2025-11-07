"""
Purpose: Unit tests for processing.overlay_drawer line drawing functions
Responsibility: Validate shoulder/pelvis lines and torso axis drawing
Dependencies: pytest, numpy, cv2
Created: 2025-11-04 by Claude
Decision Log: Phase 5 - Overlay描画実装 Stage 2
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
    draw_pelvis_line,
    draw_shoulder_line,
    draw_torso_axis,
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


class TestDrawShoulderLine:
    def test_draw_shoulder_line_success(self):
        """肩線が正常に描画される"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)

        result = draw_shoulder_line(image, landmarks, min_visibility=0.5)

        assert result is True
        # 画像が変更されたか確認（黒背景から変化）
        assert np.any(image != 0)

    def test_draw_shoulder_line_skip_missing_left_landmark(self):
        """左肩欠損時にスキップ（False返却）"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)
        landmarks[LEFT_SHOULDER] = None  # 左肩を欠損

        result = draw_shoulder_line(image, landmarks, min_visibility=0.5)

        assert result is False
        # 画像が変更されていないか確認
        assert np.all(image == 0)

    def test_draw_shoulder_line_skip_low_visibility(self):
        """低visibility時にスキップ"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.3)  # 全て低visibility

        result = draw_shoulder_line(image, landmarks, min_visibility=0.5)

        assert result is False
        assert np.all(image == 0)


class TestDrawPelvisLine:
    def test_draw_pelvis_line_success(self):
        """骨盤線が正常に描画される"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)

        result = draw_pelvis_line(image, landmarks, min_visibility=0.5)

        assert result is True
        assert np.any(image != 0)

    def test_draw_pelvis_line_skip_missing_right_hip(self):
        """右腰欠損時にスキップ"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)
        landmarks[RIGHT_HIP] = None

        result = draw_pelvis_line(image, landmarks, min_visibility=0.5)

        assert result is False
        assert np.all(image == 0)

    def test_draw_pelvis_line_skip_low_visibility(self):
        """低visibility時にスキップ"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.3)

        result = draw_pelvis_line(image, landmarks, min_visibility=0.5)

        assert result is False
        assert np.all(image == 0)


class TestDrawTorsoAxis:
    def test_draw_torso_axis_success(self):
        """体幹軸が正常に描画される（肩中点→骨盤中点）"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)

        result = draw_torso_axis(image, landmarks, min_visibility=0.5)

        assert result is True
        assert np.any(image != 0)

    def test_draw_torso_axis_skip_partial_missing(self):
        """4点のうち1点でも欠損時にスキップ"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)
        landmarks[RIGHT_HIP] = None  # 右腰を欠損

        result = draw_torso_axis(image, landmarks, min_visibility=0.5)

        assert result is False
        assert np.all(image == 0)

    def test_draw_torso_axis_skip_low_visibility_one_point(self):
        """1点でも低visibility時にスキップ"""
        image = create_test_image()
        landmarks = create_test_landmarks(visibility=0.9)
        landmarks[LEFT_SHOULDER]['visibility'] = 0.3  # 左肩のみ低visibility

        result = draw_torso_axis(image, landmarks, min_visibility=0.5)

        assert result is False
        assert np.all(image == 0)
