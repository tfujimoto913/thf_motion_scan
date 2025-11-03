"""
Purpose: Rep選定画像へのオーバーレイ描画処理
Responsibility: MediaPipeランドマークから肩線・骨盤線・体幹軸・回旋矢印を描画、注記配置
Dependencies: cv2, numpy, build_rep_annotation
Created: 2025-11-04 by Claude
Decision Log: Phase 5 - Overlay描画実装

CRITICAL: 元画像を変更しない、ランドマーク欠損時もエラーにしない
"""
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
import math

# CRITICAL: MediaPipeランドマークインデックス（削除禁止）
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_HIP = 23
RIGHT_HIP = 24


def normalize_to_pixel(
    landmark: Dict[str, float],
    image_width: int,
    image_height: int
) -> Tuple[int, int]:
    """
    What: MediaPipe正規化座標→画像ピクセル座標変換
    Why: OpenCV描画にはピクセル座標が必要
    Design Decision: 整数座標に変換、境界チェックなし（OpenCVが自動クリップ）

    Args:
        landmark: {'x': float [0,1], 'y': float [0,1], 'z': float, 'visibility': float}
        image_width: 画像幅（ピクセル）
        image_height: 画像高さ（ピクセル）

    Returns:
        (x_pixel, y_pixel): ピクセル座標

    CRITICAL: x/yは正規化座標[0,1]、境界外の値も受け入れる
    """
    x = int(landmark['x'] * image_width)
    y = int(landmark['y'] * image_height)
    return (x, y)


def get_landmark_safe(
    landmarks: List[Dict],
    index: int,
    min_visibility: float = 0.5
) -> Optional[Dict[str, float]]:
    """
    What: ランドマークを安全に取得（欠損・低visibility時はNone）
    Why: エラーハンドリング、低品質ランドマークのスキップ
    Design Decision: visibilityしきい値はデフォルト0.5（ハンドオーバー仕様）

    Args:
        landmarks: ランドマークリスト（33点）
        index: ランドマークインデックス（0-32）
        min_visibility: 最小visibility（これ未満はNone）

    Returns:
        landmark dict or None

    CRITICAL: 範囲外アクセス・None・低visibilityを全てNoneで返す
    """
    if index < 0 or index >= len(landmarks):
        return None

    landmark = landmarks[index]
    if landmark is None:
        return None

    if landmark.get('visibility', 0.0) < min_visibility:
        return None

    return landmark


def calculate_midpoint(
    pt1: Tuple[int, int],
    pt2: Tuple[int, int]
) -> Tuple[int, int]:
    """
    What: 2点の中点を計算
    Why: 体幹軸描画で肩線中点・骨盤線中点が必要
    Design Decision: 整数除算で中点を求める

    Args:
        pt1, pt2: ピクセル座標

    Returns:
        中点座標
    """
    mid_x = (pt1[0] + pt2[0]) // 2
    mid_y = (pt1[1] + pt2[1]) // 2
    return (mid_x, mid_y)
