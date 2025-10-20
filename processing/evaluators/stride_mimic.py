"""
Purpose: ストライドミミック評価ロジック
Responsibility: 股関節伸展角度と足持ち上げ高さからストライドミミックを評価
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


class StrideMimicEvaluator:
    """
    What: ストライドミミック評価クラス
    Why: 股関節伸展角度と足のクリアランス高さを定量評価
    Design Decision: config.json閾値参照、leg_length正規化（ADR-002, ADR-003）

    CRITICAL: ハードコード閾値禁止、normalizer.py使用必須
    """

    # CRITICAL: MediaPipeランドマークインデックス定義（削除禁止）
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12

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

        # CRITICAL: stride_mimic閾値取得（ADR-002参照）
        self.thresholds = self.config['thresholds']['stride_mimic']
        self.normalizer = BodyNormalizer(config_path)

    def evaluate(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: ストライドミミック総合評価
        Why: 股関節伸展と足クリアランスの2指標を評価
        Design Decision: 2指標評価、min集計（ADR-002）

        Args:
            landmarks_data: フレームごとのランドマークデータ

        Returns:
            Dict: {
                'score': int (0-3),
                'hip_extension': Dict,
                'foot_clearance': Dict,
                'details': str
            }

        CRITICAL: landmarks_data空の場合はスコア0を返す（例外投げない）
        """
        if not landmarks_data:
            return {
                'score': 0,
                'hip_extension': {'score': 0, 'max_angle': None},
                'foot_clearance': {'score': 0, 'ratio': None},
                'details': '姿勢が検出できませんでした'
            }

        # CRITICAL: 正規化処理（ADR-003）
        rep_values, _ = self.normalizer.normalize_landmarks_sequence(landmarks_data)

        # PHASE CORE LOGIC: 2指標評価
        # 1. 股関節伸展角度評価
        hip_result = self._evaluate_hip_extension(landmarks_data)

        # 2. 足クリアランス評価
        clearance_result = self._evaluate_foot_clearance(landmarks_data, rep_values)

        # 3. 総合スコアの計算（2指標全て満たす必要がある）
        total_score = min(hip_result['score'], clearance_result['score'])

        return {
            'score': total_score,
            'hip_extension': hip_result,
            'foot_clearance': clearance_result,
            'details': self._generate_details(total_score, hip_result, clearance_result)
        }

    def _evaluate_hip_extension(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 股関節伸展角度評価
        Why: 十分な股関節伸展（ほぼ直線）を確認
        Design Decision: config.json閾値参照（ADR-002）

        Returns:
            Dict: {'score': int (0-3), 'max_angle': float, 'avg_angle': float}

        CRITICAL: 股関節角度が閾値以上＝十分伸展している
        """
        # PHASE CORE LOGIC: 股関節角度計算
        hip_angles = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
                # 左右の股関節角度を計算
                left_angle = self._calculate_hip_angle(
                    landmarks[self.LEFT_SHOULDER],
                    landmarks[self.LEFT_HIP],
                    landmarks[self.LEFT_KNEE]
                )
                right_angle = self._calculate_hip_angle(
                    landmarks[self.RIGHT_SHOULDER],
                    landmarks[self.RIGHT_HIP],
                    landmarks[self.RIGHT_KNEE]
                )

                # 両脚の角度を記録（後脚は伸展している方）
                if left_angle is not None and right_angle is not None:
                    max_extension_angle = max(left_angle, right_angle)
                    hip_angles.append(max_extension_angle)

        if not hip_angles:
            return {'score': 0, 'max_angle': None, 'avg_angle': None}

        max_angle = np.max(hip_angles)
        avg_angle = np.mean(hip_angles)

        # CRITICAL: config.json閾値参照（ADR-002）
        hip_extension_min = self.thresholds['hip_extension_min']

        # スコアリング（股関節角度が閾値以上＝十分伸展している）
        if max_angle >= hip_extension_min:
            score = 3
        elif max_angle >= hip_extension_min - 8:
            score = 2
        elif max_angle >= hip_extension_min - 15:
            score = 1
        else:
            score = 0

        return {
            'score': score,
            'max_angle': float(max_angle),
            'avg_angle': float(avg_angle)
        }

    def _evaluate_foot_clearance(self, landmarks_data: List[Dict], rep_values: Dict) -> Dict:
        """
        What: 足クリアランス高さ評価（leg_length比）
        Why: 十分な足の持ち上げを確認
        Design Decision: leg_length正規化、config.json閾値参照（ADR-003）

        Returns:
            Dict: {'score': int (0-3), 'ratio': float, 'max_clearance': float}

        CRITICAL: leg_length=Noneの場合はスコア0を返す
        """
        leg_length = rep_values.get('leg_length')
        if leg_length is None or np.isnan(leg_length):
            return {'score': 0, 'ratio': None, 'max_clearance': None}

        # PHASE CORE LOGIC: 足クリアランス計算
        clearances = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
                # 左右足首のY座標差（高い方が遊脚）
                left_ankle_y = landmarks[self.LEFT_ANKLE]['y']
                right_ankle_y = landmarks[self.RIGHT_ANKLE]['y']

                # クリアランス高さ（Y座標差の絶対値）
                clearance = abs(left_ankle_y - right_ankle_y)
                clearances.append(clearance)

        if not clearances:
            return {'score': 0, 'ratio': None, 'max_clearance': None}

        max_clearance = np.max(clearances)
        avg_clearance = np.mean(clearances)

        # CRITICAL: 正規化（leg_length比、ADR-003）
        clearance_ratio = normalize_value(max_clearance, leg_length)

        if clearance_ratio is None:
            return {'score': 0, 'ratio': None, 'max_clearance': float(max_clearance)}

        # CRITICAL: config.json閾値参照（ADR-002）
        foot_clearance_ratio_min = self.thresholds['foot_clearance_ratio_min']

        # スコアリング
        if clearance_ratio >= foot_clearance_ratio_min:
            score = 3
        elif clearance_ratio >= foot_clearance_ratio_min * 0.75:
            score = 2
        elif clearance_ratio >= foot_clearance_ratio_min * 0.5:
            score = 1
        else:
            score = 0

        return {
            'score': score,
            'ratio': float(clearance_ratio),
            'max_clearance': float(max_clearance),
            'avg_clearance': float(avg_clearance)
        }

    def _calculate_hip_angle(self,
                             shoulder: Dict,
                             hip: Dict,
                             knee: Dict) -> Optional[float]:
        """
        What: 股関節角度計算（shoulder-hip-knee 3点から算出）
        Why: 股関節伸展度を定量評価
        Design Decision: 2Dベクトル内積で角度計算（ADR-003）

        Returns:
            float: 股関節の角度（度）、計算できない場合はNone

        CRITICAL: NaN/ゼロ除算時はNoneを返す（例外投げない）
        """
        try:
            # ベクトルを作成
            v1 = np.array([shoulder['x'] - hip['x'], shoulder['y'] - hip['y']])
            v2 = np.array([knee['x'] - hip['x'], knee['y'] - hip['y']])

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
                          hip_result: Dict,
                          clearance_result: Dict) -> str:
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

        # 股関節伸展角度
        details += f"股関節伸展スコア: {hip_result['score']}/3 "
        if hip_result['max_angle'] is not None:
            details += f"(最大角: {hip_result['max_angle']:.1f}度)\n"
        else:
            details += "(データなし)\n"

        # 足クリアランス
        details += f"足クリアランススコア: {clearance_result['score']}/3 "
        if clearance_result['ratio'] is not None:
            details += f"(下肢長比: {clearance_result['ratio']:.2f})"
        else:
            details += "(データなし)"

        return details
