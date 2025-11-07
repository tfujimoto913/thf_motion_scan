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

# CRITICAL: 注記配置定義（ハンドオーバー仕様）
ANNOTATION_PADDING = 10  # 画像端からの余白（px）
ANNOTATION_LINE_HEIGHT = 30  # 行間（px）
ANNOTATION_FONT = cv2.FONT_HERSHEY_SIMPLEX
ANNOTATION_FONT_SCALE = 0.6
ANNOTATION_FONT_COLOR = (255, 255, 255)  # 白
ANNOTATION_FONT_THICKNESS = 2


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


def draw_rotation_indicator(
    image: np.ndarray,
    landmarks: List[Dict],
    rotation_angle: Optional[float] = None,
    min_visibility: float = 0.5
) -> bool:
    """
    What: 体幹回旋インジケーター矢印を描画
    Why: 回旋方向の視覚化（左右どちらに回旋しているか）
    Design Decision: 体幹軸に垂直、黄色矢印（ハンドオーバー仕様）

    Args:
        image: 描画対象画像（変更される）
        landmarks: ランドマークリスト（33点）
        rotation_angle: 回旋角度（deg、正=右回旋、負=左回旋）Noneの場合は自動計算
        min_visibility: 最小visibility

    Returns:
        描画成功時True、スキップ時False

    CRITICAL:
    - rotation_angle=Noneの場合、肩線と骨盤線のずれから回旋方向を推定
    - 矢印は体幹軸中点から垂直方向に描画
    - 回旋角度が小さい（<5deg）場合はスキップ
    """
    left_shoulder = get_landmark_safe(landmarks, LEFT_SHOULDER, min_visibility)
    right_shoulder = get_landmark_safe(landmarks, RIGHT_SHOULDER, min_visibility)
    left_hip = get_landmark_safe(landmarks, LEFT_HIP, min_visibility)
    right_hip = get_landmark_safe(landmarks, RIGHT_HIP, min_visibility)

    if any(lm is None for lm in [left_shoulder, right_shoulder, left_hip, right_hip]):
        return False

    h, w = image.shape[:2]

    # 肩線中点・骨盤線中点
    shoulder_left_px = normalize_to_pixel(left_shoulder, w, h)
    shoulder_right_px = normalize_to_pixel(right_shoulder, w, h)
    shoulder_mid = calculate_midpoint(shoulder_left_px, shoulder_right_px)

    hip_left_px = normalize_to_pixel(left_hip, w, h)
    hip_right_px = normalize_to_pixel(right_hip, w, h)
    pelvis_mid = calculate_midpoint(hip_left_px, hip_right_px)

    torso_mid = calculate_midpoint(shoulder_mid, pelvis_mid)

    # 回旋角度計算（rotation_angle=Noneの場合）
    if rotation_angle is None:
        # 肩線の角度
        shoulder_dx = shoulder_right_px[0] - shoulder_left_px[0]
        shoulder_dy = shoulder_right_px[1] - shoulder_left_px[1]
        shoulder_angle = math.degrees(math.atan2(shoulder_dy, shoulder_dx))

        # 骨盤線の角度
        hip_dx = hip_right_px[0] - hip_left_px[0]
        hip_dy = hip_right_px[1] - hip_left_px[1]
        hip_angle = math.degrees(math.atan2(hip_dy, hip_dx))

        # 回旋角度（肩-骨盤のずれ）
        rotation_angle = shoulder_angle - hip_angle

    # 小さい回旋はスキップ
    if abs(rotation_angle) < 5.0:
        return False

    # 体幹軸の角度（垂直方向を計算）
    torso_dx = pelvis_mid[0] - shoulder_mid[0]
    torso_dy = pelvis_mid[1] - shoulder_mid[1]
    torso_angle_rad = math.atan2(torso_dy, torso_dx)

    # 垂直方向（右回旋なら右、左回旋なら左）
    perpendicular_angle = torso_angle_rad + (math.pi / 2 if rotation_angle > 0 else -math.pi / 2)

    # 矢印の長さ（画像幅の10%）
    arrow_length = int(w * 0.1)
    arrow_end_x = int(torso_mid[0] + arrow_length * math.cos(perpendicular_angle))
    arrow_end_y = int(torso_mid[1] + arrow_length * math.sin(perpendicular_angle))
    arrow_end = (arrow_end_x, arrow_end_y)

    # 矢印描画
    cv2.arrowedLine(
        image,
        torso_mid,
        arrow_end,
        COLOR_ROTATION_ARROW,
        THICKNESS_AXIS,
        tipLength=0.3
    )
    return True


