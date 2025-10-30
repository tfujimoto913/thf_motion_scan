"""
Purpose: 片脚スタンススクワット評価ロジック（v2.1: 8原則・560点満点システム）
Responsibility: A評価(20点) + B評価(60点: Eccentric 30点 + Concentric 30点) = 計80点満点
Dependencies: base_evaluator_v2.py, test_rules_v2.json
Created: 2025-10-30 by Claude
Decision Log: Phase B - 8原則評価システム実装, v2.1 - 560点満点統一

CRITICAL: 8原則・局面別評価、既存v1システムとは完全分離
"""
import numpy as np
from typing import Dict, List
from datetime import datetime
from .base_evaluator_v2 import BaseEvaluatorV2


class SingleLegSquatEvaluatorV2(BaseEvaluatorV2):
    """
    What: 片脚スタンススクワット評価クラス（v2.1: 8原則・80点満点）
    Why: A評価(20点) + B評価(60点) = 80点満点、Eccentric/Concentric局面別評価
    Design Decision: BaseEvaluatorV2継承、test_rules_v2.json使用

    評価構造:
    - A. テスト実施の可否（20点）
      - A1: 可動域（10点）、A2: 完遂（10点）
    - B. 8原則評価（60点）
      - Eccentric（30点）: B1(5.0) + B2(10.0) + B3(5.0) + B4(10.0)
      - Concentric（30点）: B1(5.0) + B2(10.0) + B3(5.0) + B4(10.0)

    CRITICAL: 主評価（B2, B4: 各10点）、副評価（B1, B3: 各5点）
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
        if 'test_types' in self.rules and 'single_leg_squat' in self.rules['test_types']:
            self.test_config = self.rules['test_types']['single_leg_squat']
        else:
            # フォールバック（v2.1: 560点満点システム）
            self.test_config = {
                'test_id': 'T01',
                'max_score': 80,
                'section_a': {'max_score': 20},
                'section_b': {'max_score': 60}
            }

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float = None, leg_length: float = None, **kwargs) -> Dict:
        """
        What: 片脚スタンススクワット総合評価（v2.1システム - 560点満点）
        Why: A評価(20点) + B評価(60点) = 80点満点
        Design Decision: Eccentric/Concentric局面別評価

        Args:
            landmarks_data: フレームごとのランドマークデータ
            base_width: 正規化用基準幅（normalizer.pyから取得）
            shoulder_width: 肩幅（統一インターフェース）
            leg_length: 下肢長（統一インターフェース）
            **kwargs: 追加パラメータ

        Returns:
            Dict: {
                'version': 'v2.1',
                'test_id': 'T01_single_leg_squat',
                'timestamp': str,
                'A_execution_score': float (0-20),
                'A_breakdown': Dict,
                'B_principles': {
                    'eccentric': Dict,  # B1-B4のスコア
                    'concentric': Dict  # B1-B4のスコア
                },
                'B_total': float (0-60),
                'total_score': float (0-80),
                'total_percentage': int (0-100),
                'max_possible': 80
            }

        CRITICAL: landmarks_data空の場合はスコア0を返す
        """
        if not landmarks_data:
            return {
                'version': 'v2.1',
                'test_id': 'T01_single_leg_squat',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'A_execution_score': 0.0,
                'B_total': 0.0,
                'total_score': 0.0,
                'total_percentage': 0,
                'max_possible': 80,
                'details': '姿勢が検出できませんでした'
            }

        # PHASE CORE LOGIC: A評価（テスト実施の可否）
        section_a_result = self._evaluate_section_a(landmarks_data, base_width)

        # PHASE CORE LOGIC: 局面検出（Eccentric/Concentric）
        knee_angles = self._extract_knee_angles(landmarks_data)
        phases = self._detect_phases(landmarks_data, knee_angles)

        # PHASE CORE LOGIC: B評価（8原則評価、局面別）
        section_b_result = self._evaluate_section_b(landmarks_data, phases, base_width)

        # 総合スコア
        total_score = section_a_result['score'] + section_b_result['total']
        total_percentage = int((total_score / 80) * 100)

        return {
            'version': 'v2.1',
            'test_id': 'T01_single_leg_squat',
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
        """
        What: A評価（テスト実施の可否、20点満点）
        Why: セットアップ・深さ・安全性を評価
        Design Decision: v2.1で20点満点に統一

        Returns:
            Dict: {'score': float, 'breakdown': Dict}

        CRITICAL: 20点満点（各項目10点×2）
        """
        score = 0.0
        breakdown = {}

        # A1: 膝屈曲深さ（10点）
        knee_flexion_score = self._score_knee_flexion_depth(landmarks_data)
        score += knee_flexion_score
        breakdown['knee_flexion_angle'] = knee_flexion_score

        # A2: 完遂回数（10点）
        completion_score = self._score_completion(landmarks_data)
        score += completion_score
        breakdown['completion_reps'] = completion_score

        return {
            'score': round(score, 1),
            'breakdown': breakdown
        }

    def _evaluate_section_b(self, landmarks_data: List[Dict], phases: Dict, base_width: float) -> Dict:
        """
        What: B評価（8原則評価、60点満点）
        Why: Eccentric/Concentric局面別評価
        Design Decision: B1-B4の4原則を局面別に評価

        Args:
            phases: {'eccentric': {...}, 'concentric': {...}}

        Returns:
            Dict: {
                'principles': {
                    'eccentric': {'B1': float, 'B2': float, 'B3': float, 'B4': float},
                    'concentric': {'B1': float, 'B2': float, 'B3': float, 'B4': float}
                },
                'total': float
            }

        CRITICAL: v2.1 - Eccentric 30点 + Concentric 30点 = 60点
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
        What: 8原則評価（B1-B4）
        Why: 各原則ごとのスコア計算
        Design Decision: single_leg_squatでは4原則のみ適用

        Args:
            phase: 'eccentric' or 'concentric'

        Returns:
            Dict: {'B1_core_stability': float, 'B2_support_foundation': float, ...}

        CRITICAL: v2.1 - Eccentric/Concentric各30点（主評価10点×2 + 副評価5点×2）
        """
        if not landmarks_data:
            return {
                'B1_core_stability': 0.0,
                'B2_support_foundation': 0.0,
                'B3_3joint_coordination': 0.0,
                'B4_pelvis_horizontal': 0.0
            }

        # B1: 体幹安定性（副評価: 5.0点）
        b1_score = self._evaluate_b1_core_stability(landmarks_data, max_score=5.0)

        # B2: 支持基盤（主評価: 10.0点）
        b2_score = self._evaluate_b2_support_foundation(landmarks_data, max_score=10.0)

        # B3: 3関節連動性（副評価: 5.0点）
        b3_score = self._evaluate_b3_3joint_coordination(landmarks_data, max_score=5.0)

        # B4: 骨盤水平維持（主評価: 10.0点）
        b4_score = self._evaluate_b4_pelvis_horizontal(landmarks_data, max_score=10.0)

        return {
            'B1_core_stability': round(b1_score, 1),
            'B2_support_foundation': round(b2_score, 1),
            'B3_3joint_coordination': round(b3_score, 1),
            'B4_pelvis_horizontal': round(b4_score, 1)
        }

    # ==================== A評価ヘルパーメソッド ====================

    def _score_knee_flexion_depth(self, landmarks_data: List[Dict]) -> float:
        """
        What: 膝屈曲深さスコア（10点）
        Why: テスト実施の完全性を評価
        Design Decision: 最小膝角度で評価

        CRITICAL: v2.1 - 10点満点（A1評価）
        """
        knee_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_knee_angle(frame_data, side='right')
            if angle > 0:
                knee_angles.append(angle)

        if not knee_angles:
            return 0.0

        min_angle = min(knee_angles)

        # スコアリング（v2.1: 10点満点）
        if min_angle < 90:
            return 10.0
        elif min_angle < 120:
            return 6.7
        elif min_angle < 150:
            return 3.3
        else:
            return 0.0

    def _score_completion(self, landmarks_data: List[Dict]) -> float:
        """
        What: 完遂回数スコア（10点）
        Why: テスト実施の完全性を評価
        Design Decision: フレーム数から完遂回数を推定

        CRITICAL: v2.1 - 10点満点（A2評価）
        """
        # 簡易実装: フレーム数から完遂回数を推定
        # 通常1回のスクワット = 約3秒 = 180フレーム（60fps想定）
        estimated_reps = len(landmarks_data) / 180

        if estimated_reps >= 3:
            return 10.0
        elif estimated_reps >= 2:
            return 6.7
        elif estimated_reps >= 1:
            return 3.3
        else:
            return 0.0

    # ==================== B評価ヘルパーメソッド ====================

    def _evaluate_b1_core_stability(self, landmarks_data: List[Dict], max_score: float) -> float:
        """
        What: B1評価（体幹安定性）
        Why: 体幹の揺れ・回旋を評価
        Design Decision: 体幹回旋角度と肩の高低差

        CRITICAL: v2.1 - max_score点満点（副評価: 5.0点）
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
            return 0.0

        avg_rotation = np.mean(trunk_rotations)
        avg_shoulder_diff = np.mean(shoulder_diffs)

        # スコアリング
        score = max_score

        # 体幹回旋ペナルティ
        if avg_rotation > 20:
            score -= max_score * 0.5
        elif avg_rotation > 10:
            score -= max_score * 0.25

        # 肩の高低差ペナルティ
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

        CRITICAL: v2.1 - max_score点満点（主評価: 10.0点）
        """
        knee_angles = []

        for frame_data in landmarks_data:
            angle = self._calculate_knee_angle(frame_data, side='right')
            if angle > 0:
                knee_angles.append(angle)

        if not knee_angles:
            return 0.0

        # 膝角度の標準偏差（安定性指標）
        std_dev = np.std(knee_angles)

        # スコアリング
        score = max_score

        if std_dev > 15:
            score -= max_score * 0.5
        elif std_dev > 10:
            score -= max_score * 0.3
        elif std_dev > 5:
            score -= max_score * 0.15

        return max(0.0, score)

    def _evaluate_b3_3joint_coordination(self, landmarks_data: List[Dict], max_score: float) -> float:
        """
        What: B3評価（3関節連動性）
        Why: 股・膝・足関節の協調動作を評価
        Design Decision: 股関節と膝関節の角度変化パターン

        CRITICAL: v2.1 - max_score点満点（副評価: 5.0点）
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
            return max_score * 0.5  # デフォルト50%

        # 角度変化の相関性（簡易実装）
        hip_changes = np.diff(hip_angles)
        knee_changes = np.diff(knee_angles)

        # 相関係数計算
        if len(hip_changes) > 0 and len(knee_changes) > 0:
            min_len = min(len(hip_changes), len(knee_changes))
            correlation = np.corrcoef(hip_changes[:min_len], knee_changes[:min_len])[0, 1]

            # スコアリング
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

        CRITICAL: v2.1 - max_score点満点（主評価: 10.0点）
        """
        hip_diffs = []

        for frame_data in landmarks_data:
            hip_diff = self._calculate_hip_height_diff(frame_data)
            if hip_diff > 0:
                hip_diffs.append(hip_diff)

        if not hip_diffs:
            return 0.0

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

    # ==================== ヘルパーメソッド ====================

    def _extract_knee_angles(self, landmarks_data: List[Dict]) -> List[float]:
        """
        What: 全フレームから膝角度を抽出
        Why: 局面検出に使用
        Design Decision: 右脚の膝角度を使用

        CRITICAL: 局面検出のため
        """
        knee_angles = []
        for frame_data in landmarks_data:
            angle = self._calculate_knee_angle(frame_data, side='right')
            knee_angles.append(angle)
        return knee_angles
