"""
Purpose: ジャンプランディング評価ロジック
Responsibility: ジャンプ高さと着地時膝屈曲角度からジャンプランディングを評価
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


class JumpLandingEvaluator:
    """
    What: ジャンプランディング評価クラス
    Why: ジャンプ高さと着地時の膝屈曲角度を定量評価
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

        # CRITICAL: jump_landing閾値取得（ADR-002参照）
        self.thresholds = self.config['thresholds']['jump_landing']
        self.normalizer = BodyNormalizer(config_path)

    def evaluate(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: ジャンプランディング総合評価
        Why: ジャンプ高さと着地時膝屈曲の2指標を評価
        Design Decision: 2指標評価、min集計（ADR-002）

        Args:
            landmarks_data: フレームごとのランドマークデータ

        Returns:
            Dict: {
                'score': int (0-3),
                'jump_height': Dict,
                'landing_knee_flexion': Dict,
                'details': str
            }

        CRITICAL: landmarks_data空の場合はスコア0を返す（例外投げない）
        """
        if not landmarks_data:
            return {
                'score': 0,
                'jump_height': {'score': 0, 'ratio': None},
                'landing_knee_flexion': {'score': 0, 'min_angle': None},
                'details': '姿勢が検出できませんでした'
            }

        # CRITICAL: 正規化処理（ADR-003）
        rep_values, _ = self.normalizer.normalize_landmarks_sequence(landmarks_data)

        # PHASE CORE LOGIC: 2指標評価
        # 1. ジャンプ高さ評価
        height_result = self._evaluate_jump_height(landmarks_data, rep_values)

        # 2. 着地時膝屈曲角度評価
        flexion_result = self._evaluate_landing_knee_flexion(landmarks_data)

        # 3. 総合スコアの計算（2指標全て満たす必要がある）
        total_score = min(height_result['score'], flexion_result['score'])

        return {
            'score': total_score,
            'jump_height': height_result,
            'landing_knee_flexion': flexion_result,
            'details': self._generate_details(total_score, height_result, flexion_result)
        }

    def _evaluate_jump_height(self, landmarks_data: List[Dict], rep_values: Dict) -> Dict:
        """
        What: ジャンプ高さ評価（leg_length比）
        Why: 十分なジャンプ高さを確認
        Design Decision: leg_length正規化、config.json閾値参照（ADR-003）

        Returns:
            Dict: {'score': int (0-3), 'ratio': float, 'max_height': float}

        CRITICAL: leg_length=Noneの場合はスコア0を返す
        """
        leg_length = rep_values.get('leg_length')
        if leg_length is None or np.isnan(leg_length):
            return {'score': 0, 'ratio': None, 'max_height': None}

        # PHASE CORE LOGIC: ジャンプ高さ計算
        # 腰の高さ（左右hipの中点Y座標）の変動を追跡
        hip_heights = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_HIP, self.RIGHT_HIP):
                # 左右腰の中点Y座標
                left_hip_y = landmarks[self.LEFT_HIP]['y']
                right_hip_y = landmarks[self.RIGHT_HIP]['y']
                hip_center_y = (left_hip_y + right_hip_y) / 2
                hip_heights.append(hip_center_y)

        if not hip_heights:
            return {'score': 0, 'ratio': None, 'max_height': None}

        # ジャンプ高さ = 最高点 - 最低点（Y座標は下向き正のため逆転）
        min_y = np.min(hip_heights)  # 最高点（Y座標が小さい）
        max_y = np.max(hip_heights)  # 最低点（Y座標が大きい）
        jump_height = max_y - min_y

        avg_height = np.mean(hip_heights)

        # CRITICAL: 正規化（leg_length比、ADR-003）
        jump_height_ratio = normalize_value(jump_height, leg_length)

        if jump_height_ratio is None:
            return {'score': 0, 'ratio': None, 'max_height': float(jump_height)}

        # CRITICAL: config.json閾値参照（ADR-002）
        jump_height_ratio_min = self.thresholds['jump_height_ratio_min']

        # スコアリング
        if jump_height_ratio >= jump_height_ratio_min:
            score = 3
        elif jump_height_ratio >= jump_height_ratio_min * 0.75:
            score = 2
        elif jump_height_ratio >= jump_height_ratio_min * 0.5:
            score = 1
        else:
            score = 0

        return {
            'score': score,
            'ratio': float(jump_height_ratio),
            'max_height': float(jump_height),
            'avg_height': float(avg_height)
        }

    def _evaluate_landing_knee_flexion(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 着地時膝屈曲角度評価
        Why: 十分な膝屈曲深度（90°以下）を確認
        Design Decision: config.json閾値参照（ADR-002）

        Returns:
            Dict: {'score': int (0-3), 'min_angle': float, 'avg_angle': float}

        CRITICAL: 膝角度が閾値以下＝十分屈曲している（着地衝撃吸収）
        """
        # PHASE CORE LOGIC: 膝角度計算
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

                # 両膝の平均角度（着地時は両脚で吸収）
                if left_angle is not None and right_angle is not None:
                    avg_knee_angle = (left_angle + right_angle) / 2
                    knee_angles.append(avg_knee_angle)

        if not knee_angles:
            return {'score': 0, 'min_angle': None, 'avg_angle': None}

        min_angle = np.min(knee_angles)
        avg_angle = np.mean(knee_angles)

        # CRITICAL: config.json閾値参照（ADR-002）
        knee_flexion_max = self.thresholds['knee_flexion_max']

        # スコアリング（膝角度が閾値以下＝十分屈曲している）
        if min_angle <= knee_flexion_max:
            score = 3
        elif min_angle <= knee_flexion_max + 10:
            score = 2
        elif min_angle <= knee_flexion_max + 20:
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
                          height_result: Dict,
                          flexion_result: Dict) -> str:
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

        # ジャンプ高さ
        details += f"ジャンプ高さスコア: {height_result['score']}/3 "
        if height_result['ratio'] is not None:
            details += f"(下肢長比: {height_result['ratio']:.2f})\n"
        else:
            details += "(データなし)\n"

        # 着地時膝屈曲
        details += f"着地膝屈曲スコア: {flexion_result['score']}/3 "
        if flexion_result['min_angle'] is not None:
            details += f"(最小角: {flexion_result['min_angle']:.1f}度)"
        else:
            details += "(データなし)"

        return details