def draw_versions_annotation(
    image: np.ndarray,
    versions: Dict[str, str]
) -> None:
    """
    What: versions注記を左上に描画
    Why: トレーサビリティ確保（rules/thresholds/normalizationのバージョン）
    Design Decision: 左上、白文字、3行（ハンドオーバー仕様）

    Args:
        image: 描画対象画像（変更される）
        versions: {'rules_version': '2.1.0', 'thresholds_version': '1.0.0', ...}

    CRITICAL: versionsが空の場合はスキップ（エラーにしない）
    """
    if not versions:
        return

    x = ANNOTATION_PADDING
    y = ANNOTATION_PADDING + ANNOTATION_LINE_HEIGHT

    lines = [
        f"Rules: {versions.get('rules_version', 'N/A')}",
        f"Thresholds: {versions.get('thresholds_version', 'N/A')}",
        f"Norm: {versions.get('normalization_version', 'N/A')}"
    ]

    for line in lines:
        cv2.putText(
            image,
            line,
            (x, y),
            ANNOTATION_FONT,
            ANNOTATION_FONT_SCALE,
            ANNOTATION_FONT_COLOR,
            ANNOTATION_FONT_THICKNESS
        )
        y += ANNOTATION_LINE_HEIGHT


def draw_metadata_annotation(
    image: np.ndarray,
    metadata: Dict[str, Any]
) -> None:
    """
    What: メタデータ注記を左下に描画
    Why: N/A率、有効KPI数、選定理由の表示
    Design Decision: 左下、白文字、3行（ハンドオーバー仕様）

    Args:
        image: 描画対象画像（変更される）
        metadata: {'na_rate': 0.2, 'valid_kpi_count': 6, 'selection_reason': 'best'}

    CRITICAL: metadataが空の場合はスキップ
    """
    if not metadata:
        return

    h = image.shape[0]
    x = ANNOTATION_PADDING
    y = h - ANNOTATION_PADDING - ANNOTATION_LINE_HEIGHT * 3

    lines = [
        f"Reason: {metadata.get('selection_reason', 'N/A')}",
        f"Valid KPIs: {metadata.get('valid_kpi_count', 0)}/{metadata.get('total_kpi_count', 8)}",
        f"N/A Rate: {metadata.get('na_rate', 0.0):.1%}"
    ]

    for line in lines:
        cv2.putText(
            image,
            line,
            (x, y),
            ANNOTATION_FONT,
            ANNOTATION_FONT_SCALE,
            ANNOTATION_FONT_COLOR,
            ANNOTATION_FONT_THICKNESS
        )
        y += ANNOTATION_LINE_HEIGHT


