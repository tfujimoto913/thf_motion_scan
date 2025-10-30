"""
Purpose: スケーターランジ評価ロジック（v2: 8原則・237点満点システム）
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


class SkaterLungeEvaluatorV2(BaseEvaluatorV2):
    """
    What: スケーターランジ評価クラス（v2: 8原則・33点満点）
    Why: A評価(3点) + B評価(30点) = 33点満点、Eccentric/Concentric局面別評価
    Design Decision: BaseEvaluatorV2継承、test_rules_v2.json使用

    評価構造:
    - A. テスト実施の可否（3点）
      - ステップ幅・着地安定性・転倒なし
    - B. 8原則評価（30点）
      - Eccentric（15点）: B1(2.0) + B2(2.0) + B3(2.0) + B4(4.5) + B7(4.5)
      - Concentric（15点）: B1(2.0) + B2(2.0) + B3(2.0) + B4(4.5) + B7(4.5)

    CRITICAL: 主評価（B4, B7: 各4.5点）、副評価（B1, B2, B3: 各2.0点）
    """

    def __init__(self, config_path: str = 'processing/evaluators_v2/config_v2/test_rules_v2.json'):
        """
        What: 設定ファイル読み込み
        Why: test_rules_v2.jsonから種目別ルールを取得
        Design Decision: 親クラスの初期化を呼び出し

        CRITICAL: Phase B実装
        """
        super().__init__(config_path)

        # 種目固有の設定
        if 'test_types' in self.rules and 'skater_lunge' in self.rules['test_types']:
            self.test_config = self.rules['test_types']['skater_lunge']
        else:
            # フォールバック
            self.test_config = {
                'test_id': 'T02',
                'max_score': 33,
                'section_a': {'max_score': 3},
                'section_b': {'max_score': 30}
            }

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float = None, leg_length: float = None, **kwargs) -> Dict:
        """
        What: スケーターランジ総合評価（v2システム）
        Why: A評価(3点) + B評価(30点) = 33点満点
        Design Decision: Eccentric/Concentric局面別評価

        Args:
            landmarks_data: フレームごとのランドマークデータ
            base_width: 正規化用基準幅（normalizer.pyから取得）
            shoulder_width: 肩幅（統一インターフェース）
            leg_length: 下肢長（統一インターフェース）
            **kwargs: 追加パラメータ

        Returns:
            Dict: {
                'version': 'v2',
                'test_id': 'T02_skater_lunge',
                'timestamp': str,
                'A_execution_score': float (0-3),
                'A_breakdown': Dict,
                'B_principles': {
                    'eccentric': Dict,  # B1-B4, B7のスコア
                    'concentric': Dict  # B1-B4, B7のスコア
                },
                'B_total': float (0-30),
                'total_score': float (0-33),
                'total_percentage': int (0-100),
                'max_possible': 33
            }

        CRITICAL: landmarks_data空の場合はスコア0を返す
        """
        if not landmarks_data:
            return {
                'version': 'v2',
                'test_id': 'T02_skater_lunge',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'A_execution_score': 0.0,
                'B_total': 0.0,
                'total_score': 0.0,
                'total_percentage': 0,
                'max_possible': 33,
                'details': '姿勢が検出できませんでした'
            }

        # PHASE CORE LOGIC: A評価（テスト実施の可否）
        section_a_result = self._evaluate_section_a(landmarks_data, base_width)

        # PHASE CORE LOGIC: 局面検出（Eccentric/Concentric）
        hip_angles = self._extract_hip_angles(landmarks_data)
        phases = self._detect_phases(landmarks_data, hip_angles)

        # PHASE CORE LOGIC: B評価（8原則評価、局面別）
        section_b_result = self._evaluate_section_b(landmarks_data, phases, base_width)

        # 総合スコア
        total_score = section_a_result['score'] + section_b_result['total']
        total_percentage = int((total_score / 33) * 100)

        return {
            'version': 'v2',
            'test_id': 'T02_skater_lunge',
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
        """
        What: A評価（テスト実施の可否、3点満点）
        Why: ステップ幅・着地安定性・転倒なしを評価
        Design Decision: 横方向ステップ幅と着地時の膝安定性

        Returns:
            Dict: {'score': float, 'breakdown': Dict}

        CRITICAL: 3点満点
        """
        score = 0.0
        breakdown = {}

        # A1: ステップ幅（1.5点）
        step_width_score = self._score_step_width(landmarks_data, base_width)
        score += step_width_score
        breakdown['step_width'] = step_width_score

        # A2: 着地安定性（1.5点）
        landing_score = self._score_landing_stability(landmarks_data)
        score += landing_score
        breakdown['landing_stability'] = landing_score

        return {
            'score': round(score, 1),
            'breakdown': breakdown
        }

    def _evaluate_section_b(self, landmarks_data: List[Dict], phases: Dict, base_width: float) -> Dict:
        """
        What: B評価（8原則評価、30点満点）
        Why: Eccentric/Concentric局面別評価
        Design Decision: B1-B4, B7の5原則を局面別に評価

        Args:
            phases: {'eccentric': {...}, 'concentric': {...}}

        Returns:
            Dict: {
                'principles': {
                    'eccentric': {'B1': float, 'B2': float, 'B3': float, 'B4': float, 'B7': float},
                    'concentric': {'B1': float, 'B2': float, 'B3': float, 'B4': float, 'B7': float}
                },
                'total': float
            }

        CRITICAL: Eccentric 15点 + Concentric 15点 = 30点
        """
        # Eccentric局面評価
        ecc_frames = phases['eccentric']['frames']
        ecc_data = [landmarks_data[i] for i in ecc_frames if i < len(landmarks_data)]
        ecc_scores = self._evaluate_principles(ecc_data, 'eccentric', base_width)

        # Concentric局面評価
        con_frames = phases['concentric']['frames']
        con_data = [landmarks_data[i] for i in con_frames if i < len(landmarks_data)]
        con_scores = self._evaluate_principles(con_data, 'concentric', base_width)

        # 合計スコア
        total = sum(ecc_scores.values()) + sum(con_scores.values())

        return {
            'principles': {
                'eccentric': ecc_scores,
                'concentric': con_scores
            },
            'total': round(total, 1)
        }

    def _evaluate_principles(self, landmarks_data: List[Dict], phase: str, base_width: float) -> Dict:
        """
        What: 8原則評価（B1-B4, B7）
        Why: 各原則ごとのスコア計算
        Design Decision: skater_lungeでは5原則を適用

        Args:
            phase: 'eccentric' or 'concentric'

        Returns:
            Dict: {'B1_core_stability': float, 'B2_support_foundation': float, ...}

        CRITICAL: Eccentric/Concentric各15点
        """
        if not landmarks_data:
            return {
                'B1_core_stability': 0.0,
                'B2_support_foundation': 0.0,
                'B3_3joint_coordination': 0.0,
                'B4_pelvis_horizontal': 0.0,
                'B7_upper_lower_separation': 0.0
            }

        # B1: 体幹安定性（副評価: 2.0点）
        b1_score = self._evaluate_b1_core_stability(landmarks_data, max_score=2.0)

        # B2: 支持基盤（副評価: 2.0点）
        b2_score = self._evaluate_b2_support_foundation(landmarks_data, max_score=2.0)

        # B3: 3関節連動性（副評価: 2.0点）
        b3_score = self._evaluate_b3_3joint_coordination(landmarks_data, max_score=2.0)

        # B4: 骨盤水平維持（主評価: 4.5点）
        b4_score = self._evaluate_b4_pelvis_horizontal(landmarks_data, max_score=4.5)

        # B7: 上下身分離性（主評価: 4.5点）
        b7_score = self._evaluate_b7_upper_lower_separation(landmarks_data, max_score=4.5)

        return {
            'B1_core_stability': round(b1_score, 1),
            'B2_support_foundation': round(b2_score, 1),
            'B3_3joint_coordination': round(b3_score, 1),
            'B4_pelvis_horizontal': round(b4_score, 1),
            'B7_upper_lower_separation': round(b7_score, 1)
        }

    # ==================== A評価ヘルパーメソッド ====================

    def _score_step_width(self, landmarks_data: List[Dict], base_width: float) -> float:
        """
        What: ステップ幅スコア（1.5点）
        Why: 横方向ステップ幅を評価
        Design Decision: 左右足首の横方向移動距離

        CRITICAL: 1.5点満点
        """
        step_widths = []

        for i in range(1, len(landmarks_data)):
            prev_frame = landmarks_data[i-1]
            curr_frame = landmarks_data[i]

            left_ankle_prev = self._get_landmark(prev_frame, self.LEFT_ANKLE)
            right_ankle_prev = self._get_landmark(prev_frame, self.RIGHT_ANKLE)
            left_ankle_curr = self._get_landmark(curr_frame, self.LEFT_ANKLE)
            right_ankle_curr = self._get_landmark(curr_frame, self.RIGHT_ANKLE)

            if all([left_ankle_prev, right_ankle_prev, left_ankle_curr, right_ankle_curr]):
                # 横方向（x座標）の移動距離
                left_move = abs(left_ankle_curr['x'] - left_ankle_prev['x'])
                right_move = abs(right_ankle_curr['x'] - right_ankle_prev['x'])
                step_width = max(left_move, right_move)
                step_widths.append(step_width)

        if not step_widths:
            return 0.5  # デフォルト

        avg_step_width = np.mean(step_widths)
        normalized_width = avg_step_width / base_width if base_width > 0 else 0

        # スコアリング
        if normalized_width > 0.8:
            return 1.5
        elif normalized_width > 0.6:
            return 1.0
        elif normalized_width > 0.4:
            return 0.5
        else:
            return 0.0

    def _score_landing_stability(self, landmarks_data: List[Dict]) -> float:
        """
        What: 着地安定性スコア（1.5点）
        Why: 着地時の膝・足首の安定性を評価
        Design Decision: 膝角度の変動を評価

        CRITICAL: 1.5点満点
        """
        knee_angles = []

        for frame_data in landmarks_data:
            # 支持脚の膝角度を計算（簡易実装：右脚）
            angle = self._calculate_knee_angle(frame_data, side='right')
            if angle > 0:
                knee_angles.append(angle)

        if not knee_angles:
            return 0.5  # デフォルト

        # 膝角度の標準偏差（安定性指標）
        std_dev = np.std(knee_angles)

        # スコアリング
        if std_dev < 10:
            return 1.5
        elif std_dev < 20:
            return 1.0
        elif std_dev < 30:
            return 0.5
        else:
            return 0.0

    # ==================== B評価ヘルパーメソッド ====================

    def _evaluate_b1_core_stability(self, landmarks_data: List[Dict], max_score: float) -> float:
        """
        What: B1評価（体幹安定性）
        Why: 体幹の揺れ・回旋を評価
        Design Decision: 体幹回旋角度と肩の高低差

        CRITICAL: max_score点満点（副評価: 2.0点）
        """
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

        # スコアリング
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
        """
        What: B2評価（支持基盤）
        Why: 支持脚の安定性を評価
        Design Decision: 膝角度の安定性（標準偏差）

        CRITICAL: max_score点満点（副評価: 2.0点）
        """
        knee_angles = []

        for frame_data in landmarks_data:
            angle = self._calculate_knee_angle(frame_data, side='right')
            if angle > 0:
                knee_angles.append(angle)

        if not knee_angles:
            return max_score * 0.5

        std_dev = np.std(knee_angles)

        # スコアリング
        score = max_score

        if std_dev > 15:
            score -= max_score * 0.5
        elif std_dev > 10:
            score -= max_score * 0.3

        return max(0.0, score)

    def _evaluate_b3_3joint_coordination(self, landmarks_data: List[Dict], max_score: float) -> float:
        """
        What: B3評価（3関節連動性）
        Why: 股・膝・足関節の協調動作を評価
        Design Decision: 股関節と膝関節の角度変化パターン

        CRITICAL: max_score点満点（副評価: 2.0点）
        """
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

        # 相関係数計算
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
        """
        What: B4評価（骨盤水平維持）
        Why: 骨盤の左右高低差を評価
        Design Decision: 左右腰の高低差

        CRITICAL: max_score点満点（主評価: 4.5点）
        """
        hip_diffs = []

        for frame_data in landmarks_data:
            hip_diff = self._calculate_hip_height_diff(frame_data)
            if hip_diff > 0:
                hip_diffs.append(hip_diff)

        if not hip_diffs:
            return max_score * 0.5

        avg_hip_diff = np.mean(hip_diffs)

        # スコアリング
        score = max_score

        if avg_hip_diff > 0.15:
            score -= max_score * 0.6
        elif avg_hip_diff > 0.10:
            score -= max_score * 0.4
        elif avg_hip_diff > 0.05:
            score -= max_score * 0.2

        return max(0.0, score)

    def _evaluate_b7_upper_lower_separation(self, landmarks_data: List[Dict], max_score: float) -> float:
        """
        What: B7評価（上下身分離性）
        Why: 上半身と下半身の独立動作を評価
        Design Decision: 体幹回旋と骨盤回旋の差

        CRITICAL: max_score点満点（主評価: 4.5点）
        """
        separation_angles = []

        for frame_data in landmarks_data:
            # 体幹回旋角度
            trunk_rotation = self._calculate_trunk_rotation(frame_data)

            # 骨盤回旋角度（簡易実装: 左右腰のx座標差）
            left_hip = self._get_landmark(frame_data, self.LEFT_HIP)
            right_hip = self._get_landmark(frame_data, self.RIGHT_HIP)

            if left_hip and right_hip and trunk_rotation > 0:
                hip_rotation = abs(np.degrees(np.arctan2(
                    right_hip['z'] - left_hip['z'],
                    right_hip['x'] - left_hip['x']
                )))

                # 体幹と骨盤の角度差（分離性の指標）
                separation = abs(trunk_rotation - hip_rotation)
                separation_angles.append(separation)

        if not separation_angles:
            return max_score * 0.5

        avg_separation = np.mean(separation_angles)

        # スコアリング（分離性が高いほど高得点）
        score = max_score

        if avg_separation < 5:  # 分離性が低い
            score -= max_score * 0.6
        elif avg_separation < 10:
            score -= max_score * 0.3
        elif avg_separation < 15:
            score -= max_score * 0.15

        return max(0.0, score)

    # ==================== ヘルパーメソッド ====================

    def _extract_hip_angles(self, landmarks_data: List[Dict]) -> List[float]:
        """
        What: 全フレームから股関節角度を抽出
        Why: 局面検出に使用
        Design Decision: 右脚の股関節角度を使用

        CRITICAL: 局面検出のため
        """
        hip_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_hip_angle(frame_data, side='right')
            hip_angles.append(angle)
        return hip_angles
