"""
Purpose: 上半身スイング評価ロジック
Responsibility: 腕振り振幅と左右対称性から上半身スイング動作を評価
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


class UpperBodySwingEvaluator:
    """
    What: 上半身スイング評価クラス
    Why: 腕振り振幅と左右バランスを定量評価
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

        # CRITICAL: upper_body_swing閾値取得（ADR-002参照）
        self.thresholds = self.config['thresholds']['upper_body_swing']
        self.normalizer = BodyNormalizer(config_path)

    def evaluate(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 上半身スイング総合評価
        Why: 腕振り振幅と左右対称性の両指標を評価
        Design Decision: 2指標評価（振幅、対称性）、min集計（ADR-002）

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
                'arm_amplitude': Dict,
                'symmetry': Dict,
                'details': str
            }

        CRITICAL: landmarks_data空の場合はスコア0を返す（例外投げない）
        """
        if not landmarks_data:
            return {
                'score': 0,
                'arm_amplitude': {'score': 0, 'ratio': None},
                'symmetry': {'score': 0, 'balance': None},
                'details': '姿勢が検出できませんでした'
            }

        # CRITICAL: 正規化処理（ADR-003）
        rep_values, _ = self.normalizer.normalize_landmarks_sequence(landmarks_data)

        # PHASE CORE LOGIC: 2指標評価
        # 1. 腕振り振幅評価
        amplitude_result = self._evaluate_arm_amplitude(landmarks_data, rep_values)

        # 2. 左右対称性評価
        symmetry_result = self._evaluate_symmetry(landmarks_data)

        # 3. 総合スコアの計算（両指標を満たす必要がある）
        total_score = min(amplitude_result['score'], symmetry_result['score'])

        return {
            'score': total_score,
            'arm_amplitude': amplitude_result,
            'symmetry': symmetry_result,
            'details': self._generate_details(total_score, amplitude_result, symmetry_result)
        }

    def _evaluate_arm_amplitude(self, landmarks_data: List[Dict], rep_values: Dict) -> Dict:
        """
        What: 腕振り振幅評価（肩幅比）
        Why: 十分な腕振り幅を確認
        Design Decision: shoulder_width正規化、config.json閾値参照（ADR-003）

        Args:
            landmarks_data: フレームごとのランドマークデータ
            rep_values: 正規化基準値

        Returns:
            Dict: {'score': int (0-3), 'ratio': float, 'max_amplitude': float}

        CRITICAL: shoulder_width=Noneの場合はスコア0を返す
        """
        shoulder_width = rep_values.get('shoulder_width')
        if shoulder_width is None or np.isnan(shoulder_width):
            return {'score': 0, 'ratio': None, 'max_amplitude': None}

        # PHASE CORE LOGIC: 腕振り振幅計算
        amplitudes = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_WRIST, self.RIGHT_WRIST):
                # 左右手首のY座標範囲を計算
                left_wrist_y = landmarks[self.LEFT_WRIST]['y']
                right_wrist_y = landmarks[self.RIGHT_WRIST]['y']

                # 肩の高さを基準に振り幅を計算
                left_shoulder_y = landmarks[self.LEFT_SHOULDER]['y']
                right_shoulder_y = landmarks[self.RIGHT_SHOULDER]['y']

                left_amplitude = abs(left_wrist_y - left_shoulder_y)
                right_amplitude = abs(right_wrist_y - right_shoulder_y)

                # 最大振幅を記録
                max_amp = max(left_amplitude, right_amplitude)
                amplitudes.append(max_amp)

        if not amplitudes:
            return {'score': 0, 'ratio': None, 'max_amplitude': None}

        max_amplitude = np.max(amplitudes)
        avg_amplitude = np.mean(amplitudes)

        # CRITICAL: 正規化（shoulder_width比、ADR-003）
        amplitude_ratio = normalize_value(avg_amplitude, shoulder_width)

        if amplitude_ratio is None:
            return {'score': 0, 'ratio': None, 'max_amplitude': float(max_amplitude)}

        # CRITICAL: config.json閾値参照（ADR-002）
        arm_amplitude_ratio_min = self.thresholds['arm_amplitude_ratio_min']

        # スコアリング
        if amplitude_ratio >= arm_amplitude_ratio_min:
            score = 3
        elif amplitude_ratio >= arm_amplitude_ratio_min * 0.75:
            score = 2
        elif amplitude_ratio >= arm_amplitude_ratio_min * 0.5:
            score = 1
        else:
            score = 0

        return {
            'score': score,
            'ratio': float(amplitude_ratio),
            'max_amplitude': float(max_amplitude),
            'avg_amplitude': float(avg_amplitude)
        }

    def _evaluate_symmetry(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 左右対称性評価
        Why: バランスの取れた腕振りを確認
        Design Decision: 左右振幅差で評価（ADR-002）

        Args:
            landmarks_data: フレームごとのランドマークデータ

        Returns:
            Dict: {'score': int (0-3), 'balance': float, 'avg_diff': float}

        CRITICAL: 左右差が小さいほど高スコア
        """
        # PHASE CORE LOGIC: 左右対称性計算
        symmetry_diffs = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > max(self.LEFT_WRIST, self.RIGHT_WRIST):
                # 左右手首の振り幅を計算
                left_wrist_y = landmarks[self.LEFT_WRIST]['y']
                right_wrist_y = landmarks[self.RIGHT_WRIST]['y']
                left_shoulder_y = landmarks[self.LEFT_SHOULDER]['y']
                right_shoulder_y = landmarks[self.RIGHT_SHOULDER]['y']

                left_amplitude = abs(left_wrist_y - left_shoulder_y)
                right_amplitude = abs(right_wrist_y - right_shoulder_y)

                # 左右差を計算
                diff = abs(left_amplitude - right_amplitude)
                symmetry_diffs.append(diff)

        if not symmetry_diffs:
            return {'score': 0, 'balance': None, 'avg_diff': None}

        avg_diff = np.mean(symmetry_diffs)
        max_diff = np.max(symmetry_diffs)

        # スコアリング（左右差が小さいほど高スコア）
        if avg_diff < 0.05:
            score = 3
            balance_level = "優秀"
        elif avg_diff < 0.10:
            score = 2
            balance_level = "良好"
        elif avg_diff < 0.15:
            score = 1
            balance_level = "改善の余地あり"
        else:
            score = 0
            balance_level = "要トレーニング"

        return {
            'score': score,
            'balance': balance_level,
            'avg_diff': float(avg_diff),
            'max_diff': float(max_diff)
        }

    def _generate_details(self,
                          total_score: int,
                          amplitude_result: Dict,
                          symmetry_result: Dict) -> str:
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

        # 腕振り振幅
        details += f"腕振り振幅スコア: {amplitude_result['score']}/3 "
        if amplitude_result['ratio'] is not None:
            details += f"(肩幅比: {amplitude_result['ratio']:.2f})\n"
        else:
            details += "(データなし)\n"

        # 左右対称性
        details += f"対称性スコア: {symmetry_result['score']}/3 "
        if symmetry_result['balance'] is not None:
            details += f"({symmetry_result['balance']})"
        else:
            details += "(データなし)"

        return details
