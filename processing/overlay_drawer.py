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

# CRITICAL: 描画色定義（BGR形式、ハンドオーバー仕様）
COLOR_SHOULDER_LINE = (255, 0, 0)    # 青（ハンドオーバー：青）
COLOR_PELVIS_LINE = (0, 255, 0)      # 緑（ハンドオーバー：緑）
COLOR_TORSO_AXIS = (0, 0, 255)       # 赤（ハンドオーバー：赤）
COLOR_ROTATION_ARROW = (0, 255, 255)  # 黄（ハンドオーバー：黄）

THICKNESS_LINE = 3  # 肩線・骨盤線の太さ（ハンドオーバー：3px）
THICKNESS_AXIS = 2  # 体幹軸の太さ（ハンドオーバー：2px）


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


def draw_shoulder_line(
    image: np.ndarray,
    landmarks: List[Dict],
    min_visibility: float = 0.5
) -> bool:
    """
    What: 肩線を描画（左肩→右肩）
    Why: 肩の水平性評価の視覚化
    Design Decision: 青色、太さ3px（ハンドオーバー仕様）

    Args:
        image: 描画対象画像（変更される）
        landmarks: ランドマークリスト（33点）
        min_visibility: 最小visibility

    Returns:
        描画成功時True、スキップ時False

    CRITICAL: 左右どちらかのランドマークが欠損時はスキップ、警告ログなし
    """
    left_shoulder = get_landmark_safe(landmarks, LEFT_SHOULDER, min_visibility)
    right_shoulder = get_landmark_safe(landmarks, RIGHT_SHOULDER, min_visibility)

    if left_shoulder is None or right_shoulder is None:
        return False

    h, w = image.shape[:2]
    pt1 = normalize_to_pixel(left_shoulder, w, h)
    pt2 = normalize_to_pixel(right_shoulder, w, h)

    cv2.line(image, pt1, pt2, COLOR_SHOULDER_LINE, THICKNESS_LINE)
    return True


def draw_pelvis_line(
    image: np.ndarray,
    landmarks: List[Dict],
    min_visibility: float = 0.5
) -> bool:
    """
    What: 骨盤線を描画（左腰→右腰）
    Why: 骨盤の水平性評価の視覚化
    Design Decision: 緑色、太さ3px（ハンドオーバー仕様）

    Args:
        image: 描画対象画像（変更される）
        landmarks: ランドマークリスト（33点）
        min_visibility: 最小visibility

    Returns:
        描画成功時True、スキップ時False

    CRITICAL: 左右どちらかのランドマークが欠損時はスキップ
    """
    left_hip = get_landmark_safe(landmarks, LEFT_HIP, min_visibility)
    right_hip = get_landmark_safe(landmarks, RIGHT_HIP, min_visibility)

    if left_hip is None or right_hip is None:
        return False

    h, w = image.shape[:2]
    pt1 = normalize_to_pixel(left_hip, w, h)
    pt2 = normalize_to_pixel(right_hip, w, h)

    cv2.line(image, pt1, pt2, COLOR_PELVIS_LINE, THICKNESS_LINE)
    return True


def draw_torso_axis(
    image: np.ndarray,
    landmarks: List[Dict],
    min_visibility: float = 0.5
) -> bool:
    """
    What: 体幹軸を描画（肩線中点→骨盤線中点）
    Why: 体幹の傾き・回旋評価の視覚化
    Design Decision: 赤色、太さ2px、破線スタイル（ハンドオーバー仕様）

    Args:
        image: 描画対象画像（変更される）
        landmarks: ランドマークリスト（33点）
        min_visibility: 最小visibility

    Returns:
        描画成功時True、スキップ時False

    CRITICAL: 肩2点・腰2点のいずれか欠損時はスキップ
    """
    left_shoulder = get_landmark_safe(landmarks, LEFT_SHOULDER, min_visibility)
    right_shoulder = get_landmark_safe(landmarks, RIGHT_SHOULDER, min_visibility)
    left_hip = get_landmark_safe(landmarks, LEFT_HIP, min_visibility)
    right_hip = get_landmark_safe(landmarks, RIGHT_HIP, min_visibility)

    if any(lm is None for lm in [left_shoulder, right_shoulder, left_hip, right_hip]):
        return False

    h, w = image.shape[:2]

    # 肩線中点
    shoulder_left_px = normalize_to_pixel(left_shoulder, w, h)
    shoulder_right_px = normalize_to_pixel(right_shoulder, w, h)
    shoulder_mid = calculate_midpoint(shoulder_left_px, shoulder_right_px)

    # 骨盤線中点
    hip_left_px = normalize_to_pixel(left_hip, w, h)
    hip_right_px = normalize_to_pixel(right_hip, w, h)
    pelvis_mid = calculate_midpoint(hip_left_px, hip_right_px)

    # 破線描画（OpenCV: lineType=cv2.LINE_AA + 手動破線）
    # PHASE 2: 手動破線実装は後回し、まず実線で描画
    cv2.line(image, shoulder_mid, pelvis_mid, COLOR_TORSO_AXIS, THICKNESS_AXIS)
    return True
