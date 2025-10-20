"""
Purpose: 身体スケール正規化処理
Responsibility: ランドマーク座標から身体基準距離を計算し、個人差・カメラ距離依存性を排除
Dependencies: numpy, config.json
Created: 2025-10-19 by Claude
Decision Log: ADR-003

CRITICAL: NaN保持必須（列削除禁止）、config.json normalization設定参照
"""
import numpy as np
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path


class BodyNormalizer:
    """
    What: 身体スケール正規化クラス
    Why: 個人差（身長・体格）とカメラ距離による測定値の変動を吸収
    Design Decision: MediaPipeランドマーク間距離を基準値として使用（ADR-003）

    CRITICAL: config.json依存、NaN処理はpreserveモード必須
    """

    # CRITICAL: MediaPipeランドマークインデックス定義（削除禁止）
    # https://google.github.io/mediapipe/solutions/pose.html
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self, config_path: str = 'config.json'):
        """
        What: config.json読み込みと正規化設定初期化
        Why: 正規化基準の一元管理（ADR-003）
        Design Decision: デフォルトパスでルート直下config.json参照

        CRITICAL: config_path変更時は全テスト更新必須
        """
        # PHASE CORE LOGIC: config.json読み込み
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"config.json not found: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        # 正規化設定を取得
        self.normalization_config = self.config.get('normalization', {})

    def calculate_distance(self, point1: Dict, point2: Dict) -> Optional[float]:
        """
        What: 2点間のユークリッド距離計算（3D空間）
        Why: 身体基準距離計算の基本関数
        Design Decision: x, y, z座標を使用し3D距離を計算（ADR-003）

        Args:
            point1: {'x': float, 'y': float, 'z': float, 'visibility': float}
            point2: {'x': float, 'y': float, 'z': float, 'visibility': float}

        Returns:
            float: 距離、計算不可の場合はNone

        CRITICAL: NaN入力時はNoneを返す（列削除禁止）
        """
        try:
            # CRITICAL: NaN/None チェック
            if any(key not in point1 or key not in point2 for key in ['x', 'y', 'z']):
                return None

            x1, y1, z1 = point1['x'], point1['y'], point1['z']
            x2, y2, z2 = point2['x'], point2['y'], point2['z']

            # NaNチェック
            if any(np.isnan([x1, y1, z1, x2, y2, z2])):
                return None

            # 3D距離計算
            distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

            return float(distance)

        except (KeyError, TypeError, ValueError):
            # CRITICAL: エラー時はNoneを返す（データ保持）
            return None

    def calculate_shoulder_width(self, landmarks: List[Dict]) -> Optional[float]:
        """
        What: 肩幅計算（landmarks 11-12間距離）
        Why: 上半身動作の正規化基準（upper_body_swing, push_pull）
        Design Decision: LEFT_SHOULDER - RIGHT_SHOULDER 距離（ADR-003）

        Args:
            landmarks: ランドマークリスト（33個想定）

        Returns:
            float: 肩幅、計算不可の場合はNone

        CRITICAL: landmarks不足時はNoneを返す（エラー投げない）
        """
        # PHASE CORE LOGIC: landmarks 11-12 distance
        if len(landmarks) <= max(self.LEFT_SHOULDER, self.RIGHT_SHOULDER):
            return None

        left_shoulder = landmarks[self.LEFT_SHOULDER]
        right_shoulder = landmarks[self.RIGHT_SHOULDER]

        return self.calculate_distance(left_shoulder, right_shoulder)

    def calculate_pelvis_width(self, landmarks: List[Dict]) -> Optional[float]:
        """
        What: 骨盤幅計算（landmarks 23-24間距離）
        Why: 下半身動作の正規化基準（skater_lunge, cross_step）
        Design Decision: LEFT_HIP - RIGHT_HIP 距離（ADR-003）

        Args:
            landmarks: ランドマークリスト（33個想定）

        Returns:
            float: 骨盤幅、計算不可の場合はNone

        CRITICAL: landmarks不足時はNoneを返す（エラー投げない）
        """
        # PHASE CORE LOGIC: landmarks 23-24 distance
        if len(landmarks) <= max(self.LEFT_HIP, self.RIGHT_HIP):
            return None

        left_hip = landmarks[self.LEFT_HIP]
        right_hip = landmarks[self.RIGHT_HIP]

        return self.calculate_distance(left_hip, right_hip)

    def calculate_leg_length(self, landmarks: List[Dict]) -> Optional[float]:
        """
        What: 下肢長計算（hip to ankle平均距離）
        Why: 脚動作の正規化基準（stride_mimic, jump_landing）
        Design Decision: 左右脚の平均値で個人差吸収（ADR-003）

        Args:
            landmarks: ランドマークリスト（33個想定）

        Returns:
            float: 下肢長、計算不可の場合はNone

        CRITICAL: 片側のみ計算可能な場合はその値を使用（両側NaNの場合のみNone）
        """
        # PHASE CORE LOGIC: average hip to ankle distance
        if len(landmarks) <= max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
            return None

        # 左脚長計算
        left_leg_length = self.calculate_distance(
            landmarks[self.LEFT_HIP],
            landmarks[self.LEFT_ANKLE]
        )

        # 右脚長計算
        right_leg_length = self.calculate_distance(
            landmarks[self.RIGHT_HIP],
            landmarks[self.RIGHT_ANKLE]
        )

        # CRITICAL: NaN処理（両側使用可能なら平均、片側のみなら単独値）
        if left_leg_length is not None and right_leg_length is not None:
            return float(np.mean([left_leg_length, right_leg_length]))
        elif left_leg_length is not None:
            return left_leg_length
        elif right_leg_length is not None:
            return right_leg_length
        else:
            return None

    def calculate_base_width(self, landmarks: List[Dict]) -> Optional[float]:
        """
        What: 基準幅計算（max(shoulder_width, pelvis_width)）
        Why: 全身動作の統一正規化基準（skater_lunge, cross_step）
        Design Decision: 肩幅と骨盤幅の大きい方を採用（ADR-003）

        Args:
            landmarks: ランドマークリスト（33個想定）

        Returns:
            float: 基準幅、計算不可の場合はNone

        CRITICAL: 片側のみ計算可能な場合はその値を使用
        """
        # PHASE CORE LOGIC: max(shoulder_width, pelvis_width)
        shoulder_width = self.calculate_shoulder_width(landmarks)
        pelvis_width = self.calculate_pelvis_width(landmarks)

        # CRITICAL: NaN処理
        if shoulder_width is not None and pelvis_width is not None:
            return float(max(shoulder_width, pelvis_width))
        elif shoulder_width is not None:
            return shoulder_width
        elif pelvis_width is not None:
            return pelvis_width
        else:
            return None

    def normalize_frame_data(self, landmarks: List[Dict]) -> Dict[str, Optional[float]]:
        """
        What: 1フレーム分のランドマークから全正規化基準値を計算
        Why: 評価器で繰り返し呼び出すための統合インターフェース
        Design Decision: 辞書形式で全基準値を一括返却（ADR-003）

        Args:
            landmarks: ランドマークリスト（33個想定）

        Returns:
            Dict: {
                'shoulder_width': Optional[float],
                'pelvis_width': Optional[float],
                'leg_length': Optional[float],
                'base_width': Optional[float]
            }

        CRITICAL: 計算不可の値はNoneを保持（キー削除禁止）
        """
        return {
            'shoulder_width': self.calculate_shoulder_width(landmarks),
            'pelvis_width': self.calculate_pelvis_width(landmarks),
            'leg_length': self.calculate_leg_length(landmarks),
            'base_width': self.calculate_base_width(landmarks)
        }

    def normalize_landmarks_sequence(
        self,
        landmarks_data: List[Dict]
    ) -> Tuple[Dict[str, float], List[Dict[str, Optional[float]]]]:
        """
        What: 全フレームの正規化基準値計算と代表値抽出
        Why: 動画全体の平均的な身体スケールで正規化
        Design Decision: 各フレームで計算後、中央値を代表値とする（ADR-003）

        Args:
            landmarks_data: フレームごとのランドマークデータ
                [{'frame': int, 'timestamp': float, 'landmarks': [...]}, ...]

        Returns:
            Tuple[Dict, List]:
                - 代表値: {'shoulder_width': float, 'pelvis_width': float, ...}
                - フレーム別値: [{'shoulder_width': Optional[float], ...}, ...]

        CRITICAL: 代表値はNaN除外後の中央値（外れ値に強い）
        """
        frame_normalizations = []

        # PHASE CORE LOGIC: 各フレームで正規化基準計算
        for frame_data in landmarks_data:
            landmarks = frame_data.get('landmarks', [])
            norm_values = self.normalize_frame_data(landmarks)
            frame_normalizations.append(norm_values)

        # CRITICAL: 代表値計算（中央値使用）
        representative_values = {}

        for key in ['shoulder_width', 'pelvis_width', 'leg_length', 'base_width']:
            # NaN除外
            valid_values = [
                frame[key] for frame in frame_normalizations
                if frame[key] is not None
            ]

            if valid_values:
                # 中央値計算（外れ値に強い）
                representative_values[key] = float(np.median(valid_values))
            else:
                # CRITICAL: 全フレームでNaNの場合はNaN保持
                representative_values[key] = np.nan

        return representative_values, frame_normalizations


def normalize_value(
    value: float,
    reference: Optional[float]
) -> Optional[float]:
    """
    What: 測定値を基準値で正規化（比率計算）
    Why: 個人差を排除した無次元値に変換
    Design Decision: value / reference の単純比（ADR-003）

    Args:
        value: 測定値（例: ステップ幅）
        reference: 基準値（例: base_width）

    Returns:
        float: 正規化値、計算不可の場合はNone

    CRITICAL: reference=0またはNoneの場合はNoneを返す（ゼロ除算回避）
    """
    # CRITICAL: NaN/None/ゼロチェック
    if reference is None or np.isnan(reference) or reference == 0:
        return None

    if value is None or np.isnan(value):
        return None

    try:
        normalized = value / reference
        return float(normalized)
    except (TypeError, ZeroDivisionError):
        return None