def draw_kpi_annotation(
    image: np.ndarray,
    kpi_values: Dict[str, float],
    kpi_classes: Dict[str, str],
    kpi_p_values: Dict[str, float],
    max_kpis: int = 5
) -> None:
    """
    What: 主要KPI値とクラスを右上に描画
    Why: 評価結果の視覚化
    Design Decision: 右上、白文字、最大5KPI表示（ハンドオーバー仕様）

    Args:
        image: 描画対象画像（変更される）
        kpi_values: {'B1_core_stability': 4.2, 'B4_pelvis_horizontal': 3.8, ...}
        kpi_classes: {'B1_core_stability': 'A', 'B4_pelvis_horizontal': 'B', ...}
        kpi_p_values: {'B1_core_stability': 0.92, 'B4_pelvis_horizontal': 0.85, ...}
        max_kpis: 表示するKPI数上限

    CRITICAL:
    - kpi_values/classes/p_valuesが空の場合はスキップ
    - 上位max_kpis個のみ表示（値の大きい順）
    """
    if not kpi_values:
        return

    # 値の大きい順にソート（Noneは0として扱う）
    sorted_kpis = sorted(
        kpi_values.items(),
        key=lambda x: x[1] if x[1] is not None else 0,
        reverse=True
    )
    top_kpis = sorted_kpis[:max_kpis]

    h, w = image.shape[:2]
    x = w - 350  # 右端から350px左
    y = ANNOTATION_PADDING + ANNOTATION_LINE_HEIGHT

    for kpi_name, value in top_kpis:
        kpi_class = kpi_classes.get(kpi_name, 'N/A')
        p_value = kpi_p_values.get(kpi_name, 0.0)

        # 短縮名（B1, B4等）
        short_name = kpi_name.split('_')[0] if '_' in kpi_name else kpi_name

        if value is not None:
            line = f"{short_name}: {value:.1f} [{kpi_class}] p={p_value:.2f}"
        else:
            line = f"{short_name}: N/A"

        cv2.putText(
            image,
            line,
            (x, y),
            ANNOTATION_FONT,
            ANNOTATION_FONT_SCALE,
            ANNOTATION_FONT_COLOR,
            ANNOTATION_FONT_THICKNESS
        )
        y += ANNOTATION_LINE_HEIGHT


def draw_overlay(
    image: np.ndarray,
    landmarks: List[Dict],
    annotation_data: Dict[str, Any],
    show_versions: bool = True,
    show_metadata: bool = True,
    show_kpi: bool = True,
    min_visibility: float = 0.5,
    rotation_angle: Optional[float] = None
) -> np.ndarray:
    """
    What: 画像にオーバーレイを描画（全要素統合）
    Why: rep選定画像への視覚的フィードバック提供
    Design Decision: 元画像を変更しない、エラー時もクラッシュしない（ハンドオーバー仕様）

    Args:
        image: 元画像（RGB or BGR）
        landmarks: MediaPipeランドマークリスト（33点）
        annotation_data: build_rep_annotation()の出力
        show_versions: versions注記表示フラグ
        show_metadata: metadata注記表示フラグ
        show_kpi: KPI注記表示フラグ
        min_visibility: 最小visibility（これ未満はスキップ）
        rotation_angle: 回旋角度（Noneの場合は自動計算）

    Returns:
        描画済み画像（元画像のコピー）

    CRITICAL:
    - 元画像は変更しない（コピーして描画）
    - ランドマーク欠損・低visibilityは警告ログなし、該当要素をスキップ
    - 最低解像度チェック（480p未満は警告ログ）

    Raises:
        ValueError: imageがNone or 空配列の場合のみ
    """
    if image is None or image.size == 0:
        raise ValueError("Input image is None or empty")

    # 元画像をコピー
    annotated = image.copy()

    # 最低解像度チェック
    h, w = annotated.shape[:2]
    if h < 480 or w < 640:
        # CRITICAL: 警告ログのみ、処理は継続
        print(f"Warning: Low resolution ({w}x{h}), annotations may be hard to read")

    # 線描画
    draw_shoulder_line(annotated, landmarks, min_visibility)
    draw_pelvis_line(annotated, landmarks, min_visibility)
    draw_torso_axis(annotated, landmarks, min_visibility)

    # 矢印描画
    draw_rotation_indicator(annotated, landmarks, rotation_angle, min_visibility)

    # 注記描画
    if show_versions:
        versions = annotation_data.get('versions', {})
        draw_versions_annotation(annotated, versions)

    if show_metadata:
        metadata = annotation_data.get('metadata', {})
        draw_metadata_annotation(annotated, metadata)

    if show_kpi:
        kpi_values = annotation_data.get('kpi_values', {})
        kpi_classes = annotation_data.get('kpi_classes', {})
        kpi_p_values = annotation_data.get('kpi_p_values', {})
        draw_kpi_annotation(annotated, kpi_values, kpi_classes, kpi_p_values)

    return annotated
