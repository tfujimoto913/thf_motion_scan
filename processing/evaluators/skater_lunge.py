"""
Purpose: スケーターランジ評価ロジック（2軸評価システム）
Responsibility: A.動作完全性(3点) + B.7原則達成度(9点) = 計12点満点
Dependencies: numpy, config.json, normalizer.py
Created: 2025-10-19 by Claude
Updated: 2025-10-26 - 2軸評価システム実装
Decision Log: ADR-002, ADR-003

CRITICAL: 全て客観的指標のみ使用（距離・角度・標準偏差）、主観的指標禁止
"""
import numpy as np
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from math import sqrt, acos, atan2, degrees


class SkaterLungeEvaluator:
    """
    What: スケーターランジ評価クラス（2軸評価システム）
    Why: A.動作完全性(3点) + B.7原則達成度(9点) = 計12点満点
    Design Decision: config.json閾値参照、全て客観的指標のみ使用

    評価構造:
    - A. 動作完全性（3点）
      - A1. ステップ幅（1.0点）
      - A2. 非荷重脚の完全離地（1.0点）
      - A3. 完遂回数（1.0点）
    - B. 7原則達成度（9点）
      - B1. 原則#5 内外転筋+骨盤側方シフト（3点）
      - B2. 原則#4 骨盤水平維持（3点）
      - B3. 原則#2 下半身安定性（3点）

    CRITICAL: 主観的指標禁止、全て距離・角度・標準偏差で評価
    """

    # CRITICAL: MediaPipeランドマークインデックス定義（削除禁止）
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
        What: config.json読み込みと閾値初期化
        Why: 閾値外部化によるデータ整合性保証
        Design Decision: T02_skater_lunge閾値使用

        Args:
            config_path: config.jsonのパス

        CRITICAL: config_path変更時は全テスト更新必須
        """
        # PHASE CORE LOGIC: config.json読み込み
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"config.json not found: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        # CRITICAL: T02_skater_lunge閾値取得
        self.thresholds = self.config['thresholds']['T02_skater_lunge']

    def evaluate(self, landmarks_data: List[Dict], base_width: float, leg_length: float) -> Dict:
        """
        What: スケーターランジ総合評価（2軸システム）
        Why: A評価(3点) + B評価(9点) = 計12点満点
        Design Decision: 2軸評価システム

        Args:
            landmarks_data: フレームごとのランドマークデータ
            base_width: 正規化用基準幅（normalizer.pyから取得）
            leg_length: 正規化用下肢長（normalizer.pyから取得）

        Returns:
            Dict: {
                'test_id': str,
                'execution': Dict,      # A評価: 0-3点
                'principles': Dict,     # B評価: 0-9点
                'total': float,         # 総合: 0-12点
                'max_score': float
            }

        CRITICAL: landmarks_data空の場合はスコア0を返す
        """
        if not landmarks_data:
            return {
                'test_id': 'T02_skater_lunge',
                'execution': {'total': 0.0},
                'principles': {'total': 0.0},
                'total': 0.0,
                'max_score': 12.0,
                'details': '姿勢が検出できませんでした'
            }

        # PHASE CORE LOGIC: A評価（動作完全性）
        execution = self.evaluate_execution(landmarks_data, leg_length)

        # PHASE CORE LOGIC: B評価（7原則達成度）
        principles = self.evaluate_principles(landmarks_data, base_width)

        # 総合スコア
        total_score = execution['total'] + principles['total']

        return {
            'test_id': 'T02_skater_lunge',
            'execution': execution,
            'principles': principles,
            'total': total_score,
            'max_score': 12.0
        }

    def evaluate_execution(self, landmarks_data: List[Dict], leg_length: float) -> Dict:
        """
        What: A. 動作完全性評価（3点）
        Why: ステップ幅(1.0点) + 非荷重脚離地(1.0点) + 完遂回数(1.0点)
        Design Decision: 客観的指標のみ（距離測定・角度測定・カウント）

        Returns:
            Dict: {
                'step_width': {'value': float, 'score': float, 'max': float},
                'unloaded_leg_lift': {'value': str, 'score': float, 'max': float},
                'completion': {'value': Dict, 'score': float, 'max': float},
                'total': float
            }

        CRITICAL: 主観性チェック済み - 全て客観的指標
        """
        # A1. ステップ幅（1.0点）
        step_width = self._score_step_width(landmarks_data)

        # A2. 非荷重脚の完全離地（1.0点）
        lift = self._score_unloaded_leg_lift(landmarks_data, leg_length)

        # A3. 完遂回数（1.0点）
        completion = self._score_completion(landmarks_data)

        return {
            'step_width': step_width,
            'unloaded_leg_lift': lift,
            'completion': completion,
            'total': step_width['score'] + lift['score'] + completion['score']
        }

    def evaluate_principles(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """
        What: B. 7原則達成度評価（9点）
        Why: P5(3点) + P4(3点) + P2(3点) = 9点
        Design Decision: 客観的指標のみ

        Args:
            base_width: 正規化用基準幅

        Returns:
            Dict: {
                'P5_pelvis_shift': {'score': float, 'max': float, ...},
                'P4_pelvis_level': {'score': float, 'max': float, ...},
                'P2_stability': {'score': float, 'max': float, ...},
                'total': float
            }

        CRITICAL: 主観性チェック済み - 全て客観的指標
        """
        # B1. 原則#5: 内外転筋+骨盤側方シフト（3点）
        p5 = self._evaluate_principle_5(landmarks_data, base_width)

        # B2. 原則#4: 骨盤水平維持（3点）
        p4 = self._evaluate_principle_4(landmarks_data, base_width)

        # B3. 原則#2: 下半身安定性（3点）
        p2 = self._evaluate_principle_2(landmarks_data, base_width)

        return {
            'P5_pelvis_shift': p5,
            'P4_pelvis_level': p4,
            'P2_stability': p2,
            'total': p5['score'] + p4['score'] + p2['score']
        }

    # ==================== A評価: 動作完全性 ====================

    def _score_step_width(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: A1. ステップ幅評価（1.0点）
        Why: 左右への移動距離が肩幅の何倍か
        Design Decision: config.json閾値使用（excellent: 1.5, good: 1.2, fair: 1.0）

        Returns:
            {'value': float (ratio), 'score': float, 'max': 1.0}

        CRITICAL: 主観性チェック ✅ 客観的（距離測定のみ）
        """
        ratio = self._calculate_step_width(landmarks_data)

        # スコアリング
        thresholds = self.thresholds['execution']['step_width']
        if ratio >= thresholds['excellent']:
            score = 1.0
        elif ratio >= thresholds['good']:
            score = 0.7
        elif ratio >= thresholds['fair']:
            score = 0.4
        else:
            score = 0.0

        return {'value': ratio, 'score': score, 'max': 1.0}

    def _score_unloaded_leg_lift(self, landmarks_data: List[Dict], leg_length: float) -> Dict:
        """
        What: A2. 非荷重脚の完全離地評価（1.0点）
        Why: 片脚荷重時に反対側の脚が完全に浮いているか
        Design Decision: 膝伸展(>140°) & 足首浮き(>10%下肢長)

        Returns:
            {'value': str, 'score': float, 'max': 1.0}

        CRITICAL: 主観性チェック ✅ 客観的（角度と高さの測定）
        """
        # 左右それぞれでチェック
        left_lift = self._detect_unloaded_leg_lift(landmarks_data, leg_length, side='left')
        right_lift = self._detect_unloaded_leg_lift(landmarks_data, leg_length, side='right')

        if left_lift and right_lift:
            return {'value': 'both_lifted', 'score': 1.0, 'max': 1.0}
        elif left_lift or right_lift:
            return {'value': 'partial', 'score': 0.5, 'max': 1.0}
        else:
            return {'value': 'none', 'score': 0.0, 'max': 1.0}

    def _score_completion(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: A3. 完遂回数評価（1.0点）
        Why: 左右各何回ランジを完遂したか
        Design Decision: 左右の最小値を採用

        Returns:
            {'value': Dict, 'score': float, 'max': 1.0}

        CRITICAL: 主観性チェック ✅ 客観的（位置追跡とカウント）
        """
        cycles = self._count_lunge_cycles(landmarks_data)
        min_cycles = min(cycles['right'], cycles['left'])

        # スコアリング
        target = self.thresholds['execution']['completion']['target']
        if min_cycles >= target:
            score = 1.0
        elif min_cycles >= 3:
            score = 0.6
        elif min_cycles >= 1:
            score = 0.3
        else:
            score = 0.0

        return {'value': cycles, 'score': score, 'max': 1.0}

    # ==================== B評価: 7原則達成度 ====================

    def _evaluate_principle_5(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """
        What: B1. 原則#5 内外転筋+骨盤側方シフト（3点）
        Why: 骨盤が荷重脚の真上まで移動できているか（最重要指標）
        Design Decision: シフト率 >= 90%で満点

        Returns:
            {
                'shift_rate': {'value': float, 'unit': 'percent'},
                'score': float,
                'max': 3.0
            }

        CRITICAL: 主観性チェック ✅ 客観的（距離比率の計算）
        """
        shift_rate = self._calculate_pelvis_shift_rate(landmarks_data)

        thresholds = self.thresholds['principles']['P5_pelvis_shift']
        if shift_rate >= thresholds['excellent']:
            score = 3.0
        elif shift_rate >= thresholds['good']:
            score = 2.0
        elif shift_rate >= thresholds['fair']:
            score = 1.0
        else:
            score = 0.0

        return {
            'shift_rate': {'value': shift_rate, 'unit': 'percent'},
            'score': score,
            'max': 3.0
        }

    def _evaluate_principle_4(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """
        What: B2. 原則#4 骨盤水平維持（3点）
        Why: Trendelenburg徴候（非荷重側骨盤の沈下）を評価
        Design Decision: base_widthで正規化

        Returns:
            {
                'trendelenburg': {'value': float, 'unit': 'ratio'},
                'score': float,
                'max': 3.0
            }

        CRITICAL: 主観性チェック ✅ 客観的（高さ差測定）
        """
        max_drop = self._calculate_trendelenburg_skater(landmarks_data, base_width)

        score = 3.0

        thresholds = self.thresholds['principles']['P4_pelvis_level']['trendelenburg']
        if max_drop > thresholds['moderate']:
            score = 1.0
        elif max_drop > thresholds['mild']:
            score = 2.0

        return {
            'trendelenburg': {'value': max_drop, 'unit': 'ratio'},
            'score': score,
            'max': 3.0
        }

    def _evaluate_principle_2(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """
        What: B3. 原則#2 下半身安定性（3点）
        Why: 荷重時の骨盤横方向ブレを評価
        Design Decision: 標準偏差で安定性評価

        Returns:
            {
                'lateral_stability': {'value': float, 'unit': 'ratio'},
                'score': float,
                'max': 3.0
            }

        CRITICAL: 主観性チェック ✅ 客観的（標準偏差測定）
        """
        stability = self._calculate_lateral_stability_skater(landmarks_data, base_width)

        score = 3.0

        thresholds = self.thresholds['principles']['P2_stability']['lateral_stability']
        if stability > thresholds['moderate']:
            score = 1.0
        elif stability > thresholds['excellent']:
            score = 2.0

        return {
            'lateral_stability': {'value': stability, 'unit': 'ratio'},
            'score': score,
            'max': 3.0
        }

    # ==================== ヘルパー関数 ====================

    def _calculate_step_width(self, landmarks_data: List[Dict]) -> float:
        """
        What: ステップ幅計算（肩幅に対する比率）
        Why: A1評価用
        Design Decision: 足首X座標の最大移動距離 / 肩幅

        Returns:
            float: ステップ幅比率

        CRITICAL: 主観性チェック ✅ 客観的（距離測定）
        """
        if not landmarks_data:
            return 0.0

        # 肩幅計算
        first_frame = landmarks_data[0]['landmarks']
        left_shoulder = first_frame[self.LEFT_SHOULDER]
        right_shoulder = first_frame[self.RIGHT_SHOULDER]

        shoulder_width = sqrt(
            (right_shoulder['x'] - left_shoulder['x'])**2 +
            (right_shoulder['y'] - left_shoulder['y'])**2
        )

        if shoulder_width == 0:
            return 0.0

        # 足首位置追跡
        ankle_x_positions = []
        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
                # 両足首のX座標を記録
                left_ankle = landmarks[self.LEFT_ANKLE]
                right_ankle = landmarks[self.RIGHT_ANKLE]
                ankle_x_positions.append(left_ankle['x'])
                ankle_x_positions.append(right_ankle['x'])

        if not ankle_x_positions:
            return 0.0

        # 最大移動距離
        min_x = min(ankle_x_positions)
        max_x = max(ankle_x_positions)
        step_width = max_x - min_x

        # 肩幅に対する比率
        return float(step_width / shoulder_width)

    def _detect_unloaded_leg_lift(self, landmarks_data: List[Dict],
                                    leg_length: float, side: str) -> bool:
        """
        What: 非荷重脚の離地判定
        Why: A2評価用
        Design Decision: 膝伸展(>140°) & 足首浮き(>10%下肢長)

        Args:
            side: 'left' or 'right'

        Returns:
            bool: 離地を検出したか

        CRITICAL: 主観性チェック ✅ 客観的（角度+高さ測定）
        """
        if leg_length == 0:
            return False

        thresholds = self.thresholds['execution']['unloaded_leg']
        knee_threshold = thresholds['knee_angle_threshold']
        height_threshold = thresholds['height_ratio_threshold']

        hip_idx = self.LEFT_HIP if side == 'left' else self.RIGHT_HIP
        knee_idx = self.LEFT_KNEE if side == 'left' else self.RIGHT_KNEE
        ankle_idx = self.LEFT_ANKLE if side == 'left' else self.RIGHT_ANKLE

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(hip_idx, knee_idx, ankle_idx):
                hip = landmarks[hip_idx]
                knee = landmarks[knee_idx]
                ankle = landmarks[ankle_idx]

                # 条件1: 膝伸展角度
                knee_angle = self._calculate_knee_angle(hip, knee, ankle)
                if knee_angle is None:
                    continue

                knee_extended = knee_angle > knee_threshold

                # 条件2: 足首高さ（MediaPipeは上が小さい値）
                height_diff = abs(hip['y'] - ankle['y'])
                normalized_height = height_diff / leg_length
                ankle_lifted = normalized_height > height_threshold

                # 両条件を満たす
                if knee_extended and ankle_lifted:
                    return True

        return False

    def _count_lunge_cycles(self, landmarks_data: List[Dict]) -> Dict[str, int]:
        """
        What: ランジサイクルカウント（中央→右→中央、中央→左→中央）
        Why: A3評価用
        Design Decision: 骨盤中心X座標を追跡

        Returns:
            {'right': int, 'left': int}

        CRITICAL: 主観性チェック ✅ 客観的（位置追跡カウント）
        """
        if not landmarks_data:
            return {'right': 0, 'left': 0}

        # 骨盤中心X座標を追跡
        pelvis_x_positions = []
        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_HIP, self.RIGHT_HIP):
                left_hip = landmarks[self.LEFT_HIP]
                right_hip = landmarks[self.RIGHT_HIP]
                pelvis_center_x = (left_hip['x'] + right_hip['x']) / 2
                pelvis_x_positions.append(pelvis_center_x)

        if not pelvis_x_positions:
            return {'right': 0, 'left': 0}

        # 中央値（ニュートラル位置）
        median_x = sorted(pelvis_x_positions)[len(pelvis_x_positions) // 2]

        # サイクルカウント
        cycles_right = 0
        cycles_left = 0
        state = 'center'  # center, right, left

        threshold = self.thresholds['execution']['completion']['neutral_threshold']

        for x in pelvis_x_positions:
            if state == 'center':
                if x > median_x + threshold:
                    state = 'right'
                elif x < median_x - threshold:
                    state = 'left'

            elif state == 'right':
                if abs(x - median_x) < threshold:
                    cycles_right += 1
                    state = 'center'

            elif state == 'left':
                if abs(x - median_x) < threshold:
                    cycles_left += 1
                    state = 'center'

        return {'right': cycles_right, 'left': cycles_left}

    def _calculate_pelvis_shift_rate(self, landmarks_data: List[Dict]) -> float:
        """
        What: 骨盤の側方シフト率計算
        Why: B1評価用（最重要指標）
        Design Decision: (骨盤移動距離 / 両足間距離) × 100

        Returns:
            float: シフト率（%）

        CRITICAL: 主観性チェック ✅ 客観的（距離比率計算）
        """
        if not landmarks_data:
            return 0.0

        # 開始時の足間距離（基準）
        start_frame = landmarks_data[0]['landmarks']
        if len(start_frame) <= max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
            return 0.0

        left_ankle_start = start_frame[self.LEFT_ANKLE]
        right_ankle_start = start_frame[self.RIGHT_ANKLE]

        feet_distance = abs(right_ankle_start['x'] - left_ankle_start['x'])

        if feet_distance == 0:
            return 0.0

        # 各フレームでの骨盤位置
        max_shift_rate = 0.0

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_HIP, self.RIGHT_HIP, self.RIGHT_ANKLE):
                left_hip = landmarks[self.LEFT_HIP]
                right_hip = landmarks[self.RIGHT_HIP]
                pelvis_center_x = (left_hip['x'] + right_hip['x']) / 2

                # 右足首への距離
                right_ankle = landmarks[self.RIGHT_ANKLE]
                shift_distance = abs(pelvis_center_x - right_ankle['x'])

                # シフト率
                shift_rate = (shift_distance / feet_distance) * 100
                max_shift_rate = max(max_shift_rate, shift_rate)

        return float(max_shift_rate)

    def _calculate_trendelenburg_skater(self, landmarks_data: List[Dict],
                                         base_width: float) -> float:
        """
        What: 荷重時の左右腰の高さ差（正規化）
        Why: B2評価用
        Design Decision: base_widthで正規化

        Returns:
            float: 正規化された高さ差

        CRITICAL: 主観性チェック ✅ 客観的（高さ差測定）
        """
        if base_width == 0:
            return 0.0

        max_drop = 0.0

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_HIP, self.RIGHT_HIP):
                left_hip = landmarks[self.LEFT_HIP]
                right_hip = landmarks[self.RIGHT_HIP]

                # 高さ差（Y座標差）
                height_diff = abs(left_hip['y'] - right_hip['y'])

                # 正規化
                normalized_drop = height_diff / base_width

                max_drop = max(max_drop, normalized_drop)

        return float(max_drop)

    def _calculate_lateral_stability_skater(self, landmarks_data: List[Dict],
                                             base_width: float) -> float:
        """
        What: 荷重フェーズでの骨盤横ブレ計算
        Why: B3評価用
        Design Decision: 荷重フェーズでの標準偏差

        Returns:
            float: 正規化された標準偏差

        CRITICAL: 主観性チェック ✅ 客観的（標準偏差測定）
        """
        if base_width == 0:
            return 0.0

        # 骨盤中心X座標を追跡
        pelvis_x = []
        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_HIP, self.RIGHT_HIP):
                left_hip = landmarks[self.LEFT_HIP]
                right_hip = landmarks[self.RIGHT_HIP]
                center_x = (left_hip['x'] + right_hip['x']) / 2
                pelvis_x.append(center_x)

        if not pelvis_x:
            return 0.0

        # 中央値
        median_x = sorted(pelvis_x)[len(pelvis_x) // 2]

        # 右荷重フェーズ（median_xより右側）
        right_phase_x = [x for x in pelvis_x if x > median_x + 0.05]

        # 左荷重フェーズ
        left_phase_x = [x for x in pelvis_x if x < median_x - 0.05]

        # 各フェーズでの標準偏差
        def calc_std(values):
            if len(values) < 2:
                return 0.0
            mean = sum(values) / len(values)
            variance = sum((x - mean)**2 for x in values) / len(values)
            return sqrt(variance)

        right_std = calc_std(right_phase_x)
        left_std = calc_std(left_phase_x)

        # 最大値を採用
        max_std = max(right_std, left_std)

        # 正規化
        normalized_std = max_std / base_width

        return float(normalized_std)

    def _calculate_knee_angle(self, hip: Dict, knee: Dict, ankle: Dict) -> Optional[float]:
        """
        What: 膝角度計算（hip-knee-ankle 3点から算出）
        Why: 離地判定用
        Design Decision: 3Dベクトル内積で角度計算

        Args:
            hip, knee, ankle: ランドマーク座標 {'x': float, 'y': float, 'z': float}

        Returns:
            float: 膝の角度（度）、計算できない場合はNone

        CRITICAL: NaN/ゼロ除算時はNoneを返す
        """
        try:
            # ベクトル1: 膝→股関節
            vec1_x = hip['x'] - knee['x']
            vec1_y = hip['y'] - knee['y']
            vec1_z = hip['z'] - knee['z']

            # ベクトル2: 膝→足首
            vec2_x = ankle['x'] - knee['x']
            vec2_y = ankle['y'] - knee['y']
            vec2_z = ankle['z'] - knee['z']

            # 内積
            dot_product = vec1_x * vec2_x + vec1_y * vec2_y + vec1_z * vec2_z

            # ベクトルの長さ
            mag1 = sqrt(vec1_x**2 + vec1_y**2 + vec1_z**2)
            mag2 = sqrt(vec2_x**2 + vec2_y**2 + vec2_z**2)

            # ゼロベクトルチェック
            if mag1 == 0 or mag2 == 0:
                return None

            # コサイン
            cos_angle = dot_product / (mag1 * mag2)
            cos_angle = max(-1.0, min(1.0, cos_angle))  # -1～1にクリップ

            # 角度（ラジアン→度）
            angle_rad = acos(cos_angle)
            angle_deg = degrees(angle_rad)

            return float(angle_deg)
        except (ValueError, ZeroDivisionError, KeyError):
            return None
