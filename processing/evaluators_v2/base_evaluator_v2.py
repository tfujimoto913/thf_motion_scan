"""
Purpose: 8原則・237点満点評価システムの抽象基底クラス
Responsibility: 新評価体系の共通インターフェース定義
Dependencies: test_rules_v2.json
Created: 2025-10-30 by Claude
Decision Log: Phase A - 並行動作環境構築, Phase B - 8原則評価ロジック実装

CRITICAL: 既存BaseEvaluatorとは完全分離、8原則・局面別評価に対応
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import json
import numpy as np
from math import sqrt, acos, atan2, degrees


class BaseEvaluatorV2(ABC):
    """
    What: 8原則（B1-B8）・237点満点評価システムの基底クラス
    Why: 新評価体系の共通インターフェースを統一
    Design Decision: 並行動作方式、既存BaseEvaluatorとは完全分離

    CRITICAL: 既存のBaseEvaluatorには一切影響を与えない
    """

    # CRITICAL: MediaPipeランドマークインデックス定義（削除禁止）
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32

    def __init__(self, config_path: str = 'processing/evaluators_v2/config_v2/test_rules_v2.json'):
        """
        What: 8原則ルール読み込み
        Why: 237点満点システムの定義を取得
        Design Decision: test_rules_v2.json使用

        Args:
            config_path: test_rules_v2.jsonのパス

        CRITICAL: Phase B実装、8原則評価ロジック対応
        """
        self.config_path = Path(config_path)

        # PHASE B: ルール読み込み
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.rules = json.load(f)
        else:
            # フォールバック（テスト環境用）
            self.rules = {
                'version': 'v2.0',
                'scoring_system': {
                    'total_max_score': 237,
                    'section_a': {'max_score': 21},
                    'section_b': {'max_score': 216}
                },
                'principles': {}
            }

    @abstractmethod
    def evaluate(
        self,
        landmarks_data: List[Dict],
        **kwargs
    ) -> Dict:
        """
        What: 評価実行メソッド（抽象メソッド）
        Why: サブクラスで具体的な評価ロジックを実装
        Design Decision: 8原則・局面別評価に対応

        Args:
            landmarks_data: フレームごとのランドマークデータ
            **kwargs: 追加パラメータ（base_width, shoulder_width, leg_length等）

        Returns:
            Dict: {
                'version': 'v2',
                'total_score': int (0-237),
                'section_a': Dict,  # 21点
                'section_b': Dict,  # 216点（8原則）
                'phase_scores': Dict,  # Eccentric/Concentric別
                'details': str
            }

        CRITICAL: Phase Bで実装、Phase Aでは NotImplementedError
        """
        raise NotImplementedError(
            "Phase B で実装予定: 8原則・237点満点評価ロジック"
        )

    def _detect_phases(self, landmarks_data: List[Dict], joint_angles: List[float]) -> Dict:
        """
        What: 局面検出（Eccentric/Concentric）
        Why: 局面別評価のため
        Design Decision: 関節角度の変化から動作フェーズを自動検出

        Args:
            landmarks_data: フレームごとのランドマークデータ
            joint_angles: フレームごとの関節角度（例: 膝関節角度）

        Returns:
            Dict: {
                'eccentric': {'start_frame': int, 'end_frame': int, 'frames': List[int]},
                'concentric': {'start_frame': int, 'end_frame': int, 'frames': List[int]}
            }

        CRITICAL: サブクラスで種目ごとにオーバーライド可能
        """
        if not joint_angles or len(joint_angles) < 3:
            # デフォルト: 全フレームを両局面に含める
            return {
                'eccentric': {
                    'start_frame': 0,
                    'end_frame': len(landmarks_data) - 1,
                    'frames': list(range(len(landmarks_data)))
                },
                'concentric': {
                    'start_frame': 0,
                    'end_frame': len(landmarks_data) - 1,
                    'frames': list(range(len(landmarks_data)))
                }
            }

        # 関節角度の変化から局面を検出
        # Eccentric: 角度が減少（下降・曲がる）
        # Concentric: 角度が増加（上昇・伸びる）
        eccentric_frames = []
        concentric_frames = []

        for i in range(1, len(joint_angles)):
            angle_change = joint_angles[i] - joint_angles[i-1]

            if angle_change < -2:  # 角度減少（Eccentric）
                eccentric_frames.append(i)
            elif angle_change > 2:  # 角度増加（Concentric）
                concentric_frames.append(i)

        # フレーム範囲を決定
        if eccentric_frames:
            ecc_start = min(eccentric_frames)
            ecc_end = max(eccentric_frames)
        else:
            ecc_start = 0
            ecc_end = len(landmarks_data) // 2
            eccentric_frames = list(range(ecc_start, ecc_end))

        if concentric_frames:
            con_start = min(concentric_frames)
            con_end = max(concentric_frames)
        else:
            con_start = len(landmarks_data) // 2
            con_end = len(landmarks_data) - 1
            concentric_frames = list(range(con_start, con_end))

        return {
            'eccentric': {
                'start_frame': ecc_start,
                'end_frame': ecc_end,
                'frames': eccentric_frames
            },
            'concentric': {
                'start_frame': con_start,
                'end_frame': con_end,
                'frames': concentric_frames
            }
        }

    def _evaluate_principle(
        self,
        principle_id: str,
        landmarks_data: List[Dict],
        phase: str
    ) -> Dict:
        """
        What: 個別原則の評価
        Why: 各原則（B1-B8）ごとのスコア計算
        Design Decision: 原則IDベースで柔軟に対応

        Args:
            principle_id: 原則ID（例: "B1", "B2"）
            landmarks_data: ランドマークデータ
            phase: "eccentric" or "concentric"

        Returns:
            Dict: {
                'score': float,
                'max_score': float,
                'details': str
            }

        CRITICAL: サブクラスで具体的な評価ロジックを実装
        """
        raise NotImplementedError(
            f"Subclass must implement _evaluate_principle for {principle_id}"
        )

    # ==================== 共通ヘルパーメソッド ====================

    def _calculate_angle_3d(self, p1: Dict, p2: Dict, p3: Dict) -> float:
        """
        What: 3点から角度を計算（3D空間）
        Why: 関節角度の客観的計算
        Design Decision: MediaPipe正規化座標使用

        Args:
            p1, p2, p3: {'x': float, 'y': float, 'z': float}
            p2が頂点

        Returns:
            float: 角度（度数）

        CRITICAL: ゼロ除算保護、NaN/Inf チェック
        """
        try:
            # ベクトル計算
            v1 = np.array([p1['x'] - p2['x'], p1['y'] - p2['y'], p1['z'] - p2['z']])
            v2 = np.array([p3['x'] - p2['x'], p3['y'] - p2['y'], p3['z'] - p2['z']])

            # 内積とノルム
            dot_product = np.dot(v1, v2)
            norm_v1 = np.linalg.norm(v1)
            norm_v2 = np.linalg.norm(v2)

            # ゼロ除算保護
            if norm_v1 == 0 or norm_v2 == 0:
                return 0.0

            # 角度計算
            cos_angle = dot_product / (norm_v1 * norm_v2)
            cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 数値誤差対策
            angle_rad = np.arccos(cos_angle)
            angle_deg = np.degrees(angle_rad)

            return float(angle_deg)

        except Exception:
            return 0.0

    def _calculate_distance(self, p1: Dict, p2: Dict) -> float:
        """
        What: 2点間の距離計算（3D空間）
        Why: 体幹揺れ、高低差等の評価
        Design Decision: MediaPipe正規化座標使用

        Args:
            p1, p2: {'x': float, 'y': float, 'z': float}

        Returns:
            float: 距離

        CRITICAL: NaN/Inf チェック
        """
        try:
            dx = p1['x'] - p2['x']
            dy = p1['y'] - p2['y']
            dz = p1['z'] - p2['z']
            distance = sqrt(dx*dx + dy*dy + dz*dz)
            return float(distance)
        except Exception:
            return 0.0

    def _get_landmark(self, frame_data: Dict, index: int) -> Optional[Dict]:
        """
        What: ランドマーク取得
        Why: 安全なランドマークアクセス
        Design Decision: visibility閾値チェック

        Args:
            frame_data: フレームデータ
            index: ランドマークインデックス

        Returns:
            Dict or None: {'x', 'y', 'z', 'visibility'}

        CRITICAL: visibility < 0.5 の場合はNone返却
        """
        try:
            if 'landmarks' not in frame_data:
                return None

            landmarks = frame_data['landmarks']
            if index >= len(landmarks):
                return None

            landmark = landmarks[index]
            if landmark.get('visibility', 0) < 0.5:
                return None

            return landmark
        except Exception:
            return None

    # ==================== 8原則評価の共通ヘルパーメソッド ====================

    def _calculate_trunk_rotation(self, frame_data: Dict) -> float:
        """
        What: 体幹回旋角度を計算（B1: 体幹安定性）
        Why: 体幹の揺れを客観的に評価
        Design Decision: 左右肩・左右腰の平面から回旋角度を算出

        Returns:
            float: 回旋角度（度数）

        CRITICAL: NaN/Inf保護
        """
        left_shoulder = self._get_landmark(frame_data, self.LEFT_SHOULDER)
        right_shoulder = self._get_landmark(frame_data, self.RIGHT_SHOULDER)
        left_hip = self._get_landmark(frame_data, self.LEFT_HIP)
        right_hip = self._get_landmark(frame_data, self.RIGHT_HIP)

        if not all([left_shoulder, right_shoulder, left_hip, right_hip]):
            return 0.0

        # 肩ベクトルと腰ベクトルの角度差
        shoulder_vec = np.array([
            right_shoulder['x'] - left_shoulder['x'],
            right_shoulder['z'] - left_shoulder['z']
        ])
        hip_vec = np.array([
            right_hip['x'] - left_hip['x'],
            right_hip['z'] - left_hip['z']
        ])

        # 角度計算
        try:
            shoulder_angle = np.degrees(np.arctan2(shoulder_vec[1], shoulder_vec[0]))
            hip_angle = np.degrees(np.arctan2(hip_vec[1], hip_vec[0]))
            rotation = abs(shoulder_angle - hip_angle)
            return float(rotation)
        except Exception:
            return 0.0

    def _calculate_shoulder_height_diff(self, frame_data: Dict) -> float:
        """
        What: 左右肩の高低差を計算（B1: 体幹安定性）
        Why: 体幹の傾きを客観的に評価
        Design Decision: y座標の差分

        Returns:
            float: 高低差（正規化座標）

        CRITICAL: NaN/Inf保護
        """
        left_shoulder = self._get_landmark(frame_data, self.LEFT_SHOULDER)
        right_shoulder = self._get_landmark(frame_data, self.RIGHT_SHOULDER)

        if not all([left_shoulder, right_shoulder]):
            return 0.0

        height_diff = abs(left_shoulder['y'] - right_shoulder['y'])
        return float(height_diff)

    def _calculate_hip_height_diff(self, frame_data: Dict) -> float:
        """
        What: 左右腰の高低差を計算（B4: 骨盤水平維持）
        Why: 骨盤の傾きを客観的に評価
        Design Decision: y座標の差分

        Returns:
            float: 高低差（正規化座標）

        CRITICAL: NaN/Inf保護
        """
        left_hip = self._get_landmark(frame_data, self.LEFT_HIP)
        right_hip = self._get_landmark(frame_data, self.RIGHT_HIP)

        if not all([left_hip, right_hip]):
            return 0.0

        height_diff = abs(left_hip['y'] - right_hip['y'])
        return float(height_diff)

    def _calculate_knee_angle(self, frame_data: Dict, side: str = 'right') -> float:
        """
        What: 膝関節角度を計算（B2: 支持基盤、B3: 3関節連動性）
        Why: 支持脚の安定性と関節連動を評価
        Design Decision: 股関節-膝-足首の3点から角度算出

        Args:
            side: 'left' or 'right'

        Returns:
            float: 膝関節角度（度数）

        CRITICAL: NaN/Inf保護
        """
        if side == 'left':
            hip = self._get_landmark(frame_data, self.LEFT_HIP)
            knee = self._get_landmark(frame_data, self.LEFT_KNEE)
            ankle = self._get_landmark(frame_data, self.LEFT_ANKLE)
        else:
            hip = self._get_landmark(frame_data, self.RIGHT_HIP)
            knee = self._get_landmark(frame_data, self.RIGHT_KNEE)
            ankle = self._get_landmark(frame_data, self.RIGHT_ANKLE)

        if not all([hip, knee, ankle]):
            return 0.0

        return self._calculate_angle_3d(hip, knee, ankle)

    def _calculate_ankle_angle(self, frame_data: Dict, side: str = 'right') -> float:
        """
        What: 足首関節角度を計算（B3: 3関節連動性、B6: 後方筋群活性化）
        Why: 関節連動と衝撃吸収能力を評価
        Design Decision: 膝-足首-つま先の3点から角度算出

        Args:
            side: 'left' or 'right'

        Returns:
            float: 足首関節角度（度数）

        CRITICAL: NaN/Inf保護
        """
        if side == 'left':
            knee = self._get_landmark(frame_data, self.LEFT_KNEE)
            ankle = self._get_landmark(frame_data, self.LEFT_ANKLE)
            foot = self._get_landmark(frame_data, self.LEFT_FOOT_INDEX)
        else:
            knee = self._get_landmark(frame_data, self.RIGHT_KNEE)
            ankle = self._get_landmark(frame_data, self.RIGHT_ANKLE)
            foot = self._get_landmark(frame_data, self.RIGHT_FOOT_INDEX)

        if not all([knee, ankle, foot]):
            return 0.0

        return self._calculate_angle_3d(knee, ankle, foot)

    def _calculate_hip_angle(self, frame_data: Dict, side: str = 'right') -> float:
        """
        What: 股関節角度を計算（B3: 3関節連動性、B6: 後方筋群活性化）
        Why: 関節連動と後方筋群活性化を評価
        Design Decision: 肩-股関節-膝の3点から角度算出

        Args:
            side: 'left' or 'right'

        Returns:
            float: 股関節角度（度数）

        CRITICAL: NaN/Inf保護
        """
        if side == 'left':
            shoulder = self._get_landmark(frame_data, self.LEFT_SHOULDER)
            hip = self._get_landmark(frame_data, self.LEFT_HIP)
            knee = self._get_landmark(frame_data, self.LEFT_KNEE)
        else:
            shoulder = self._get_landmark(frame_data, self.RIGHT_SHOULDER)
            hip = self._get_landmark(frame_data, self.RIGHT_HIP)
            knee = self._get_landmark(frame_data, self.RIGHT_KNEE)

        if not all([shoulder, hip, knee]):
            return 0.0

        return self._calculate_angle_3d(shoulder, hip, knee)

    def _calculate_center_of_mass(self, frame_data: Dict) -> Optional[Dict]:
        """
        What: 重心位置を計算（B5: 重心移動）
        Why: 重心の軌跡・移動速度を評価
        Design Decision: 主要ランドマークの平均位置

        Returns:
            Dict or None: {'x': float, 'y': float, 'z': float}

        CRITICAL: NaN/Inf保護
        """
        # 重心計算に使用するランドマーク
        key_landmarks = [
            self.LEFT_SHOULDER, self.RIGHT_SHOULDER,
            self.LEFT_HIP, self.RIGHT_HIP,
            self.LEFT_KNEE, self.RIGHT_KNEE
        ]

        positions = []
        for idx in key_landmarks:
            lm = self._get_landmark(frame_data, idx)
            if lm:
                positions.append([lm['x'], lm['y'], lm['z']])

        if not positions:
            return None

        # 平均位置を重心として計算
        com = np.mean(positions, axis=0)
        return {
            'x': float(com[0]),
            'y': float(com[1]),
            'z': float(com[2])
        }

    def _calculate_elbow_angle(self, frame_data: Dict, side: str = 'right') -> float:
        """
        What: 肘関節角度を計算（B8: 肩周り独立制御）
        Why: 上腕の動作パターンを評価
        Design Decision: 肩-肘-手首の3点から角度算出

        Args:
            side: 'left' or 'right'

        Returns:
            float: 肘関節角度（度数）

        CRITICAL: NaN/Inf保護
        """
        if side == 'left':
            shoulder = self._get_landmark(frame_data, self.LEFT_SHOULDER)
            elbow = self._get_landmark(frame_data, self.LEFT_ELBOW)
            wrist = self._get_landmark(frame_data, self.LEFT_WRIST)
        else:
            shoulder = self._get_landmark(frame_data, self.RIGHT_SHOULDER)
            elbow = self._get_landmark(frame_data, self.RIGHT_ELBOW)
            wrist = self._get_landmark(frame_data, self.RIGHT_WRIST)

        if not all([shoulder, elbow, wrist]):
            return 0.0

        return self._calculate_angle_3d(shoulder, elbow, wrist)

    def _calculate_shoulder_elevation(self, frame_data: Dict, side: str = 'right') -> float:
        """
        What: 肩挙上角度を計算（B8: 肩周り独立制御）
        Why: 肩甲骨の安定性を評価
        Design Decision: 肩と肘のy座標差

        Args:
            side: 'left' or 'right'

        Returns:
            float: 肩挙上角度（正規化座標の差分）

        CRITICAL: NaN/Inf保護
        """
        if side == 'left':
            shoulder = self._get_landmark(frame_data, self.LEFT_SHOULDER)
            elbow = self._get_landmark(frame_data, self.LEFT_ELBOW)
        else:
            shoulder = self._get_landmark(frame_data, self.RIGHT_SHOULDER)
            elbow = self._get_landmark(frame_data, self.RIGHT_ELBOW)

        if not all([shoulder, elbow]):
            return 0.0

        # y座標の差（正の値 = 肩が肘より高い = 腕を下げている、負の値 = 肩挙上）
        elevation = shoulder['y'] - elbow['y']
        return float(abs(elevation))
