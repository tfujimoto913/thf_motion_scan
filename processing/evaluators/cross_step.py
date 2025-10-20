"""
Purpose: クロスステップ評価ロジック
Responsibility: ステップ幅、膝屈曲角度からクロスステップを評価
Dependencies: numpy, config.json, normalizer.py
Created: 2025-10-19 by Claude
Decision Log: ADR-002, ADR-003

CRITICAL: config.json閾値参照必須、正規化処理統合必須
"""
import numpy as np
import json
from pathlib import Path
from typing import List, Dict, Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))
from normalizer import BodyNormalizer, normalize_value


class CrossStepEvaluator:
    """
    What: クロスステップ評価クラス
    Why: ステップ幅と膝屈曲角度を定量評価
    Design Decision: config.json閾値参照、base_width正規化（ADR-002, ADR-003）

    CRITICAL: ハードコード閾値禁止、normalizer.py使用必須
    """

    # CRITICAL: MediaPipeランドマークインデックス定義（削除禁止）
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self, config_path: str = 'config.json'):
        """
        What: config.json読み込みと閾値初期化
        Why: 閾値外部化によるデータ整合性保証（ADR-002）
        Design Decision: デフォルトパスでルート直下config.json参照

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

        # CRITICAL: cross_step閾値取得（ADR-002参照）
        self.thresholds = self.config['thresholds']['cross_step']
        self.normalizer = BodyNormalizer(config_path)

    def evaluate(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: クロスステップ総合評価
        Why: ステップ幅と膝屈曲の2指標を評価
        Design Decision: 2指標評価、min集計（ADR-002）

        Args:
            landmarks_data: フレームごとのランドマークデータ

        Returns:
            Dict: {
                'score': int (0-3),
                'step_width': Dict,
                'knee_flexion': Dict,
                'details': str
            }

        CRITICAL: landmarks_data空の場合はスコア0を返す（例外投げない）
        """
        if not landmarks_data:
            return {
                'score': 0,
                'step_width': {'score': 0, 'ratio': None},
                'knee_flexion': {'score': 0, 'min_angle': None},
                'details': '姿勢が検出できませんでした'
            }

        # CRITICAL: 正規化処理（ADR-003）
        rep_values, _ = self.normalizer.normalize_landmarks_sequence(landmarks_data)

        # PHASE CORE LOGIC: 2指標評価
        # 1. ステップ幅評価
        step_result = self._evaluate_step_width(landmarks_data, rep_values)

        # 2. 膝屈曲角度評価
        knee_result = self._evaluate_knee_flexion(landmarks_data)

        # 3. 総合スコアの計算（2指標全て満たす必要がある）
        total_score = min(step_result['score'], knee_result['score'])

        return {
            'score': total_score,
            'step_width': step_result,
            'knee_flexion': knee_result,
            'details': self._generate_details(total_score, step_result, knee_result)
        }

    def _evaluate_step_width(self, landmarks_data: List[Dict], rep_values: Dict) -> Dict:
        """
        What: ステップ幅評価（base_width比）
        Why: 十分なクロスステップ幅を確認
        Design Decision: base_width正規化、config.json閾値参照（ADR-003）

        Returns:
            Dict: {'score': int (0-3), 'ratio': float, 'max_width': float}

        CRITICAL: base_width=Noneの場合はスコア0を返す
        """
        base_width = rep_values.get('base_width')
        if base_width is None or np.isnan(base_width):
            return {'score': 0, 'ratio': None, 'max_width': None}

        # PHASE CORE LOGIC: ステップ幅計算
        step_widths = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
                left_ankle = landmarks[self.LEFT_ANKLE]
                right_ankle = landmarks[self.RIGHT_ANKLE]

                # 左右足首間の水平距離
                step_width = abs(left_ankle['x'] - right_ankle['x'])
                step_widths.append(step_width)

        if not step_widths:
            return {'score': 0, 'ratio': None, 'max_width': None}

        max_width = np.max(step_widths)
        avg_width = np.mean(step_widths)

        # CRITICAL: 正規化（base_width比、ADR-003）
        step_width_ratio = normalize_value(max_width, base_width)

        if step_width_ratio is None:
            return {'score': 0, 'ratio': None, 'max_width': float(max_width)}

        # CRITICAL: config.json閾値参照（ADR-002）
        step_width_ratio_min = self.thresholds['step_width_ratio_min']

        # スコアリング
        if step_width_ratio >= step_width_ratio_min:
            score = 3
        elif step_width_ratio >= step_width_ratio_min * 0.8:
            score = 2
        elif step_width_ratio >= step_width_ratio_min * 0.6:
            score = 1
        else:
            score = 0

        return {
            'score': score,
            'ratio': float(step_width_ratio),
            'max_width': float(max_width),
            'avg_width': float(avg_width)
        }

    def _evaluate_knee_flexion(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 軸脚膝屈曲角度評価
        Why: 十分な膝屈曲深度（90°以上）を確認
        Design Decision: config.json閾値参照（ADR-002）

        Returns:
            Dict: {'score': int (0-3), 'min_angle': float, 'avg_angle': float}

        CRITICAL: 軸脚判定は左右膝角度の小さい方（より曲がっている方）
        """
        # PHASE CORE LOGIC: 軸脚膝角度計算
        knee_angles = []

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
                if left_angle is not None and right_angle is not None:
                    axis_leg_angle = min(left_angle, right_angle)
                    knee_angles.append(axis_leg_angle)

        if not knee_angles:
            return {'score': 0, 'min_angle': None, 'avg_angle': None}

        min_angle = np.min(knee_angles)
        avg_angle = np.mean(knee_angles)

        # CRITICAL: config.json閾値参照（ADR-002）
        knee_flexion_min = self.thresholds['knee_flexion_min']

        # スコアリング（膝角度が閾値以下＝十分屈曲している）
        if min_angle <= knee_flexion_min:
            score = 3
        elif min_angle <= knee_flexion_min + 10:
            score = 2
        elif min_angle <= knee_flexion_min + 20:
            score = 1
        else:
            score = 0

        return {
            'score': score,
            'min_angle': float(min_angle),
            'avg_angle': float(avg_angle)
        }

    def _calculate_knee_angle(self,
                              hip: Dict,
                              knee: Dict,
                              ankle: Dict) -> Optional[float]:
        """
        What: 膝角度計算（hip-knee-ankle 3点から算出）
        Why: 膝屈曲深度を定量評価
        Design Decision: 2Dベクトル内積で角度計算（ADR-003）

        Returns:
            float: 膝の角度（度）、計算できない場合はNone

        CRITICAL: NaN/ゼロ除算時はNoneを返す（例外投げない）
        """
        try:
            # ベクトルを作成
            v1 = np.array([hip['x'] - knee['x'], hip['y'] - knee['y']])
            v2 = np.array([ankle['x'] - knee['x'], ankle['y'] - knee['y']])

            # 内積とノルムから角度を計算
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 数値誤差対策
            angle = np.degrees(np.arccos(cos_angle))

            return float(angle)
        except (ValueError, ZeroDivisionError, KeyError):
            # CRITICAL: エラー時はNoneを返す（データ保持）
            return None

    def _generate_details(self,
                          total_score: int,
                          step_result: Dict,
                          knee_result: Dict) -> str:
        """
        What: 評価詳細メッセージ生成
        Why: 評価結果の可読性向上
        Design Decision: 2指標すべてを含めたサマリー（ADR-002）

        Returns:
            str: 詳細メッセージ

        CRITICAL: NaNの場合は"データなし"と表示
        """
        if total_score == 3:
            level = "優秀"
        elif total_score == 2:
            level = "良好"
        elif total_score == 1:
            level = "改善の余地あり"
        else:
            level = "要トレーニング"

        details = f"総合評価: {level}\n"

        # ステップ幅
        details += f"ステップ幅スコア: {step_result['score']}/3 "
        if step_result['ratio'] is not None:
            details += f"(基準幅比: {step_result['ratio']:.2f})\n"
        else:
            details += "(データなし)\n"

        # 膝屈曲角度
        details += f"膝屈曲スコア: {knee_result['score']}/3 "
        if knee_result['min_angle'] is not None:
            details += f"(最小角: {knee_result['min_angle']:.1f}度)"
        else:
            details += "(データなし)"

        return details
