"""
Purpose: プッシュプル評価ロジック
Responsibility: プル距離とプッシュ角度からプッシュプル動作を評価
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


class PushPullEvaluator:
    """
    What: プッシュプル評価クラス
    Why: プル距離とプッシュ角度を定量評価
    Design Decision: config.json閾値参照、shoulder_width正規化（ADR-002, ADR-003）

    CRITICAL: ハードコード閾値禁止、normalizer.py使用必須
    """

    # CRITICAL: MediaPipeランドマークインデックス定義（削除禁止）
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24

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

        # CRITICAL: push_pull閾値取得（ADR-002参照）
        self.thresholds = self.config['thresholds']['push_pull']
        self.normalizer = BodyNormalizer(config_path)

    def evaluate(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: プッシュプル総合評価
        Why: プル距離とプッシュ角度の2指標を評価
        Design Decision: 2指標評価、min集計（ADR-002）

        Args:
            landmarks_data: フレームごとのランドマークデータ

        Returns:
            Dict: {
                'score': int (0-3),
                'pull_distance': Dict,
                'push_angle': Dict,
                'details': str
            }

        CRITICAL: landmarks_data空の場合はスコア0を返す（例外投げない）
        """
        if not landmarks_data:
            return {
                'score': 0,
                'pull_distance': {'score': 0, 'ratio': None},
                'push_angle': {'score': 0, 'min_angle': None},
                'details': '姿勢が検出できませんでした'
            }

        # CRITICAL: 正規化処理（ADR-003）
        rep_values, _ = self.normalizer.normalize_landmarks_sequence(landmarks_data)

        # PHASE CORE LOGIC: 2指標評価
        # 1. プル距離評価
        pull_result = self._evaluate_pull_distance(landmarks_data, rep_values)

        # 2. プッシュ角度評価
        push_result = self._evaluate_push_angle(landmarks_data)

        # 3. 総合スコアの計算（2指標全て満たす必要がある）
        total_score = min(pull_result['score'], push_result['score'])

        return {
            'score': total_score,
            'pull_distance': pull_result,
            'push_angle': push_result,
            'details': self._generate_details(total_score, pull_result, push_result)
        }

    def _evaluate_pull_distance(self, landmarks_data: List[Dict], rep_values: Dict) -> Dict:
        """
        What: プル距離評価（shoulder_width比）
        Why: 十分な引き動作距離を確認
        Design Decision: shoulder_width正規化、config.json閾値参照（ADR-003）

        Returns:
            Dict: {'score': int (0-3), 'ratio': float, 'max_distance': float}

        CRITICAL: shoulder_width=Noneの場合はスコア0を返す
        """
        shoulder_width = rep_values.get('shoulder_width')
        if shoulder_width is None or np.isnan(shoulder_width):
            return {'score': 0, 'ratio': None, 'max_distance': None}

        # PHASE CORE LOGIC: プル距離計算
        pull_distances = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_WRIST, self.RIGHT_WRIST):
                # 左右手首の水平移動距離（肩からの距離）
                left_shoulder = landmarks[self.LEFT_SHOULDER]
                right_shoulder = landmarks[self.RIGHT_SHOULDER]
                left_wrist = landmarks[self.LEFT_WRIST]
                right_wrist = landmarks[self.RIGHT_WRIST]

                # 肩-手首間の水平距離（X軸方向）
                left_distance = abs(left_wrist['x'] - left_shoulder['x'])
                right_distance = abs(right_wrist['x'] - right_shoulder['x'])

                # 最大距離を記録
                max_distance = max(left_distance, right_distance)
                pull_distances.append(max_distance)

        if not pull_distances:
            return {'score': 0, 'ratio': None, 'max_distance': None}

        max_distance = np.max(pull_distances)
        avg_distance = np.mean(pull_distances)

        # CRITICAL: 正規化（shoulder_width比、ADR-003）
        pull_distance_ratio = normalize_value(max_distance, shoulder_width)

        if pull_distance_ratio is None:
            return {'score': 0, 'ratio': None, 'max_distance': float(max_distance)}

        # CRITICAL: config.json閾値参照（ADR-002）
        pull_distance_ratio_min = self.thresholds['pull_distance_ratio_min']

        # スコアリング
        if pull_distance_ratio >= pull_distance_ratio_min:
            score = 3
        elif pull_distance_ratio >= pull_distance_ratio_min * 0.8:
            score = 2
        elif pull_distance_ratio >= pull_distance_ratio_min * 0.6:
            score = 1
        else:
            score = 0

        return {
            'score': score,
            'ratio': float(pull_distance_ratio),
            'max_distance': float(max_distance),
            'avg_distance': float(avg_distance)
        }

    def _evaluate_push_angle(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: プッシュ角度評価（肘伸展角度）
        Why: 十分な押し動作（肘伸展）を確認
        Design Decision: config.json閾値参照（ADR-002）

        Returns:
            Dict: {'score': int (0-3), 'min_angle': float, 'avg_angle': float}

        CRITICAL: 肘角度が閾値以上＝十分伸展している
        """
        # PHASE CORE LOGIC: 肘角度計算
        elbow_angles = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_WRIST, self.RIGHT_WRIST):
                # 左右の肘角度を計算
                left_angle = self._calculate_elbow_angle(
                    landmarks[self.LEFT_SHOULDER],
                    landmarks[self.LEFT_ELBOW],
                    landmarks[self.LEFT_WRIST]
                )
                right_angle = self._calculate_elbow_angle(
                    landmarks[self.RIGHT_SHOULDER],
                    landmarks[self.RIGHT_ELBOW],
                    landmarks[self.RIGHT_WRIST]
                )

                # 両腕の角度を記録（プッシュ時は伸展している方）
                if left_angle is not None and right_angle is not None:
                    max_extension_angle = max(left_angle, right_angle)
                    elbow_angles.append(max_extension_angle)

        if not elbow_angles:
            return {'score': 0, 'min_angle': None, 'avg_angle': None}

        max_angle = np.max(elbow_angles)
        avg_angle = np.mean(elbow_angles)

        # CRITICAL: config.json閾値参照（ADR-002）
        push_angle_min = self.thresholds['push_angle_min']

        # スコアリング（肘角度が閾値以上＝十分伸展している）
        if max_angle >= push_angle_min:
            score = 3
        elif max_angle >= push_angle_min - 8:
            score = 2
        elif max_angle >= push_angle_min - 15:
            score = 1
        else:
            score = 0

        return {
            'score': score,
            'max_angle': float(max_angle),
            'avg_angle': float(avg_angle)
        }

    def _calculate_elbow_angle(self,
                               shoulder: Dict,
                               elbow: Dict,
                               wrist: Dict) -> Optional[float]:
        """
        What: 肘角度計算（shoulder-elbow-wrist 3点から算出）
        Why: 肘伸展度を定量評価
        Design Decision: 2Dベクトル内積で角度計算（ADR-003）

        Returns:
            float: 肘の角度（度）、計算できない場合はNone

        CRITICAL: NaN/ゼロ除算時はNoneを返す（例外投げない）
        """
        try:
            # ベクトルを作成
            v1 = np.array([shoulder['x'] - elbow['x'], shoulder['y'] - elbow['y']])
            v2 = np.array([wrist['x'] - elbow['x'], wrist['y'] - elbow['y']])

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
                          pull_result: Dict,
                          push_result: Dict) -> str:
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

        # プル距離
        details += f"プル距離スコア: {pull_result['score']}/3 "
        if pull_result['ratio'] is not None:
            details += f"(肩幅比: {pull_result['ratio']:.2f})\n"
        else:
            details += "(データなし)\n"

        # プッシュ角度
        details += f"プッシュ角度スコア: {push_result['score']}/3 "
        if push_result['max_angle'] is not None:
            details += f"(最大角: {push_result['max_angle']:.1f}度)"
        else:
            details += "(データなし)"

        return details
