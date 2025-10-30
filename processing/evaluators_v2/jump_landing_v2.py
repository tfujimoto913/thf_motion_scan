"""
Purpose: ジャンプ着地評価ロジック（v2: 8原則・237点満点システム）
Responsibility: A評価(3点) + B評価(33点: Eccentricのみ) = 計36点満点
Dependencies: base_evaluator_v2.py, test_rules_v2.json
Created: 2025-10-30 by Claude
Decision Log: Phase B - 8原則評価システム実装、Eccentricのみ評価（特殊構造）

CRITICAL: 8原則・Eccentricのみ評価、B2支持基盤・B6後方筋群が主評価
"""
import numpy as np
from typing import Dict, List
from datetime import datetime
from .base_evaluator_v2 import BaseEvaluatorV2


class JumpLandingEvaluatorV2(BaseEvaluatorV2):
    """
    What: ジャンプ着地評価クラス（v2: 8原則・36点満点）
    Why: A評価(3点) + B評価(33点) = 36点満点、Eccentric局面のみ評価（特殊構造）
    Design Decision: BaseEvaluatorV2継承、test_rules_v2.json使用、B2・B6主評価

    評価構造:
    - A. テスト実施の可否（3点）
      - ジャンプ高・着地バランス・転倒なし
    - B. 8原則評価（33点）
      - Eccentric（33点）: B1(4.0) + B2(9.0) + B3(4.0) + B4(4.0) + B6(12.0)
      - Concentric（なし）: 着地衝撃吸収のみ評価

    CRITICAL: 主評価（B2, B6: 9.0点+12.0点）、副評価（B1, B3, B4: 各4.0点）
    """

    def __init__(self, config_path: str = 'processing/evaluators_v2/config_v2/test_rules_v2.json'):
        """初期化"""
        super().__init__(config_path)
        if 'test_types' in self.rules and 'jump_landing' in self.rules['test_types']:
            self.test_config = self.rules['test_types']['jump_landing']
        else:
            self.test_config = {'test_id': 'T04', 'max_score': 36}

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float = None, leg_length: float = None, **kwargs) -> Dict:
        """総合評価"""
        if not landmarks_data:
            return {
                'version': 'v2',
                'test_id': 'T04_jump_landing',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'A_execution_score': 0.0,
                'B_total': 0.0,
                'total_score': 0.0,
                'total_percentage': 0,
                'max_possible': 36,
                'details': '姿勢が検出できませんでした'
            }

        section_a_result = self._evaluate_section_a(landmarks_data, base_width)
        knee_angles = self._extract_knee_angles(landmarks_data)
        phases = self._detect_landing_phase(landmarks_data, knee_angles)
        section_b_result = self._evaluate_section_b(landmarks_data, phases, base_width)

        total_score = section_a_result['score'] + section_b_result['total']
        total_percentage = int((total_score / 36) * 100)

        return {
            'version': 'v2',
            'test_id': 'T04_jump_landing',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'A_execution_score': section_a_result['score'],
            'A_breakdown': section_a_result['breakdown'],
            'B_principles': section_b_result['principles'],
            'B_total': section_b_result['total'],
            'total_score': round(total_score, 1),
            'total_percentage': total_percentage,
            'max_possible': 36,
            'special_structure': 'eccentric_only'
        }

    def _evaluate_section_a(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """A評価（3点満点）"""
        score = 0.0
        breakdown = {}

        jump_height_score = self._score_jump_height(landmarks_data, base_width)
        score += jump_height_score
        breakdown['jump_height'] = jump_height_score

        landing_balance_score = self._score_landing_balance(landmarks_data)
        score += landing_balance_score
        breakdown['landing_balance'] = landing_balance_score

        return {'score': round(score, 1), 'breakdown': breakdown}

    def _evaluate_section_b(self, landmarks_data: List[Dict], phases: Dict, base_width: float) -> Dict:
        """B評価（33点満点: Eccentricのみ）"""
        ecc_frames = phases['eccentric']['frames']
        ecc_data = [landmarks_data[i] for i in ecc_frames if i < len(landmarks_data)]
        ecc_scores = self._evaluate_principles(ecc_data, 'eccentric', base_width)

        total = sum(ecc_scores.values())
        return {'principles': {'eccentric': ecc_scores}, 'total': round(total, 1)}

    def _evaluate_principles(self, landmarks_data: List[Dict], phase: str, base_width: float) -> Dict:
        """8原則評価（B1, B2, B3, B4, B6）"""
        if not landmarks_data:
            return {
                'B1_core_stability': 0.0,
                'B2_support_foundation': 0.0,
                'B3_3joint_coordination': 0.0,
                'B4_pelvis_horizontal': 0.0,
                'B6_posterior_chain': 0.0
            }

        b1_score = self._evaluate_b1_core_stability(landmarks_data, max_score=4.0)
        b2_score = self._evaluate_b2_support_foundation(landmarks_data, max_score=9.0)
        b3_score = self._evaluate_b3_3joint_coordination(landmarks_data, max_score=4.0)
        b4_score = self._evaluate_b4_pelvis_horizontal(landmarks_data, max_score=4.0)
        b6_score = self._evaluate_b6_posterior_chain(landmarks_data, max_score=12.0)

        return {
            'B1_core_stability': round(b1_score, 1),
            'B2_support_foundation': round(b2_score, 1),
            'B3_3joint_coordination': round(b3_score, 1),
            'B4_pelvis_horizontal': round(b4_score, 1),
            'B6_posterior_chain': round(b6_score, 1)
        }

    # ==================== A評価ヘルパーメソッド ====================

    def _score_jump_height(self, landmarks_data: List[Dict], base_width: float) -> float:
        """ジャンプ高スコア（1.5点）"""
        hip_heights = []
        for frame_data in landmarks_data:
            left_hip = self._get_landmark(frame_data, self.LEFT_HIP)
            right_hip = self._get_landmark(frame_data, self.RIGHT_HIP)
            if left_hip and right_hip:
                avg_hip_y = (left_hip['y'] + right_hip['y']) / 2
                hip_heights.append(avg_hip_y)

        if not hip_heights:
            return 0.5

        # ジャンプ高 = 最低点と最高点の差
        min_hip_height = min(hip_heights)
        max_hip_height = max(hip_heights)
        jump_height = abs(max_hip_height - min_hip_height)

        # base_widthで正規化
        normalized_height = jump_height / base_width if base_width > 0 else 0

        if normalized_height > 0.6:
            return 1.5
        elif normalized_height > 0.4:
            return 1.0
        elif normalized_height > 0.2:
            return 0.5
        else:
            return 0.0

    def _score_landing_balance(self, landmarks_data: List[Dict]) -> float:
        """着地バランススコア（1.5点）"""
        # 着地後の腰の高さの安定性を評価
        # 後半30%のフレームを着地後とみなす
        landing_start = int(len(landmarks_data) * 0.7)
        landing_frames = landmarks_data[landing_start:]

        if not landing_frames:
            return 0.5

        hip_heights = []
        for frame_data in landing_frames:
            left_hip = self._get_landmark(frame_data, self.LEFT_HIP)
            right_hip = self._get_landmark(frame_data, self.RIGHT_HIP)
            if left_hip and right_hip:
                avg_hip_y = (left_hip['y'] + right_hip['y']) / 2
                hip_heights.append(avg_hip_y)

        if not hip_heights:
            return 0.5

        # 高さの標準偏差（小さいほど安定）
        std_dev = np.std(hip_heights)
        if std_dev < 0.02:
            return 1.5
        elif std_dev < 0.05:
            return 1.0
        elif std_dev < 0.10:
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
        """B2評価（支持基盤）- 主評価"""
        knee_angles = []
        ankle_widths = []

        for frame_data in landmarks_data:
            # 膝角度の安定性
            knee_angle = self._calculate_knee_angle(frame_data, side='right')
            if knee_angle > 0:
                knee_angles.append(knee_angle)

            # 足幅の安定性
            left_ankle = self._get_landmark(frame_data, self.LEFT_ANKLE)
            right_ankle = self._get_landmark(frame_data, self.RIGHT_ANKLE)
            if left_ankle and right_ankle:
                width = abs(left_ankle['x'] - right_ankle['x'])
                ankle_widths.append(width)

        if not knee_angles or not ankle_widths:
            return max_score * 0.5

        # 膝角度の標準偏差（着地時の安定性）
        knee_std = np.std(knee_angles)
        # 足幅の標準偏差（支持基盤の安定性）
        ankle_std = np.std(ankle_widths)

        score = max_score

        # 膝の安定性（小さいほど良い）
        if knee_std > 20:
            score -= max_score * 0.4
        elif knee_std > 10:
            score -= max_score * 0.2

        # 足幅の安定性（小さいほど良い）
        if ankle_std > 0.1:
            score -= max_score * 0.4
        elif ankle_std > 0.05:
            score -= max_score * 0.2

        return max(0.0, score)

    def _evaluate_b3_3joint_coordination(self, landmarks_data: List[Dict], max_score: float) -> float:
        """B3評価（3関節連動性）"""
        hip_angles = []
        knee_angles = []
        ankle_angles = []

        for frame_data in landmarks_data:
            hip_angle = self._calculate_hip_angle(frame_data, side='right')
            knee_angle = self._calculate_knee_angle(frame_data, side='right')
            ankle_angle = self._calculate_ankle_angle(frame_data, side='right')

            if hip_angle > 0 and knee_angle > 0 and ankle_angle > 0:
                hip_angles.append(hip_angle)
                knee_angles.append(knee_angle)
                ankle_angles.append(ankle_angle)

        if len(hip_angles) < 2 or len(knee_angles) < 2 or len(ankle_angles) < 2:
            return max_score * 0.5

        # 3関節の角度変化の相関（着地時の連動性）
        hip_changes = np.diff(hip_angles)
        knee_changes = np.diff(knee_angles)
        ankle_changes = np.diff(ankle_angles)

        if len(hip_changes) > 0 and len(knee_changes) > 0 and len(ankle_changes) > 0:
            min_len = min(len(hip_changes), len(knee_changes), len(ankle_changes))
            hip_knee_corr = np.corrcoef(hip_changes[:min_len], knee_changes[:min_len])[0, 1]
            knee_ankle_corr = np.corrcoef(knee_changes[:min_len], ankle_changes[:min_len])[0, 1]
            avg_correlation = (hip_knee_corr + knee_ankle_corr) / 2

            if avg_correlation > 0.7:
                return max_score
            elif avg_correlation > 0.5:
                return max_score * 0.75
            elif avg_correlation > 0.3:
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

    def _evaluate_b6_posterior_chain(self, landmarks_data: List[Dict], max_score: float) -> float:
        """B6評価（後方筋群活性化）- 主評価"""
        hip_angles = []
        knee_angles = []
        ankle_angles = []

        for frame_data in landmarks_data:
            hip_angle = self._calculate_hip_angle(frame_data, side='right')
            knee_angle = self._calculate_knee_angle(frame_data, side='right')
            ankle_angle = self._calculate_ankle_angle(frame_data, side='right')

            if hip_angle > 0:
                hip_angles.append(hip_angle)
            if knee_angle > 0:
                knee_angles.append(knee_angle)
            if ankle_angle > 0:
                ankle_angles.append(ankle_angle)

        if not hip_angles or not knee_angles or not ankle_angles:
            return max_score * 0.5

        # 着地時の股関節・膝関節の屈曲（後方筋群の活性化）
        # 屈曲が大きいほど後方筋群が衝撃を吸収している
        min_hip_angle = min(hip_angles)  # 最大屈曲
        min_knee_angle = min(knee_angles)  # 最大屈曲
        min_ankle_angle = min(ankle_angles)  # 最大底屈

        score = max_score

        # 股関節屈曲（90度以下で良好な衝撃吸収）
        if min_hip_angle > 120:  # 屈曲不足
            score -= max_score * 0.4
        elif min_hip_angle > 100:
            score -= max_score * 0.2

        # 膝関節屈曲（70-90度が理想的な衝撃吸収）
        if min_knee_angle > 120:  # 屈曲不足
            score -= max_score * 0.4
        elif min_knee_angle > 90:
            score -= max_score * 0.2

        # 足関節（衝撃吸収への寄与）
        if min_ankle_angle > 120:
            score -= max_score * 0.2

        return max(0.0, score)

    def _extract_knee_angles(self, landmarks_data: List[Dict]) -> List[float]:
        """膝角度抽出（局面検出用）"""
        knee_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_knee_angle(frame_data, side='right')
            knee_angles.append(angle)
        return knee_angles

    def _detect_landing_phase(self, landmarks_data: List[Dict], knee_angles: List[float]) -> Dict:
        """着地局面検出（Eccentricのみ）"""
        # ジャンプ着地は主に着地後の衝撃吸収（Eccentric）を評価
        # 全体の後半50%を着地局面とみなす
        mid_point = len(landmarks_data) // 2
        eccentric_frames = list(range(mid_point, len(landmarks_data)))

        return {
            'eccentric': {
                'frames': eccentric_frames,
                'description': '着地・衝撃吸収局面'
            }
        }
