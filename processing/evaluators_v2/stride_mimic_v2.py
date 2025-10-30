"""
Purpose: ストライド模倣評価ロジック（v2: 8原則・237点満点システム）
Responsibility: A評価(3点) + B評価(30点: Eccentric 15点 + Concentric 15点) = 計33点満点
Dependencies: base_evaluator_v2.py, test_rules_v2.json
Created: 2025-10-30 by Claude
Decision Log: Phase B - 8原則評価システム実装

CRITICAL: 8原則・局面別評価、既存v1システムとは完全分離
"""
import numpy as np
from typing import Dict, List
from datetime import datetime
from .base_evaluator_v2 import BaseEvaluatorV2


class StrideMimicEvaluatorV2(BaseEvaluatorV2):
    """
    What: ストライド模倣評価クラス（v2: 8原則・33点満点）
    Why: A評価(3点) + B評価(30点) = 33点満点、Eccentric/Concentric局面別評価
    Design Decision: BaseEvaluatorV2継承、test_rules_v2.json使用

    評価構造:
    - A. テスト実施の可否（3点）
      - ストライド長・股関節伸展・完遂回数
    - B. 8原則評価（30点）
      - Eccentric（15点）: B1(2.0) + B2(2.0) + B3(4.5) + B6(2.0) + B7(4.5)
      - Concentric（15点）: B1(2.0) + B2(2.0) + B3(4.5) + B6(2.0) + B7(4.5)

    CRITICAL: 主評価（B3, B7: 各4.5点）、副評価（B1, B2, B6: 各2.0点）
    """

    def __init__(self, config_path: str = 'processing/evaluators_v2/config_v2/test_rules_v2.json'):
        """初期化"""
        super().__init__(config_path)
        if 'test_types' in self.rules and 'stride_mimic' in self.rules['test_types']:
            self.test_config = self.rules['test_types']['stride_mimic']
        else:
            self.test_config = {'test_id': 'T03', 'max_score': 33}

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float = None, leg_length: float = None, **kwargs) -> Dict:
        """総合評価"""
        if not landmarks_data:
            return {
                'version': 'v2',
                'test_id': 'T03_stride_mimic',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'A_execution_score': 0.0,
                'B_total': 0.0,
                'total_score': 0.0,
                'total_percentage': 0,
                'max_possible': 33,
                'details': '姿勢が検出できませんでした'
            }

        section_a_result = self._evaluate_section_a(landmarks_data, base_width)
        hip_angles = self._extract_hip_angles(landmarks_data)
        phases = self._detect_phases(landmarks_data, hip_angles)
        section_b_result = self._evaluate_section_b(landmarks_data, phases, base_width)

        total_score = section_a_result['score'] + section_b_result['total']
        total_percentage = int((total_score / 33) * 100)

        return {
            'version': 'v2',
            'test_id': 'T03_stride_mimic',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'A_execution_score': section_a_result['score'],
            'A_breakdown': section_a_result['breakdown'],
            'B_principles': section_b_result['principles'],
            'B_total': section_b_result['total'],
            'total_score': round(total_score, 1),
            'total_percentage': total_percentage,
            'max_possible': 33
        }

    def _evaluate_section_a(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """A評価（3点満点）"""
        score = 0.0
        breakdown = {}

        stride_length_score = self._score_stride_length(landmarks_data, base_width)
        score += stride_length_score
        breakdown['stride_length'] = stride_length_score

        hip_extension_score = self._score_hip_extension(landmarks_data)
        score += hip_extension_score
        breakdown['hip_extension'] = hip_extension_score

        return {'score': round(score, 1), 'breakdown': breakdown}

    def _evaluate_section_b(self, landmarks_data: List[Dict], phases: Dict, base_width: float) -> Dict:
        """B評価（30点満点）"""
        ecc_frames = phases['eccentric']['frames']
        ecc_data = [landmarks_data[i] for i in ecc_frames if i < len(landmarks_data)]
        ecc_scores = self._evaluate_principles(ecc_data, 'eccentric', base_width)

        con_frames = phases['concentric']['frames']
        con_data = [landmarks_data[i] for i in con_frames if i < len(landmarks_data)]
        con_scores = self._evaluate_principles(con_data, 'concentric', base_width)

        total = sum(ecc_scores.values()) + sum(con_scores.values())
        return {'principles': {'eccentric': ecc_scores, 'concentric': con_scores}, 'total': round(total, 1)}

    def _evaluate_principles(self, landmarks_data: List[Dict], phase: str, base_width: float) -> Dict:
        """8原則評価（B1, B2, B3, B6, B7）"""
        if not landmarks_data:
            return {
                'B1_core_stability': 0.0,
                'B2_support_foundation': 0.0,
                'B3_3joint_coordination': 0.0,
                'B6_posterior_chain': 0.0,
                'B7_upper_lower_separation': 0.0
            }

        b1_score = self._evaluate_b1_core_stability(landmarks_data, max_score=2.0)
        b2_score = self._evaluate_b2_support_foundation(landmarks_data, max_score=2.0)
        b3_score = self._evaluate_b3_3joint_coordination(landmarks_data, max_score=4.5)
        b6_score = self._evaluate_b6_posterior_chain(landmarks_data, max_score=2.0)
        b7_score = self._evaluate_b7_upper_lower_separation(landmarks_data, max_score=4.5)

        return {
            'B1_core_stability': round(b1_score, 1),
            'B2_support_foundation': round(b2_score, 1),
            'B3_3joint_coordination': round(b3_score, 1),
            'B6_posterior_chain': round(b6_score, 1),
            'B7_upper_lower_separation': round(b7_score, 1)
        }

    # ==================== A評価ヘルパーメソッド ====================

    def _score_stride_length(self, landmarks_data: List[Dict], base_width: float) -> float:
        """ストライド長スコア（1.5点）"""
        stride_lengths = []
        for i in range(1, len(landmarks_data)):
            prev = landmarks_data[i-1]
            curr = landmarks_data[i]
            left_ankle_prev = self._get_landmark(prev, self.LEFT_ANKLE)
            right_ankle_prev = self._get_landmark(prev, self.RIGHT_ANKLE)
            left_ankle_curr = self._get_landmark(curr, self.LEFT_ANKLE)
            right_ankle_curr = self._get_landmark(curr, self.RIGHT_ANKLE)

            if all([left_ankle_prev, right_ankle_prev, left_ankle_curr, right_ankle_curr]):
                stride_length = max(
                    abs(left_ankle_curr['z'] - left_ankle_prev['z']),
                    abs(right_ankle_curr['z'] - right_ankle_prev['z'])
                )
                stride_lengths.append(stride_length)

        if not stride_lengths:
            return 0.5

        avg_stride = np.mean(stride_lengths)
        normalized_stride = avg_stride / base_width if base_width > 0 else 0

        if normalized_stride > 1.0:
            return 1.5
        elif normalized_stride > 0.7:
            return 1.0
        elif normalized_stride > 0.5:
            return 0.5
        else:
            return 0.0

    def _score_hip_extension(self, landmarks_data: List[Dict]) -> float:
        """股関節伸展スコア（1.5点）"""
        hip_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_hip_angle(frame_data, side='right')
            if angle > 0:
                hip_angles.append(angle)

        if not hip_angles:
            return 0.5

        max_hip_angle = max(hip_angles)
        if max_hip_angle > 170:
            return 1.5
        elif max_hip_angle > 160:
            return 1.0
        elif max_hip_angle > 150:
            return 0.5
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

    def _evaluate_b3_3joint_coordination(self, landmarks_data: List[Dict], max_score: float) -> float:
        """B3評価（3関節連動性）- 主評価"""
        hip_angles = []
        knee_angles = []
        for frame_data in landmarks_data:
            hip_angle = self._calculate_hip_angle(frame_data, side='right')
            knee_angle = self._calculate_knee_angle(frame_data, side='right')
            if hip_angle > 0 and knee_angle > 0:
                hip_angles.append(hip_angle)
                knee_angles.append(knee_angle)

        if len(hip_angles) < 2 or len(knee_angles) < 2:
            return max_score * 0.5

        hip_changes = np.diff(hip_angles)
        knee_changes = np.diff(knee_angles)

        if len(hip_changes) > 0 and len(knee_changes) > 0:
            min_len = min(len(hip_changes), len(knee_changes))
            correlation = np.corrcoef(hip_changes[:min_len], knee_changes[:min_len])[0, 1]
            if correlation > 0.7:
                return max_score
            elif correlation > 0.5:
                return max_score * 0.75
            elif correlation > 0.3:
                return max_score * 0.5
            else:
                return max_score * 0.25
        else:
            return max_score * 0.5

    def _evaluate_b6_posterior_chain(self, landmarks_data: List[Dict], max_score: float) -> float:
        """B6評価（後方筋群活性化）"""
        hip_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_hip_angle(frame_data, side='right')
            if angle > 0:
                hip_angles.append(angle)

        if not hip_angles:
            return max_score * 0.5

        # 股関節伸展角度の最大値（後方筋群活性化の指標）
        max_hip_angle = max(hip_angles)
        avg_hip_angle = np.mean(hip_angles)

        score = max_score
        if max_hip_angle < 150:  # 伸展不足
            score -= max_score * 0.5
        elif max_hip_angle < 160:
            score -= max_score * 0.25

        if avg_hip_angle < 140:
            score -= max_score * 0.3
        elif avg_hip_angle < 150:
            score -= max_score * 0.15

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

    def _extract_hip_angles(self, landmarks_data: List[Dict]) -> List[float]:
        """股関節角度抽出（局面検出用）"""
        hip_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_hip_angle(frame_data, side='right')
            hip_angles.append(angle)
        return hip_angles
