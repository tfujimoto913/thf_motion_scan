"""
Purpose: Cross Step評価ロジック（v2.1: 8原則・560点満点システム）
Responsibility: A評価(20点) + B評価(60点: Eccentric 30点 + Concentric 30点) = 計80点満点
Dependencies: base_evaluator_v2.py, test_rules_v2.json
Created: 2025-10-30 by Claude
Decision Log: Phase B - 8原則評価システム実装, v2.1 - 560点満点統一、B5重心移動主評価

CRITICAL: 8原則・局面別評価、B5初の主評価実装
"""
import numpy as np
from typing import Dict, List
from datetime import datetime
from .base_evaluator_v2 import BaseEvaluatorV2


class CrossStepEvaluatorV2(BaseEvaluatorV2):
    """
    What: Cross Step評価クラス（v2.1: 8原則・80点満点）
    Why: A評価(20点) + B評価(60点) = 80点満点、Eccentric/Concentric局面別評価
    Design Decision: BaseEvaluatorV2継承、test_rules_v2.json使用、B5主評価

    評価構造:
    - A. テスト実施の可否（3点）
      - ステップ幅・膝屈曲・完遂回数
    - B. 8原則評価（30点）
      - Eccentric（30点）: B1(2.0) + B2(2.0) + B3(4.5) + B4(2.0) + B5(4.5)
      - Concentric（30点）: B1(2.0) + B2(2.0) + B3(4.5) + B4(2.0) + B5(4.5)

    CRITICAL: 主評価（B3, B5: 各4.5点）、副評価（B1, B2, B4: 各2.0点）
    """

    def __init__(self, config_path: str = 'processing/evaluators_v2/config_v2/test_rules_v2.json'):
        """初期化"""
        super().__init__(config_path)
        if 'test_types' in self.rules and 'cross_step' in self.rules['test_types']:
            self.test_config = self.rules['test_types']['cross_step']
        else:
            self.test_config = {'test_id': 'T07', 'max_score': 33}

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float = None, leg_length: float = None, **kwargs) -> Dict:
        """総合評価"""
        if not landmarks_data:
            return {
                'version': 'v2.1',
                'test_id': 'T07_cross_step',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'A_execution_score': 0.0,
                'B_total': 0.0,
                'total_score': 0.0,
                'total_percentage': 0,
                'max_possible': 80,
                'details': '姿勢が検出できませんでした'
            }

        section_a_result = self._evaluate_section_a(landmarks_data, base_width)
        knee_angles = self._extract_knee_angles(landmarks_data)
        phases = self._detect_phases(landmarks_data, knee_angles)
        section_b_result = self._evaluate_section_b(landmarks_data, phases, base_width)

        total_score = section_a_result['score'] + section_b_result['total']
        total_percentage = int((total_score / 80) * 100)

        return {
            'version': 'v2.1',
            'test_id': 'T07_cross_step',
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

        step_width_score = self._score_step_width(landmarks_data, base_width)
        score += step_width_score
        breakdown['step_width'] = step_width_score

        knee_flexion_score = self._score_knee_flexion(landmarks_data)
        score += knee_flexion_score
        breakdown['knee_flexion'] = knee_flexion_score

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
        """8原則評価（B1, B2, B3, B4, B5）"""
        if not landmarks_data:
            return {
                'B1_core_stability': 0.0,
                'B2_support_foundation': 0.0,
                'B3_3joint_coordination': 0.0,
                'B4_pelvis_horizontal': 0.0,
                'B5_weight_shift': 0.0
            }

        b1_score = self._evaluate_b1_core_stability(landmarks_data, max_score=4.0)
        b2_score = self._evaluate_b2_support_foundation(landmarks_data, max_score=4.0)
        b3_score = self._evaluate_b3_3joint_coordination(landmarks_data, max_score=9.0)
        b4_score = self._evaluate_b4_pelvis_horizontal(landmarks_data, max_score=4.0)
        b5_score = self._evaluate_b5_weight_shift(landmarks_data, max_score=9.0)

        return {
            'B1_core_stability': round(b1_score, 1),
            'B2_support_foundation': round(b2_score, 1),
            'B3_3joint_coordination': round(b3_score, 1),
            'B4_pelvis_horizontal': round(b4_score, 1),
            'B5_weight_shift': round(b5_score, 1)
        }

    # ==================== A評価ヘルパーメソッド ====================

    def _score_step_width(self, landmarks_data: List[Dict], base_width: float) -> float:
        """ステップ幅スコア（10点）"""
        step_widths = []
        for i in range(1, len(landmarks_data)):
            prev = landmarks_data[i-1]
            curr = landmarks_data[i]
            left_ankle_prev = self._get_landmark(prev, self.LEFT_ANKLE)
            right_ankle_prev = self._get_landmark(prev, self.RIGHT_ANKLE)
            left_ankle_curr = self._get_landmark(curr, self.LEFT_ANKLE)
            right_ankle_curr = self._get_landmark(curr, self.RIGHT_ANKLE)

            if all([left_ankle_prev, right_ankle_prev, left_ankle_curr, right_ankle_curr]):
                step_width = max(
                    abs(left_ankle_curr['x'] - left_ankle_prev['x']),
                    abs(right_ankle_curr['x'] - right_ankle_prev['x'])
                )
                step_widths.append(step_width)

        if not step_widths:
            return 3.3

        avg_step_width = np.mean(step_widths)
        normalized_width = avg_step_width / base_width if base_width > 0 else 0

        if normalized_width > 0.8:
            return 10.0
        elif normalized_width > 0.6:
            return 6.7
        elif normalized_width > 0.4:
            return 3.3
        else:
            return 0.0

    def _score_knee_flexion(self, landmarks_data: List[Dict]) -> float:
        """膝屈曲スコア（10点）"""
        knee_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_knee_angle(frame_data, side='right')
            if angle > 0:
                knee_angles.append(angle)

        if not knee_angles:
            return 3.3

        min_knee_angle = min(knee_angles)
        if min_knee_angle < 90:
            return 10.0
        elif min_knee_angle < 120:
            return 6.7
        elif min_knee_angle < 150:
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

    def _evaluate_b4_pelvis_horizontal(self, landmarks_data: List[Dict], max_score: float) -> float:
        """B4評価（骨盤水平維持）"""
        hip_diffs = []
        for frame_data in landmarks_data:
            hip_diff = self._calculate_hip_height_diff(frame_data)
            if hip_diff > 0:
                hip_diffs.append(hip_diff)

        if not hip_diffs:
            return max_score * 0.5

        avg_hip_diff = np.mean(hip_diffs)
        score = max_score
        if avg_hip_diff > 0.15:
            score -= max_score * 0.6
        elif avg_hip_diff > 0.10:
            score -= max_score * 0.4
        elif avg_hip_diff > 0.05:
            score -= max_score * 0.2

        return max(0.0, score)

    def _evaluate_b5_weight_shift(self, landmarks_data: List[Dict], max_score: float) -> float:
        """B5評価（重心移動）- 主評価"""
        com_positions = []
        for frame_data in landmarks_data:
            com = self._calculate_center_of_mass(frame_data)
            if com:
                com_positions.append(com)

        if len(com_positions) < 2:
            return max_score * 0.5

        # 重心移動距離
        total_movement = 0.0
        for i in range(1, len(com_positions)):
            movement = self._calculate_distance(com_positions[i-1], com_positions[i])
            total_movement += movement

        # 重心移動の方向性（横方向移動）
        x_movements = []
        for i in range(1, len(com_positions)):
            x_move = abs(com_positions[i]['x'] - com_positions[i-1]['x'])
            x_movements.append(x_move)

        if not x_movements:
            return max_score * 0.5

        total_x_movement = sum(x_movements)
        avg_x_movement = np.mean(x_movements)

        score = max_score

        # 重心移動距離（大きいほど良い）
        if total_movement < 0.5:
            score -= max_score * 0.4
        elif total_movement < 1.0:
            score -= max_score * 0.2

        # 横方向移動（クロスステップの特徴）
        if avg_x_movement < 0.05:
            score -= max_score * 0.4
        elif avg_x_movement < 0.10:
            score -= max_score * 0.2

        return max(0.0, score)

    def _extract_knee_angles(self, landmarks_data: List[Dict]) -> List[float]:
        """膝角度抽出（局面検出用）"""
        knee_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_knee_angle(frame_data, side='right')
            knee_angles.append(angle)
        return knee_angles
