"""
Purpose: Upper Body Swing評価ロジック（v2.1: 8原則・560点満点システム）
Responsibility: A評価(20点) + B評価(60点: Eccentric 30点 + Concentric 30点) = 計80点満点
Dependencies: base_evaluator_v2.py, test_rules_v2.json
Created: 2025-10-30 by Claude
Decision Log: Phase B - 8原則評価システム実装, v2.1 - 560点満点統一、B8肩周り独立制御主評価

CRITICAL: 8原則・局面別評価、B8初の主評価実装
"""
import numpy as np
from typing import Dict, List
from datetime import datetime
from .base_evaluator_v2 import BaseEvaluatorV2


class UpperBodySwingEvaluatorV2(BaseEvaluatorV2):
    """
    What: Upper Body Swing評価クラス（v2.1: 8原則・80点満点）
    Why: A評価(20点) + B評価(60点) = 80点満点、Eccentric/Concentric局面別評価
    Design Decision: BaseEvaluatorV2継承、test_rules_v2.json使用、B8主評価

    評価構造:
    - A. テスト実施の可否（3点）
      - 腕振幅・バランス・完遂回数
    - B. 8原則評価（30点）
      - Eccentric（30点）: B1(3.0) + B2(3.0) + B7(4.5) + B8(4.5)
      - Concentric（30点）: B1(3.0) + B2(3.0) + B7(4.5) + B8(4.5)

    CRITICAL: 主評価（B7, B8: 各4.5点）、副評価（B1, B2: 各3.0点）
    """

    def __init__(self, config_path: str = 'processing/evaluators_v2/config_v2/test_rules_v2.json'):
        """初期化"""
        super().__init__(config_path)
        if 'test_types' in self.rules and 'upper_body_swing' in self.rules['test_types']:
            self.test_config = self.rules['test_types']['upper_body_swing']
        else:
            self.test_config = {'test_id': 'T05', 'max_score': 33}

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float = None, leg_length: float = None, **kwargs) -> Dict:
        """総合評価"""
        if not landmarks_data:
            return {
                'version': 'v2.1',
                'test_id': 'T05_upper_body_swing',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'A_execution_score': 0.0,
                'B_total': 0.0,
                'total_score': 0.0,
                'total_percentage': 0,
                'max_possible': 80,
                'details': '姿勢が検出できませんでした'
            }

        section_a_result = self._evaluate_section_a(landmarks_data, base_width)
        elbow_angles = self._extract_elbow_angles(landmarks_data)
        phases = self._detect_phases(landmarks_data, elbow_angles)
        section_b_result = self._evaluate_section_b(landmarks_data, phases, base_width)

        total_score = section_a_result['score'] + section_b_result['total']
        total_percentage = int((total_score / 80) * 100)

        return {
            'version': 'v2.1',
            'test_id': 'T05_upper_body_swing',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'A_execution_score': section_a_result['score'],
            'A_breakdown': section_a_result['breakdown'],
            'B_principles': section_b_result['principles'],
            'B_total': section_b_result['total'],
            'total_score': round(total_score, 1),
            'total_percentage': total_percentage,
            'max_possible': 80
        }

    def _evaluate_section_a(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """A評価（20点満点）"""
        score = 0.0
        breakdown = {}

        arm_swing_score = self._score_arm_swing_amplitude(landmarks_data, base_width)
        score += arm_swing_score
        breakdown['arm_swing_amplitude'] = arm_swing_score

        balance_score = self._score_balance(landmarks_data)
        score += balance_score
        breakdown['balance'] = balance_score

        return {'score': round(score, 1), 'breakdown': breakdown}

    def _evaluate_section_b(self, landmarks_data: List[Dict], phases: Dict, base_width: float) -> Dict:
        """B評価（60点満点）"""
        ecc_frames = phases['eccentric']['frames']
        ecc_data = [landmarks_data[i] for i in ecc_frames if i < len(landmarks_data)]
        ecc_scores = self._evaluate_principles(ecc_data, 'eccentric', base_width)

        con_frames = phases['concentric']['frames']
        con_data = [landmarks_data[i] for i in con_frames if i < len(landmarks_data)]
        con_scores = self._evaluate_principles(con_data, 'concentric', base_width)

        total = sum(ecc_scores.values()) + sum(con_scores.values())
        return {'principles': {'eccentric': ecc_scores, 'concentric': con_scores}, 'total': round(total, 1)}

    def _evaluate_principles(self, landmarks_data: List[Dict], phase: str, base_width: float) -> Dict:
        """8原則評価（B1, B2, B7, B8）"""
        if not landmarks_data:
            return {
                'B1_core_stability': 0.0,
                'B2_support_foundation': 0.0,
                'B7_upper_lower_separation': 0.0,
                'B8_shoulder_independent_control': 0.0
            }

        b1_score = self._evaluate_b1_core_stability(landmarks_data, max_score=6.0)
        b2_score = self._evaluate_b2_support_foundation(landmarks_data, max_score=6.0)
        b7_score = self._evaluate_b7_upper_lower_separation(landmarks_data, max_score=9.0)
        b8_score = self._evaluate_b8_shoulder_independent_control(landmarks_data, max_score=9.0)

        return {
            'B1_core_stability': round(b1_score, 1),
            'B2_support_foundation': round(b2_score, 1),
            'B7_upper_lower_separation': round(b7_score, 1),
            'B8_shoulder_independent_control': round(b8_score, 1)
        }

    # ==================== A評価ヘルパーメソッド ====================

    def _score_arm_swing_amplitude(self, landmarks_data: List[Dict], base_width: float) -> float:
        """腕振幅スコア（10点）"""
        wrist_movements = []
        for i in range(1, len(landmarks_data)):
            prev = landmarks_data[i-1]
            curr = landmarks_data[i]
            left_wrist_prev = self._get_landmark(prev, self.LEFT_WRIST)
            right_wrist_prev = self._get_landmark(prev, self.RIGHT_WRIST)
            left_wrist_curr = self._get_landmark(curr, self.LEFT_WRIST)
            right_wrist_curr = self._get_landmark(curr, self.RIGHT_WRIST)

            if all([left_wrist_prev, right_wrist_prev, left_wrist_curr, right_wrist_curr]):
                left_move = self._calculate_distance(left_wrist_prev, left_wrist_curr)
                right_move = self._calculate_distance(right_wrist_prev, right_wrist_curr)
                wrist_movements.append(max(left_move, right_move))

        if not wrist_movements:
            return 3.3

        max_movement = max(wrist_movements)
        normalized_movement = max_movement / base_width if base_width > 0 else 0

        if normalized_movement > 0.8:
            return 10.0
        elif normalized_movement > 0.6:
            return 6.7
        elif normalized_movement > 0.4:
            return 3.3
        else:
            return 0.0

    def _score_balance(self, landmarks_data: List[Dict]) -> float:
        """バランススコア（10点）"""
        hip_diffs = []
        for frame_data in landmarks_data:
            hip_diff = self._calculate_hip_height_diff(frame_data)
            if hip_diff > 0:
                hip_diffs.append(hip_diff)

        if not hip_diffs:
            return 3.3

        avg_hip_diff = np.mean(hip_diffs)
        if avg_hip_diff < 0.05:
            return 10.0
        elif avg_hip_diff < 0.10:
            return 6.7
        elif avg_hip_diff < 0.15:
            return 3.3
        else:
            return 0.0

    # ==================== B評価ヘルパーメソッド ====================

    def _evaluate_b1_core_stability(self, landmarks_data: List[Dict], max_score: float) -> float:
        """B1評価（体幹安定性）"""
        trunk_rotations = []
        shoulder_diffs = []
        for frame_data in landmarks_data:
            rotation = self._calculate_trunk_rotation(frame_data)
            shoulder_diff = self._calculate_shoulder_height_diff(frame_data)
            if rotation > 0:
                trunk_rotations.append(rotation)
            if shoulder_diff > 0:
                shoulder_diffs.append(shoulder_diff)

        if not trunk_rotations or not shoulder_diffs:
            return max_score * 0.5

        avg_rotation = np.mean(trunk_rotations)
        avg_shoulder_diff = np.mean(shoulder_diffs)

        score = max_score
        if avg_rotation > 20:
            score -= max_score * 0.5
        elif avg_rotation > 10:
            score -= max_score * 0.25
        if avg_shoulder_diff > 0.1:
            score -= max_score * 0.3
        elif avg_shoulder_diff > 0.05:
            score -= max_score * 0.15

        return max(0.0, score)

    def _evaluate_b2_support_foundation(self, landmarks_data: List[Dict], max_score: float) -> float:
        """B2評価（支持基盤）"""
        knee_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_knee_angle(frame_data, side='right')
            if angle > 0:
                knee_angles.append(angle)

        if not knee_angles:
            return max_score * 0.5

        std_dev = np.std(knee_angles)
        score = max_score
        if std_dev > 15:
            score -= max_score * 0.5
        elif std_dev > 10:
            score -= max_score * 0.3

        return max(0.0, score)

    def _evaluate_b7_upper_lower_separation(self, landmarks_data: List[Dict], max_score: float) -> float:
        """B7評価（上下身分離性）- 主評価"""
        separation_angles = []
        for frame_data in landmarks_data:
            trunk_rotation = self._calculate_trunk_rotation(frame_data)
            left_hip = self._get_landmark(frame_data, self.LEFT_HIP)
            right_hip = self._get_landmark(frame_data, self.RIGHT_HIP)

            if left_hip and right_hip and trunk_rotation > 0:
                hip_rotation = abs(np.degrees(np.arctan2(
                    right_hip['z'] - left_hip['z'],
                    right_hip['x'] - left_hip['x']
                )))
                separation = abs(trunk_rotation - hip_rotation)
                separation_angles.append(separation)

        if not separation_angles:
            return max_score * 0.5

        avg_separation = np.mean(separation_angles)
        score = max_score
        if avg_separation < 5:
            score -= max_score * 0.6
        elif avg_separation < 10:
            score -= max_score * 0.3
        elif avg_separation < 15:
            score -= max_score * 0.15

        return max(0.0, score)

    def _evaluate_b8_shoulder_independent_control(self, landmarks_data: List[Dict], max_score: float) -> float:
        """B8評価（肩周り独立制御）- 主評価"""
        elbow_angles = []
        shoulder_elevations = []
        shoulder_height_diffs = []

        for frame_data in landmarks_data:
            # 肘角度（腕の動き）
            elbow_angle = self._calculate_elbow_angle(frame_data, side='right')
            if elbow_angle > 0:
                elbow_angles.append(elbow_angle)

            # 肩挙上（肩甲骨安定性）
            shoulder_elevation = self._calculate_shoulder_elevation(frame_data, side='right')
            if shoulder_elevation > 0:
                shoulder_elevations.append(shoulder_elevation)

            # 左右肩の高低差（肩の安定性）
            shoulder_diff = self._calculate_shoulder_height_diff(frame_data)
            if shoulder_diff > 0:
                shoulder_height_diffs.append(shoulder_diff)

        if not elbow_angles or not shoulder_elevations or not shoulder_height_diffs:
            return max_score * 0.5

        # 肘角度の変動（腕振りの大きさ）
        elbow_range = max(elbow_angles) - min(elbow_angles)
        # 肩挙上の抑制（肩甲骨安定性）
        avg_shoulder_elevation = np.mean(shoulder_elevations)
        # 左右肩の安定性
        avg_shoulder_diff = np.mean(shoulder_height_diffs)

        score = max_score

        # 肘角度変動（腕振りが大きいほど良い）
        if elbow_range < 30:
            score -= max_score * 0.3
        elif elbow_range < 60:
            score -= max_score * 0.15

        # 肩挙上抑制（肩を上げすぎないほど良い）
        if avg_shoulder_elevation > 0.15:
            score -= max_score * 0.4
        elif avg_shoulder_elevation > 0.10:
            score -= max_score * 0.2

        # 左右肩の安定性
        if avg_shoulder_diff > 0.10:
            score -= max_score * 0.3
        elif avg_shoulder_diff > 0.05:
            score -= max_score * 0.15

        return max(0.0, score)

    def _extract_elbow_angles(self, landmarks_data: List[Dict]) -> List[float]:
        """肘角度抽出（局面検出用）"""
        elbow_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_elbow_angle(frame_data, side='right')
            elbow_angles.append(angle)
        return elbow_angles
