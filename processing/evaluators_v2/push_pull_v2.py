"""
Purpose: Push Pull評価ロジック（v2.1: 8原則・560点満点システム）
Responsibility: A評価(3点) + B評価(30点: Pull 30点 + Push 30点) = 計320点満点
Dependencies: base_evaluator_v2.py, test_rules_v2.json
Created: 2025-10-30 by Claude
Decision Log: Phase B - 8原則評価システム実装, v2.1 - 560点満点統一、Pull/Push局面別評価（特殊構造）

CRITICAL: 8原則・Pull/Push局面別評価、B7上下身分離・B8肩周り独立制御が主評価
"""
import numpy as np
from typing import Dict, List
from datetime import datetime
from .base_evaluator_v2 import BaseEvaluatorV2


class PushPullEvaluatorV2(BaseEvaluatorV2):
    """
    What: Push Pull評価クラス（v2.1: 8原則・80点満点）
    Why: A評価(20点) + B評価(60点) = 80点満点、Pull/Push局面別評価（特殊構造）
    Design Decision: BaseEvaluatorV2継承、test_rules_v2.json使用、B7・B8主評価

    評価構造:
    - A. テスト実施の可否（3点）
      - プル距離・プッシュ角度・完遂回数
    - B. 8原則評価（30点）
      - Pull局面（30点）: B1(3.0) + B2(3.0) + B7(4.5) + B8(4.5)
      - Push局面（30点）: B1(3.0) + B2(3.0) + B7(4.5) + B8(4.5)

    CRITICAL: 主評価（B7, B8: 各4.5点）、副評価（B1, B2: 各3.0点）
    """

    def __init__(self, config_path: str = 'processing/evaluators_v2/config_v2/test_rules_v2.json'):
        """初期化"""
        super().__init__(config_path)
        if 'test_types' in self.rules and 'push_pull' in self.rules['test_types']:
            self.test_config = self.rules['test_types']['push_pull']
        else:
            self.test_config = {'test_id': 'T06', 'max_score': 33}

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float = None, leg_length: float = None, **kwargs) -> Dict:
        """総合評価"""
        if not landmarks_data:
            return {
                'version': 'v2.1',
                'test_id': 'T06_push_pull',
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
        phases = self._detect_pull_push_phases(landmarks_data, elbow_angles)
        section_b_result = self._evaluate_section_b(landmarks_data, phases, base_width)

        total_score = section_a_result['score'] + section_b_result['total']
        total_percentage = int((total_score / 80) * 100)

        return {
            'version': 'v2.1',
            'test_id': 'T06_push_pull',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'A_execution_score': section_a_result['score'],
            'A_breakdown': section_a_result['breakdown'],
            'B_principles': section_b_result['principles'],
            'B_total': section_b_result['total'],
            'total_score': round(total_score, 1),
            'total_percentage': total_percentage,
            'max_possible': 80,
            'special_structure': 'pull_push_separate'
        }

    def _evaluate_section_a(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """A評価（20点満点）"""
        score = 0.0
        breakdown = {}

        pull_distance_score = self._score_pull_distance(landmarks_data, base_width)
        score += pull_distance_score
        breakdown['pull_distance'] = pull_distance_score

        push_angle_score = self._score_push_angle(landmarks_data)
        score += push_angle_score
        breakdown['push_angle'] = push_angle_score

        return {'score': round(score, 1), 'breakdown': breakdown}

    def _evaluate_section_b(self, landmarks_data: List[Dict], phases: Dict, base_width: float) -> Dict:
        """B評価（60点満点: Pull + Push）"""
        pull_frames = phases['pull']['frames']
        pull_data = [landmarks_data[i] for i in pull_frames if i < len(landmarks_data)]
        pull_scores = self._evaluate_principles(pull_data, 'pull', base_width)

        push_frames = phases['push']['frames']
        push_data = [landmarks_data[i] for i in push_frames if i < len(landmarks_data)]
        push_scores = self._evaluate_principles(push_data, 'push', base_width)

        total = sum(pull_scores.values()) + sum(push_scores.values())
        return {'principles': {'pull': pull_scores, 'push': push_scores}, 'total': round(total, 1)}

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

    def _score_pull_distance(self, landmarks_data: List[Dict], base_width: float) -> float:
        """プル距離スコア（10点）"""
        wrist_movements = []
        for i in range(1, len(landmarks_data)):
            prev = landmarks_data[i-1]
            curr = landmarks_data[i]

            # 両手首の移動距離（プル動作）
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

        if normalized_movement > 0.7:
            return 10.0
        elif normalized_movement > 0.5:
            return 6.7
        elif normalized_movement > 0.3:
            return 3.3
        else:
            return 0.0

    def _score_push_angle(self, landmarks_data: List[Dict]) -> float:
        """プッシュ角度スコア（10点）"""
        elbow_angles = []
        for frame_data in landmarks_data:
            # 肘伸展角度（プッシュの質）
            left_angle = self._calculate_elbow_angle(frame_data, side='left')
            right_angle = self._calculate_elbow_angle(frame_data, side='right')
            if left_angle > 0 and right_angle > 0:
                avg_angle = (left_angle + right_angle) / 2
                elbow_angles.append(avg_angle)

        if not elbow_angles:
            return 3.3

        max_elbow_angle = max(elbow_angles)
        if max_elbow_angle > 160:  # ほぼ完全伸展
            return 10.0
        elif max_elbow_angle > 140:
            return 6.7
        elif max_elbow_angle > 120:
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
        elbow_angles_left = []
        elbow_angles_right = []
        shoulder_elevations = []
        shoulder_height_diffs = []

        for frame_data in landmarks_data:
            # 左右肘角度（腕の動き）
            elbow_angle_left = self._calculate_elbow_angle(frame_data, side='left')
            elbow_angle_right = self._calculate_elbow_angle(frame_data, side='right')
            if elbow_angle_left > 0:
                elbow_angles_left.append(elbow_angle_left)
            if elbow_angle_right > 0:
                elbow_angles_right.append(elbow_angle_right)

            # 肩挙上（肩甲骨安定性）
            shoulder_elevation_left = self._calculate_shoulder_elevation(frame_data, side='left')
            shoulder_elevation_right = self._calculate_shoulder_elevation(frame_data, side='right')
            if shoulder_elevation_left > 0 and shoulder_elevation_right > 0:
                avg_elevation = (shoulder_elevation_left + shoulder_elevation_right) / 2
                shoulder_elevations.append(avg_elevation)

            # 左右肩の高低差（肩の安定性）
            shoulder_diff = self._calculate_shoulder_height_diff(frame_data)
            if shoulder_diff > 0:
                shoulder_height_diffs.append(shoulder_diff)

        if not elbow_angles_left or not elbow_angles_right or not shoulder_elevations or not shoulder_height_diffs:
            return max_score * 0.5

        # 肘角度の変動（プル/プッシュの大きさ）
        left_elbow_range = max(elbow_angles_left) - min(elbow_angles_left)
        right_elbow_range = max(elbow_angles_right) - min(elbow_angles_right)
        avg_elbow_range = (left_elbow_range + right_elbow_range) / 2

        # 肩挙上の抑制（肩甲骨安定性）
        avg_shoulder_elevation = np.mean(shoulder_elevations)

        # 左右肩の安定性
        avg_shoulder_diff = np.mean(shoulder_height_diffs)

        score = max_score

        # 肘角度変動（プル/プッシュが大きいほど良い）
        if avg_elbow_range < 40:
            score -= max_score * 0.3
        elif avg_elbow_range < 70:
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

    def _detect_pull_push_phases(self, landmarks_data: List[Dict], elbow_angles: List[float]) -> Dict:
        """Pull/Push局面検出（特殊構造）"""
        if not elbow_angles or len(elbow_angles) < 2:
            # フォールバック: 前半をPull、後半をPushとみなす
            mid_point = len(landmarks_data) // 2
            return {
                'pull': {
                    'frames': list(range(0, mid_point)),
                    'description': 'プル局面'
                },
                'push': {
                    'frames': list(range(mid_point, len(landmarks_data))),
                    'description': 'プッシュ局面'
                }
            }

        # 肘角度の変化から局面検出
        # Pull: 肘角度が減少（屈曲）
        # Push: 肘角度が増加（伸展）
        angle_changes = np.diff(elbow_angles)

        pull_frames = []
        push_frames = []

        for i, change in enumerate(angle_changes):
            if change < 0:  # 屈曲 = Pull
                pull_frames.append(i)
            else:  # 伸展 = Push
                push_frames.append(i)

        # フレームが空の場合はフォールバック
        if not pull_frames:
            pull_frames = list(range(0, len(landmarks_data) // 2))
        if not push_frames:
            push_frames = list(range(len(landmarks_data) // 2, len(landmarks_data)))

        return {
            'pull': {
                'frames': pull_frames,
                'description': 'プル局面'
            },
            'push': {
                'frames': push_frames,
                'description': 'プッシュ局面'
            }
        }
