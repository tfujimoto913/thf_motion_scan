"""
Purpose: 片脚スタンススクワット評価ロジック（2軸評価システム）
Responsibility: A.動作完全性(3点) + B.7原則達成度(9点) = 計12点満点
Dependencies: numpy, config.json, normalizer.py
Created: 2025-10-19 by Claude
Updated: 2025-10-26 - 2軸評価システム実装
Decision Log: ADR-002, ADR-003

CRITICAL: 全て客観的指標のみ使用（角度・距離・標準偏差）、主観的指標禁止
"""
import numpy as np
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from math import sqrt, acos, atan2, degrees


class SingleLegSquatEvaluator:
    """
    What: 片脚スタンススクワット評価クラス（2軸評価システム）
    Why: A.動作完全性(3点) + B.7原則達成度(9点) = 計12点満点
    Design Decision: config.json閾値参照、全て客観的指標のみ使用

    評価構造:
    - A. 動作完全性（3点）
      - A1. 膝屈曲角度（1.5点）
      - A2. 完遂回数（1.5点）
    - B. 7原則達成度（9点）
      - B1. 原則#1 代償動作の除去（3点）
      - B2. 原則#2 下半身安定性（3点）
      - B3. 原則#4 骨盤水平維持（3点）

    CRITICAL: 主観的指標禁止、全て角度・距離・標準偏差で評価
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

    def __init__(self, config_path: str = 'config.json'):
        """
        What: config.json読み込みと閾値初期化
        Why: 閾値外部化によるデータ整合性保証
        Design Decision: T01_single_leg_squat閾値使用

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

        # CRITICAL: T01_single_leg_squat閾値取得
        self.thresholds = self.config['thresholds']['T01_single_leg_squat']

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float, leg_length: float) -> Dict:
        """
        What: 片脚スタンススクワット総合評価（2軸システム）
        Why: A評価(3点) + B評価(9点) = 計12点満点
        Design Decision: 2軸評価システム

        Args:
            landmarks_data: フレームごとのランドマークデータ
            base_width: 正規化用基準幅（normalizer.pyから取得）
            shoulder_width: 正規化用肩幅（統一インターフェース、P1評価で使用）
            leg_length: 正規化用下肢長（統一インターフェース、将来の拡張用）

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
                'test_id': 'T01_single_leg_squat',
                'execution': {'total': 0.0},
                'principles': {'total': 0.0},
                'total': 0.0,
                'max_score': 12.0,
                'details': '姿勢が検出できませんでした'
            }

        # PHASE CORE LOGIC: A評価（動作完全性）
        execution = self.evaluate_execution(landmarks_data)

        # PHASE CORE LOGIC: B評価（7原則達成度）
        principles = self.evaluate_principles(landmarks_data, base_width)

        # 総合スコア
        total_score = execution['total'] + principles['total']

        return {
            'test_id': 'T01_single_leg_squat',
            'execution': execution,
            'principles': principles,
            'total': total_score,
            'max_score': 12.0
        }

    def evaluate_execution(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: A. 動作完全性評価（3点）
        Why: 膝屈曲角度(1.5点) + 完遂回数(1.5点)
        Design Decision: 客観的指標のみ（角度測定・回数カウント）

        Returns:
            Dict: {
                'knee_flexion': {'value': float, 'score': float, 'max': float},
                'completion': {'value': int, 'score': float, 'max': float},
                'total': float
            }

        CRITICAL: 主観性チェック済み - 全て客観的指標
        """
        # A1. 膝屈曲角度（1.5点）
        knee_flexion = self._score_knee_flexion(landmarks_data)

        # A2. 完遂回数（1.5点）
        completion = self._score_completion(landmarks_data)

        return {
            'knee_flexion': knee_flexion,
            'completion': completion,
            'total': knee_flexion['score'] + completion['score']
        }

    def evaluate_principles(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """
        What: B. 7原則達成度評価（9点）
        Why: P1(3点) + P2(3点) + P4(3点) = 9点
        Design Decision: 減点方式、客観的指標のみ

        Args:
            base_width: 正規化用基準幅

        Returns:
            Dict: {
                'P1_compensation': {'score': float, 'max': float, ...},
                'P2_stability': {'score': float, 'max': float, ...},
                'P4_pelvis_level': {'score': float, 'max': float, ...},
                'total': float
            }

        CRITICAL: 主観性チェック済み - 全て客観的指標
        """
        # B1. 原則#1: 代償動作の除去（3点）
        p1 = self._evaluate_principle_1(landmarks_data, base_width)

        # B2. 原則#2: 下半身安定性（3点）
        p2 = self._evaluate_principle_2(landmarks_data, base_width)

        # B3. 原則#4: 骨盤水平維持（3点）
        p4 = self._evaluate_principle_4(landmarks_data, base_width)

        return {
            'P1_compensation': p1,
            'P2_stability': p2,
            'P4_pelvis_level': p4,
            'total': p1['score'] + p2['score'] + p4['score']
        }

    # ==================== A評価: 動作完全性 ====================

    def _score_knee_flexion(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: A1. 膝屈曲角度評価（1.5点）
        Why: 支持脚の膝が最も曲がった時点（ピーク）の角度を評価
        Design Decision: config.json閾値使用（excellent: 87, good: 67, fair: 42）

        Returns:
            {'value': float (degree), 'score': float, 'max': 1.5}

        CRITICAL: 主観性チェック ✅ 客観的（角度測定のみ）
        """
        min_angle = 180.0  # 初期値

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
                # 左右の膝角度を計算
                left_angle = self._calculate_knee_angle(
                    landmarks[self.LEFT_HIP],
                    landmarks[self.LEFT_KNEE],
                    landmarks[self.LEFT_ANKLE]
                )
                right_angle = self._calculate_knee_angle(
                    landmarks[self.RIGHT_HIP],
                    landmarks[self.RIGHT_KNEE],
                    landmarks[self.RIGHT_ANKLE]
                )

                # 軸脚は膝がより曲がっている方（角度が小さい方）
                if left_angle is not None:
                    min_angle = min(min_angle, left_angle)
                if right_angle is not None:
                    min_angle = min(min_angle, right_angle)

        # スコアリング
        thresholds = self.thresholds['execution']['knee_flexion']
        if min_angle <= thresholds['excellent']:
            score = 1.5
        elif min_angle <= thresholds['good']:
            score = 1.0
        elif min_angle <= thresholds['fair']:
            score = 0.5
        else:
            score = 0.0

        return {'value': min_angle, 'score': score, 'max': 1.5}

    def _score_completion(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: A2. 完遂回数評価（1.5点）
        Why: スクワット動作を何回完遂したかをカウント
        Design Decision: ヒステリシス使用（誤検出防止）

        Returns:
            {'value': int (count), 'score': float, 'max': 1.5}

        CRITICAL: 主観性チェック ✅ 客観的（回数カウントのみ）
        """
        cycles = self._count_squat_cycles(landmarks_data)

        # スコアリング
        if cycles >= 3:
            score = 1.5
        elif cycles == 2:
            score = 1.0
        elif cycles == 1:
            score = 0.5
        else:
            score = 0.0

        return {'value': cycles, 'score': score, 'max': 1.5}

    def _count_squat_cycles(self, landmarks_data: List[Dict]) -> int:
        """
        What: スクワットサイクルカウント（立位→しゃがむ→立位）
        Why: 完遂回数評価
        Design Decision: ヒステリシスで誤検出防止

        ヒステリシス:
        - 開始角度: 160°以上（ほぼ直立）
        - 屈曲閾値: 90°以下
        - 終了閾値: 開始角度±2°以内に戻る

        CRITICAL: 誤検出防止のためヒステリシス必須
        """
        cycles = 0
        in_squat = False
        start_angle = None
        has_flexed = False

        hysteresis = self.thresholds['execution']['completion']['hysteresis']
        start_threshold = hysteresis['start_angle']
        end_threshold = hysteresis['end_threshold']
        squat_threshold = hysteresis['squat_threshold']

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
                # 軸脚の膝角度を取得
                left_angle = self._calculate_knee_angle(
                    landmarks[self.LEFT_HIP],
                    landmarks[self.LEFT_KNEE],
                    landmarks[self.LEFT_ANKLE]
                )
                right_angle = self._calculate_knee_angle(
                    landmarks[self.RIGHT_HIP],
                    landmarks[self.RIGHT_KNEE],
                    landmarks[self.RIGHT_ANKLE]
                )

                if left_angle is None and right_angle is None:
                    continue

                # 軸脚判定（角度が小さい方）
                angle = min(
                    left_angle if left_angle is not None else 180,
                    right_angle if right_angle is not None else 180
                )

                # サイクル開始検出
                if not in_squat and angle >= start_threshold:
                    start_angle = angle
                    in_squat = True
                    has_flexed = False

                # 屈曲検出
                if in_squat and angle <= squat_threshold:
                    has_flexed = True

                # サイクル完了検出
                if in_squat and has_flexed and start_angle is not None:
                    if abs(angle - start_angle) <= end_threshold:
                        cycles += 1
                        in_squat = False
                        has_flexed = False

        return cycles

    # ==================== B評価: 7原則達成度 ====================

    def _evaluate_principle_1(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """
        What: B1. 原則#1 代償動作の除去（3点）
        Why: 4つの代償パターンを検出し減点方式
        Design Decision: 減点方式、骨盤傾きが最重要

        減点項目:
        1. 骨盤の傾き（最重要）
        2. 膝の内外逸脱
        3. 上半身の側屈
        4. 反対側肩の沈み込み

        Returns:
            {
                'pelvis_tilt': {'value': float, 'deduction': float},
                'knee_deviation': {'value': float, 'deduction': float},
                'torso_lean': {'value': float, 'deduction': float},
                'shoulder_drop': {'value': float, 'deduction': float},
                'score': float,
                'max': 3.0
            }

        CRITICAL: 主観性チェック ✅ 客観的（全て角度・距離測定）
        """
        # 1. 骨盤の傾き
        pelvis = self._score_pelvis_tilt(landmarks_data)

        # 2. 膝の内外逸脱
        knee = self._score_knee_deviation(landmarks_data, base_width)

        # 3. 上半身の側屈
        torso = self._score_torso_lean(landmarks_data)

        # 4. 反対側肩の沈み込み
        shoulder = self._score_shoulder_drop(landmarks_data, base_width)

        # 総減点
        total_deduction = (
            pelvis['deduction'] +
            knee['deduction'] +
            torso['deduction'] +
            shoulder['deduction']
        )

        score = max(0.0, 3.0 - total_deduction)

        return {
            'pelvis_tilt': pelvis,
            'knee_deviation': knee,
            'torso_lean': torso,
            'shoulder_drop': shoulder,
            'score': score,
            'max': 3.0
        }

    def _score_pelvis_tilt(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 骨盤の傾き評価（減点方式）
        Why: 代償動作の最重要指標
        Design Decision: config.json閾値使用（severe: 15, moderate: 10, mild: 5）

        Returns:
            {'value': float (degree), 'deduction': float}

        CRITICAL: 主観性チェック ✅ 客観的（角度測定）
        """
        max_tilt = 0.0

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_HIP, self.RIGHT_HIP):
                tilt = self._calculate_pelvis_tilt(
                    landmarks[self.LEFT_HIP],
                    landmarks[self.RIGHT_HIP]
                )
                if tilt is not None:
                    max_tilt = max(max_tilt, tilt)

        # 減点計算
        thresholds = self.thresholds['principles']['P1_compensation']['pelvis_tilt']
        if max_tilt > thresholds['severe']:
            deduction = 2.0
        elif max_tilt > thresholds['moderate']:
            deduction = 1.0
        elif max_tilt > thresholds['mild']:
            deduction = 0.5
        else:
            deduction = 0.0

        return {'value': max_tilt, 'deduction': deduction}

    def _score_knee_deviation(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """
        What: 膝の内外逸脱評価（減点方式）
        Why: 膝が股関節-足首ラインから逸脱していないか
        Design Decision: base_widthで正規化

        Returns:
            {'value': float (ratio), 'deduction': float}

        CRITICAL: 主観性チェック ✅ 客観的（距離測定）
        """
        max_deviation = 0.0

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
                # 左右の膝逸脱を計算
                left_dev = self._calculate_knee_deviation(
                    landmarks[self.LEFT_HIP],
                    landmarks[self.LEFT_KNEE],
                    landmarks[self.LEFT_ANKLE]
                )
                right_dev = self._calculate_knee_deviation(
                    landmarks[self.RIGHT_HIP],
                    landmarks[self.RIGHT_KNEE],
                    landmarks[self.RIGHT_ANKLE]
                )

                # 正規化（base_widthに対する比率）
                if left_dev is not None and base_width > 0:
                    normalized_left = left_dev / base_width
                    max_deviation = max(max_deviation, normalized_left)
                if right_dev is not None and base_width > 0:
                    normalized_right = right_dev / base_width
                    max_deviation = max(max_deviation, normalized_right)

        # 減点計算
        thresholds = self.thresholds['principles']['P1_compensation']['knee_deviation']
        if max_deviation > thresholds['severe']:
            deduction = 1.0
        elif max_deviation > thresholds['moderate']:
            deduction = 0.5
        else:
            deduction = 0.0

        return {'value': max_deviation, 'deduction': deduction}

    def _score_torso_lean(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 上半身の側屈評価（減点方式）
        Why: 体幹の安定性評価
        Design Decision: config.json閾値使用（threshold: 15）

        Returns:
            {'value': float (degree), 'deduction': float}

        CRITICAL: 主観性チェック ✅ 客観的（角度測定）
        """
        max_lean = 0.0

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_HIP, self.RIGHT_HIP):
                lean = self._calculate_torso_lean(
                    landmarks[self.LEFT_SHOULDER],
                    landmarks[self.RIGHT_SHOULDER],
                    landmarks[self.LEFT_HIP],
                    landmarks[self.RIGHT_HIP]
                )
                if lean is not None:
                    max_lean = max(max_lean, lean)

        # 減点計算
        threshold = self.thresholds['principles']['P1_compensation']['torso_lean']['threshold']
        if max_lean > threshold:
            deduction = 0.5
        else:
            deduction = 0.0

        return {'value': max_lean, 'deduction': deduction}

    def _score_shoulder_drop(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """
        What: 反対側肩の沈み込み評価（減点方式）
        Why: 体幹の左右バランス評価
        Design Decision: base_widthで正規化

        Returns:
            {'value': float (ratio), 'deduction': float}

        CRITICAL: 主観性チェック ✅ 客観的（高さ差測定）
        """
        max_drop = 0.0

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_SHOULDER, self.RIGHT_SHOULDER):
                drop = self._calculate_shoulder_drop(
                    landmarks[self.LEFT_SHOULDER],
                    landmarks[self.RIGHT_SHOULDER],
                    base_width
                )
                if drop is not None:
                    max_drop = max(max_drop, drop)

        # 減点計算
        threshold = self.thresholds['principles']['P1_compensation']['shoulder_drop']['threshold']
        if max_drop > threshold:
            deduction = 0.5
        else:
            deduction = 0.0

        return {'value': max_drop, 'deduction': deduction}

    def _evaluate_principle_2(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """
        What: B2. 原則#2 下半身安定性（3点）
        Why: 骨盤・膝の横方向ブレを評価
        Design Decision: 標準偏差で安定性評価

        Returns:
            {
                'pelvis_stability': {'value': float, 'unit': 'ratio'},
                'knee_stability': {'value': float, 'unit': 'ratio'},
                'score': float,
                'max': 3.0
            }

        CRITICAL: 主観性チェック ✅ 客観的（標準偏差測定）
        """
        # 骨盤の横方向安定性
        pelvis_stability = self._calculate_pelvis_lateral_stability(landmarks_data)

        # 膝の横方向安定性
        knee_stability = self._calculate_knee_lateral_stability(landmarks_data)

        # 正規化（base_widthに対する比率）
        pelvis_ratio = pelvis_stability / base_width if base_width > 0 else 0.0
        knee_ratio = knee_stability / base_width if base_width > 0 else 0.0

        score = 3.0

        # 骨盤ブレで減点
        thresholds = self.thresholds['principles']['P2_stability']['pelvis_ratio']
        if pelvis_ratio > thresholds['high']:
            score -= 1.5
        elif pelvis_ratio > thresholds['moderate']:
            score -= 1.0

        # 膝ブレで減点
        thresholds = self.thresholds['principles']['P2_stability']['knee_ratio']
        if knee_ratio > thresholds['high']:
            score -= 1.5
        elif knee_ratio > thresholds['moderate']:
            score -= 1.0

        score = max(0.0, score)

        return {
            'pelvis_stability': {'value': pelvis_ratio, 'unit': 'ratio'},
            'knee_stability': {'value': knee_ratio, 'unit': 'ratio'},
            'score': score,
            'max': 3.0
        }

    def _evaluate_principle_4(self, landmarks_data: List[Dict], base_width: float) -> Dict:
        """
        What: B3. 原則#4 骨盤水平維持（3点）
        Why: Trendelenburg徴候（非支持側骨盤の沈下）を評価
        Design Decision: base_widthで正規化

        Returns:
            {
                'trendelenburg': {'value': float, 'unit': 'ratio'},
                'score': float,
                'max': 3.0
            }

        CRITICAL: 主観性チェック ✅ 客観的（高さ差測定）
        """
        max_tilt = 0.0

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_HIP, self.RIGHT_HIP):
                tilt = self._calculate_trendelenburg(
                    landmarks[self.LEFT_HIP],
                    landmarks[self.RIGHT_HIP],
                    base_width
                )
                if tilt is not None:
                    max_tilt = max(max_tilt, tilt)

        score = 3.0

        # 減点計算
        thresholds = self.thresholds['principles']['P4_pelvis_level']['trendelenburg']
        if max_tilt > thresholds['severe']:
            score -= 1.5
        elif max_tilt > thresholds['moderate']:
            score -= 1.0
        elif max_tilt > thresholds['mild']:
            score -= 0.5

        score = max(0.0, score)

        return {
            'trendelenburg': {'value': max_tilt, 'unit': 'ratio'},
            'score': score,
            'max': 3.0
        }

    # ==================== ヘルパー関数 ====================

    def _calculate_knee_angle(self, hip: Dict, knee: Dict, ankle: Dict) -> Optional[float]:
        """
        What: 膝角度計算（hip-knee-ankle 3点から算出）
        Why: 膝屈曲深度を定量評価
        Design Decision: 3Dベクトル内積で角度計算

        Args:
            hip, knee, ankle: ランドマーク座標 {'x': float, 'y': float, 'z': float}

        Returns:
            float: 膝の角度（度）、計算できない場合はNone

        CRITICAL: NaN/ゼロ除算時はNoneを返す（例外投げない）
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

    def _calculate_pelvis_tilt(self, left_hip: Dict, right_hip: Dict) -> Optional[float]:
        """
        What: 骨盤の左右傾斜角度計算
        Why: 代償動作検出
        Design Decision: Y座標差とX座標差から角度計算

        Args:
            left_hip: ランドマーク23
            right_hip: ランドマーク24

        Returns:
            float: 骨盤傾斜角度（度）

        CRITICAL: 主観性チェック ✅ 客観的（角度測定）
        """
        try:
            # Y座標差とX座標差から角度を計算
            dy = right_hip['y'] - left_hip['y']
            dx = right_hip['x'] - left_hip['x']

            tilt_rad = atan2(abs(dy), abs(dx))
            tilt_deg = degrees(tilt_rad)

            return float(tilt_deg)
        except (ValueError, KeyError):
            return None

    def _calculate_knee_deviation(self, hip: Dict, knee: Dict, ankle: Dict) -> Optional[float]:
        """
        What: 膝が股関節-足首ラインからどれだけ逸脱しているか
        Why: 代償動作検出
        Design Decision: 外積で垂直距離を計算

        Args:
            hip, knee, ankle: ランドマーク座標

        Returns:
            float: 正規化前の逸脱距離

        CRITICAL: 主観性チェック ✅ 客観的（距離測定）
        """
        try:
            # 股関節→足首のライン
            line_vec_x = ankle['x'] - hip['x']
            line_vec_y = ankle['y'] - hip['y']

            # 股関節→膝のベクトル
            knee_vec_x = knee['x'] - hip['x']
            knee_vec_y = knee['y'] - hip['y']

            # ラインの長さ
            line_length = sqrt(line_vec_x**2 + line_vec_y**2)

            if line_length == 0:
                return None

            # 外積で垂直距離を計算
            cross = abs(line_vec_x * knee_vec_y - line_vec_y * knee_vec_x)
            deviation = cross / line_length

            return float(deviation)
        except (ValueError, ZeroDivisionError, KeyError):
            return None

    def _calculate_torso_lean(self, left_shoulder: Dict, right_shoulder: Dict,
                              left_hip: Dict, right_hip: Dict) -> Optional[float]:
        """
        What: 肩-腰ラインの垂直からの角度計算
        Why: 上半身側屈検出
        Design Decision: 肩・腰の中点を使用

        Returns:
            float: 垂直からの角度（度）

        CRITICAL: 主観性チェック ✅ 客観的（角度測定）
        """
        try:
            # 肩の中点
            shoulder_mid_x = (left_shoulder['x'] + right_shoulder['x']) / 2
            shoulder_mid_y = (left_shoulder['y'] + right_shoulder['y']) / 2

            # 腰の中点
            hip_mid_x = (left_hip['x'] + right_hip['x']) / 2
            hip_mid_y = (left_hip['y'] + right_hip['y']) / 2

            # 垂直からの角度
            dx = abs(shoulder_mid_x - hip_mid_x)
            dy = abs(shoulder_mid_y - hip_mid_y)

            if dy == 0:
                return None

            lean_rad = atan2(dx, dy)
            lean_deg = degrees(lean_rad)

            return float(lean_deg)
        except (ValueError, KeyError):
            return None

    def _calculate_shoulder_drop(self, left_shoulder: Dict, right_shoulder: Dict,
                                  base_width: float) -> Optional[float]:
        """
        What: 左右肩の高さ差（正規化）
        Why: 体幹バランス評価
        Design Decision: base_widthで正規化

        Returns:
            float: 正規化された高さ差（ratio）

        CRITICAL: 主観性チェック ✅ 客観的（高さ差測定）
        """
        try:
            height_diff = abs(left_shoulder['y'] - right_shoulder['y'])

            if base_width == 0:
                return None

            normalized_diff = height_diff / base_width

            return float(normalized_diff)
        except (ValueError, KeyError):
            return None

    def _calculate_pelvis_lateral_stability(self, landmarks_data: List[Dict]) -> float:
        """
        What: 骨盤中心のX座標の標準偏差計算
        Why: 横方向ブレ評価
        Design Decision: numpy標準偏差使用

        Returns:
            float: 標準偏差

        CRITICAL: 主観性チェック ✅ 客観的（標準偏差測定）
        """
        pelvis_x_positions = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_HIP, self.RIGHT_HIP):
                left_hip = landmarks[self.LEFT_HIP]
                right_hip = landmarks[self.RIGHT_HIP]
                pelvis_center_x = (left_hip['x'] + right_hip['x']) / 2
                pelvis_x_positions.append(pelvis_center_x)

        if not pelvis_x_positions:
            return 0.0

        return float(np.std(pelvis_x_positions))

    def _calculate_knee_lateral_stability(self, landmarks_data: List[Dict]) -> float:
        """
        What: 膝のX座標の標準偏差計算
        Why: 横方向ブレ評価
        Design Decision: 軸脚（角度が小さい方）の膝を使用

        Returns:
            float: 標準偏差

        CRITICAL: 主観性チェック ✅ 客観的（標準偏差測定）
        """
        knee_x_positions = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
                # 軸脚判定（角度が小さい方）
                left_angle = self._calculate_knee_angle(
                    landmarks[self.LEFT_HIP],
                    landmarks[self.LEFT_KNEE],
                    landmarks[self.LEFT_ANKLE]
                )
                right_angle = self._calculate_knee_angle(
                    landmarks[self.RIGHT_HIP],
                    landmarks[self.RIGHT_KNEE],
                    landmarks[self.RIGHT_ANKLE]
                )

                if left_angle is not None and right_angle is not None:
                    # 軸脚の膝X座標を記録
                    if left_angle < right_angle:
                        knee_x_positions.append(landmarks[self.LEFT_KNEE]['x'])
                    else:
                        knee_x_positions.append(landmarks[self.RIGHT_KNEE]['x'])

        if not knee_x_positions:
            return 0.0

        return float(np.std(knee_x_positions))

    def _calculate_trendelenburg(self, left_hip: Dict, right_hip: Dict,
                                  base_width: float) -> Optional[float]:
        """
        What: 左右腰の高さ差（正規化）
        Why: Trendelenburg徴候検出
        Design Decision: base_widthで正規化

        Returns:
            float: 正規化された高さ差（ratio）

        CRITICAL: 主観性チェック ✅ 客観的（高さ差測定）
        """
        try:
            height_diff = abs(right_hip['y'] - left_hip['y'])

            if base_width == 0:
                return None

            normalized_diff = height_diff / base_width

            return float(normalized_diff)
        except (ValueError, KeyError):
            return None
