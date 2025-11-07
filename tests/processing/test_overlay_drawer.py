"""
Purpose: Unit tests for processing.overlay_drawer coordinate conversion utilities
Responsibility: Validate MediaPipe coordinate transformation and safe landmark access
Dependencies: pytest
Created: 2025-11-04 by Claude
Decision Log: Phase 5 - Overlay描画実装 Stage 1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from processing.overlay_drawer import (
    calculate_midpoint,
    get_landmark_safe,
    normalize_to_pixel,
)


class TestNormalizeToPixel:
    def test_center_coordinate(self):
        """正規化座標(0.5, 0.5)が画像中心に変換される"""
        landmark = {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}
        result = normalize_to_pixel(landmark, image_width=640, image_height=480)
        assert result == (320, 240)

    def test_top_left_corner(self):
        """正規化座標(0, 0)が左上に変換される"""
        landmark = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'visibility': 1.0}
        result = normalize_to_pixel(landmark, image_width=640, image_height=480)
        assert result == (0, 0)

    def test_bottom_right_corner(self):
        """正規化座標(1, 1)が右下に変換される"""
        landmark = {'x': 1.0, 'y': 1.0, 'z': 0.0, 'visibility': 1.0}
        result = normalize_to_pixel(landmark, image_width=640, image_height=480)
        assert result == (640, 480)

    def test_fractional_coordinates(self):
        """小数座標が整数ピクセルに変換される"""
        landmark = {'x': 0.333, 'y': 0.666, 'z': 0.0, 'visibility': 1.0}
        result = normalize_to_pixel(landmark, image_width=600, image_height=400)
        # 0.333 * 600 = 199.8 → 199
        # 0.666 * 400 = 266.4 → 266
        assert result == (199, 266)


class TestGetLandmarkSafe:
    def test_valid_landmark_high_visibility(self):
        """visibility=0.9のランドマークが取得成功"""
        landmarks = [
            {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.9}
            for _ in range(33)
        ]
        result = get_landmark_safe(landmarks, index=11, min_visibility=0.5)
        assert result is not None
        assert result['visibility'] == 0.9

    def test_low_visibility_returns_none(self):
        """visibility=0.3のランドマークがNoneを返す"""
        landmarks = [
            {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.3}
            for _ in range(33)
        ]
        result = get_landmark_safe(landmarks, index=11, min_visibility=0.5)
        assert result is None

    def test_out_of_range_index_returns_none(self):
        """範囲外インデックス(50)がNoneを返す"""
        landmarks = [
            {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.9}
            for _ in range(33)
        ]
        result = get_landmark_safe(landmarks, index=50, min_visibility=0.5)
        assert result is None

    def test_negative_index_returns_none(self):
        """負のインデックスがNoneを返す"""
        landmarks = [
            {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.9}
            for _ in range(33)
        ]
        result = get_landmark_safe(landmarks, index=-1, min_visibility=0.5)
        assert result is None

    def test_none_landmark_returns_none(self):
        """Noneランドマークが安全にNoneを返す"""
        landmarks = [None for _ in range(33)]
        result = get_landmark_safe(landmarks, index=11, min_visibility=0.5)
        assert result is None


class TestCalculateMidpoint:
    def test_midpoint_of_two_points(self):
        """2点(100,100)と(200,200)の中点が(150,150)"""
        pt1 = (100, 100)
        pt2 = (200, 200)
        result = calculate_midpoint(pt1, pt2)
        assert result == (150, 150)

    def test_midpoint_horizontal_line(self):
        """水平線上の中点"""
        pt1 = (0, 100)
        pt2 = (400, 100)
        result = calculate_midpoint(pt1, pt2)
        assert result == (200, 100)

    def test_midpoint_vertical_line(self):
        """垂直線上の中点"""
        pt1 = (100, 0)
        pt2 = (100, 300)
        result = calculate_midpoint(pt1, pt2)
        assert result == (100, 150)

    def test_midpoint_odd_coordinates(self):
        """奇数座標の中点（整数除算）"""
        pt1 = (1, 1)
        pt2 = (4, 4)
        result = calculate_midpoint(pt1, pt2)
        # (1+4)//2 = 2, (1+4)//2 = 2
        assert result == (2, 2)
