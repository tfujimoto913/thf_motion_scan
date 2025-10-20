"""
Purpose: 片脚スタンススクワット評価ロジック
Responsibility: 骨盤水平性と膝角度比から片脚立位スクワットを評価
Dependencies: numpy, config.json, normalizer.py
Created: 2025-10-19 by Claude
Decision Log: ADR-002, ADR-003

CRITICAL: config.json閾値参照必須、正規化処理統合必須
"""
import numpy as np
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional


class SingleLegSquatEvaluator:
    """
    What: 片脚スタンススクワット評価クラス
    Why: 骨盤安定性と軸脚・遊脚の膝角度差を定量評価
    Design Decision: config.json閾値参照、正規化処理統合（ADR-002, ADR-003）

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

        # CRITICAL: single_leg_squat閾値取得（ADR-002参照）
        self.thresholds = self.config['thresholds']['single_leg_squat']

    def evaluate(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 片脚スタンススクワット総合評価
        Why: 骨盤水平性と膝角度比の両指標を満たす必要がある
        Design Decision: min(骨盤スコア, 膝角度スコア)で総合評価（ADR-002）

        Args:
            landmarks_data: フレームごとのランドマークデータ
                [{
                    'frame': int,
                    'timestamp': float,
                    'landmarks': [{'x': float, 'y': float, 'z': float, 'visibility': float}, ...]
                }, ...]

        Returns:
            Dict: {
                'score': int (0-3),
                'pelvic_stability': Dict,
                'knee_angle_ratio': Dict,
                'knee_flexion': Dict,
                'details': str
            }

        CRITICAL: landmarks_data空の場合はスコア0を返す（例外投げない）
        """
        if not landmarks_data:
            return {
                'score': 0,
                'pelvic_stability': {'score': 0, 'avg_diff': None},
                'knee_angle_ratio': {'score': 0, 'avg_diff': None},
                'knee_flexion': {'score': 0, 'min_angle': None},
                'details': '姿勢が検出できませんでした'
            }

        # PHASE CORE LOGIC: 3指標評価
        # 1. 骨盤水平性の評価
        pelvic_result = self._evaluate_pelvic_stability(landmarks_data)

        # 2. 膝角度比の評価
        knee_result = self._evaluate_knee_angle_ratio(landmarks_data)

        # 3. 膝屈曲角度の評価（config.json: knee_flexion_min）
        flexion_result = self._evaluate_knee_flexion(landmarks_data)

        # 4. 総合スコアの計算（3指標全て満たす必要がある）
        total_score = min(pelvic_result['score'], knee_result['score'], flexion_result['score'])

        return {
            'score': total_score,
            'pelvic_stability': pelvic_result,
            'knee_angle_ratio': knee_result,
            'knee_flexion': flexion_result,
            'details': self._generate_details(total_score, pelvic_result, knee_result, flexion_result)
        }

    def _evaluate_pelvic_stability(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 骨盤水平性評価（左右hip Y座標差）
        Why: 片脚立位時の骨盤水平保持能力を評価
        Design Decision: pelvic_stability閾値はanalyzer.pyと共通（ADR-002）

        Returns:
            Dict: {'score': int (0-3), 'avg_diff': float, 'max_diff': float, 'frames_analyzed': int}

        CRITICAL: config.json pelvic_stability閾値参照（ハードコード禁止）
        """
        # PHASE CORE LOGIC: 骨盤傾き計算
        hip_diffs = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_HIP, self.RIGHT_HIP):
                left_hip = landmarks[self.LEFT_HIP]
                right_hip = landmarks[self.RIGHT_HIP]

                # 骨盤の傾き（Y座標の差）
                diff = abs(left_hip['y'] - right_hip['y'])
                hip_diffs.append(diff)

        if not hip_diffs:
            return {'score': 0, 'avg_diff': None, 'max_diff': None, 'frames_analyzed': 0}

        avg_diff = np.mean(hip_diffs)
        max_diff = np.max(hip_diffs)

        # CRITICAL: config.json閾値参照（ADR-002）
        pelvic_thresholds = self.config['thresholds']['pelvic_stability']
        tilt_excellent = pelvic_thresholds['tilt_excellent']
        tilt_good = pelvic_thresholds['tilt_good']
        tilt_improvement = pelvic_thresholds['tilt_improvement']

        # スコアリング（0-3点）
        if avg_diff < tilt_excellent:
            score = 3
        elif avg_diff < tilt_good:
            score = 2
        elif avg_diff < tilt_improvement:
            score = 1
        else:
            score = 0

        return {
            'score': score,
            'avg_diff': float(avg_diff),
            'max_diff': float(max_diff),
            'frames_analyzed': len(hip_diffs)
        }

    def _evaluate_knee_flexion(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 軸脚膝屈曲角度評価
        Why: 十分な膝屈曲深度（90°以上）を確認
        Design Decision: config.json knee_flexion_min閾値使用（ADR-002）

        Returns:
            Dict: {'score': int (0-3), 'min_angle': float, 'avg_angle': float, 'frames_analyzed': int}

        CRITICAL: 軸脚判定は左右膝角度の小さい方（より曲がっている方）
        """
        knee_angles = []

        # PHASE CORE LOGIC: 軸脚膝角度計算
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
            return {'score': 0, 'min_angle': None, 'avg_angle': None, 'frames_analyzed': 0}

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
            'avg_angle': float(avg_angle),
            'frames_analyzed': len(knee_angles)
        }

    def _evaluate_knee_angle_ratio(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 膝角度比評価（軸脚と遊脚の差）
        Why: 軸脚のみが屈曲し、遊脚は伸展している状態を確認
        Design Decision: 角度差20°以上で合格（現在はハードコード、将来config化）

        Returns:
            Dict: {'score': int (0-3), 'avg_diff': float, 'max_diff': float, 'frames_analyzed': int}

        CRITICAL: 将来的にconfig.json化予定
        """
        # PHASE CORE LOGIC: 左右膝角度差計算
        angle_diffs = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_ANKLE, self.RIGHT_ANKLE):
                # 左脚と右脚の膝角度を計算
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
                    # 角度の差（軸脚はより曲がる）
                    diff = abs(left_angle - right_angle)
                    angle_diffs.append(diff)

        if not angle_diffs:
            return {'score': 0, 'avg_diff': None, 'max_diff': None, 'frames_analyzed': 0}

        avg_diff = np.mean(angle_diffs)
        max_diff = np.max(angle_diffs)

        # CRITICAL: 暫定ハードコード（将来config.json化）
        knee_angle_diff_threshold = 20.0

        # スコアリング
        if avg_diff > knee_angle_diff_threshold:
            score = 3
        elif avg_diff > knee_angle_diff_threshold * 0.75:
            score = 2
        elif avg_diff > knee_angle_diff_threshold * 0.5:
            score = 1
        else:
            score = 0

        return {
            'score': score,
            'avg_diff': float(avg_diff),
            'max_diff': float(max_diff),
            'frames_analyzed': len(angle_diffs)
        }

    def _calculate_knee_angle(self,
                              hip: Dict,
                              knee: Dict,
                              ankle: Dict) -> Optional[float]:
        """
        What: 膝角度計算（hip-knee-ankle 3点から算出）
        Why: 膝屈曲深度を定量評価
        Design Decision: 2Dベクトル内積で角度計算（ADR-003）

        Args:
            hip, knee, ankle: ランドマーク座標 {'x': float, 'y': float, 'z': float}

        Returns:
            float: 膝の角度（度）、計算できない場合はNone

        CRITICAL: NaN/ゼロ除算時はNoneを返す（例外投げない）
        """
        try:
            # ベクトルを作成
            v1 = np.array([hip['x'] - knee['x'], hip['y'] - knee['y']])
            v2 = np.array([ankle['x'] - knee['x'], ankle['y'] - knee['y']])

            # ノルムチェック（ゼロベクトル対策）
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)

            # CRITICAL: ゼロベクトルの場合はNone返却
            if norm1 == 0 or norm2 == 0:
                return None

            # 内積とノルムから角度を計算
            cos_angle = np.dot(v1, v2) / (norm1 * norm2)
            cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 数値誤差対策
            angle = np.degrees(np.arccos(cos_angle))

            # CRITICAL: NaN判定
            if np.isnan(angle):
                return None

            return float(angle)
        except (ValueError, ZeroDivisionError, KeyError):
            # CRITICAL: エラー時はNoneを返す（データ保持）
            return None

    def _generate_details(self,
                          total_score: int,
                          pelvic_result: Dict,
                          knee_result: Dict,
                          flexion_result: Dict) -> str:
        """
        What: 評価詳細メッセージ生成
        Why: 評価結果の可読性向上
        Design Decision: 3指標すべてを含めたサマリー（ADR-002）

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

        # 骨盤安定性
        details += f"骨盤安定性スコア: {pelvic_result['score']}/3 "
        if pelvic_result['avg_diff'] is not None:
            details += f"(平均差: {pelvic_result['avg_diff']:.4f})\n"
        else:
            details += "(データなし)\n"

        # 膝屈曲角度
        details += f"膝屈曲スコア: {flexion_result['score']}/3 "
        if flexion_result['min_angle'] is not None:
            details += f"(最小角: {flexion_result['min_angle']:.1f}度)\n"
        else:
            details += "(データなし)\n"

        # 膝角度比
        details += f"膝角度比スコア: {knee_result['score']}/3 "
        if knee_result['avg_diff'] is not None:
            details += f"(平均差: {knee_result['avg_diff']:.1f}度)"
        else:
            details += "(データなし)"

        return details
