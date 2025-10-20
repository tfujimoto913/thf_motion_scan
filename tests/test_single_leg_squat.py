"""
Purpose: single_leg_squat.pyの単体テスト
Responsibility: 片脚スタンススクワット評価器の検証、評価器単体テストのテンプレート
Dependencies: pytest, single_leg_squat.py, sample_landmarks.json, config.json
Created: 2025-10-21 by Claude
Decision Log: ADR-002, ADR-003, ADR-005

CRITICAL: 3指標評価検証必須（骨盤水平性、膝角度比、膝屈曲角度）、スコアリング0-3点検証必須
"""
import pytest
import json
import numpy as np
from pathlib import Path
import sys

# CRITICAL: processing/モジュールをインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from processing.evaluators.single_leg_squat import SingleLegSquatEvaluator


class TestSingleLegSquatEvaluator:
    """
    What: SingleLegSquatEvaluatorクラスの単体テスト
    Why: 片脚スタンススクワット評価の正確性保証、評価器単体テストのテンプレート
    Design Decision: pytest標準準拠、sample_landmarks.json使用（ADR-005）

    CRITICAL: このテストは他の6評価器のテンプレートとなる
    """

    @pytest.fixture
    def evaluator(self):
        """
        What: SingleLegSquatEvaluatorインスタンス生成
        Why: 各テストで再利用
        Design Decision: config.json使用（ADR-002）
        """
        return SingleLegSquatEvaluator('config.json')

    @pytest.fixture
    def sample_landmarks(self):
        """
        What: sample_landmarks.json読み込み
        Why: 実データでテスト
        Design Decision: tests/fixtures/sample_landmarks.json使用（ADR-005）

        CRITICAL: ファイルが存在しない場合はテストスキップ
        """
        json_path = Path(__file__).parent / 'fixtures' / 'sample_landmarks.json'
        if not json_path.exists():
            pytest.skip(f"sample_landmarks.json not found: {json_path}")

        with open(json_path, 'r') as f:
            data = json.load(f)

        return data['landmarks']

    @pytest.fixture
    def config_values(self):
        """
        What: config.json閾値読み込み
        Why: テストで期待値として使用
        Design Decision: config.json一元管理（ADR-002）
        """
        config_path = Path(__file__).parent.parent / 'config.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config

    @pytest.fixture
    def synthetic_single_leg_data(self):
        """
        What: 片脚スクワットの合成データ生成
        Why: 特定パターンのテスト用
        Design Decision: 軸脚右、遊脚左でテスト（ADR-003）

        CRITICAL: 骨盤水平、膝角度差20°以上、膝屈曲90°以下を満たすデータ
        """
        # PHASE CORE LOGIC: 優秀な片脚スクワットデータ生成
        data = []
        for i in range(10):
            landmarks = [{'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 1.0} for _ in range(33)]

            # 骨盤水平（Y座標差 < 0.02）
            landmarks[23] = {'x': 0.4, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}  # LEFT_HIP
            landmarks[24] = {'x': 0.6, 'y': 0.501, 'z': 0.0, 'visibility': 1.0}  # RIGHT_HIP (diff=0.001)

            # 右脚軸脚（膝角度80°）、左脚遊脚（膝角度170°）
            # 右脚: hip-knee-ankle = 80°
            landmarks[23] = {'x': 0.6, 'y': 0.4, 'z': 0.0, 'visibility': 1.0}  # RIGHT_HIP
            landmarks[25] = {'x': 0.6, 'y': 0.6, 'z': 0.0, 'visibility': 1.0}  # RIGHT_KNEE
            landmarks[27] = {'x': 0.65, 'y': 0.8, 'z': 0.0, 'visibility': 1.0}  # RIGHT_ANKLE

            # 左脚: hip-knee-ankle = 170°（ほぼ伸展）
            landmarks[24] = {'x': 0.4, 'y': 0.401, 'z': 0.0, 'visibility': 1.0}  # LEFT_HIP
            landmarks[26] = {'x': 0.4, 'y': 0.6, 'z': 0.0, 'visibility': 1.0}  # LEFT_KNEE
            landmarks[28] = {'x': 0.39, 'y': 0.8, 'z': 0.0, 'visibility': 1.0}  # LEFT_ANKLE

            data.append({
                'frame': i,
                'timestamp': i * 0.033,
                'landmarks': landmarks
            })

        return data

    def test_evaluator_initialization(self, evaluator, config_values):
        """
        What: 初期化テスト
        Why: config.json読み込みと閾値設定確認
        Design Decision: config.json一元管理（ADR-002）

        CRITICAL: single_leg_squat閾値が正しく読み込まれること
        """
        # 検証: config読み込み成功
        assert evaluator.config is not None, "configが読み込まれていません"
        assert 'thresholds' in evaluator.config, "thresholdsが存在しません"

        # 検証: single_leg_squat閾値
        assert 'single_leg_squat' in evaluator.config['thresholds'], \
            "single_leg_squat閾値が存在しません"

        assert evaluator.thresholds == config_values['thresholds']['single_leg_squat'], \
            "閾値が一致しません"

        # 検証: knee_flexion_min閾値
        assert 'knee_flexion_min' in evaluator.thresholds, \
            "knee_flexion_minが存在しません"
        assert evaluator.thresholds['knee_flexion_min'] == 87, \
            f"knee_flexion_minが87ではありません: {evaluator.thresholds['knee_flexion_min']}"

    def test_landmark_indices(self, evaluator):
        """
        What: ランドマークインデックス定義テスト
        Why: MediaPipe Pose標準仕様準拠確認
        Design Decision: クラス変数で定義（ADR-003）

        CRITICAL: インデックス削除・変更禁止
        """
        # 検証: 必須ランドマークインデックス存在
        assert hasattr(evaluator, 'LEFT_HIP'), "LEFT_HIPが定義されていません"
        assert hasattr(evaluator, 'RIGHT_HIP'), "RIGHT_HIPが定義されていません"
        assert hasattr(evaluator, 'LEFT_KNEE'), "LEFT_KNEEが定義されていません"
        assert hasattr(evaluator, 'RIGHT_KNEE'), "RIGHT_KNEEが定義されていません"
        assert hasattr(evaluator, 'LEFT_ANKLE'), "LEFT_ANKLEが定義されていません"
        assert hasattr(evaluator, 'RIGHT_ANKLE'), "RIGHT_ANKLEが定義されていません"

        # 検証: MediaPipe標準値
        assert evaluator.LEFT_HIP == 23, f"LEFT_HIP != 23: {evaluator.LEFT_HIP}"
        assert evaluator.RIGHT_HIP == 24, f"RIGHT_HIP != 24: {evaluator.RIGHT_HIP}"
        assert evaluator.LEFT_KNEE == 25, f"LEFT_KNEE != 25: {evaluator.LEFT_KNEE}"
        assert evaluator.RIGHT_KNEE == 26, f"RIGHT_KNEE != 26: {evaluator.RIGHT_KNEE}"
        assert evaluator.LEFT_ANKLE == 27, f"LEFT_ANKLE != 27: {evaluator.LEFT_ANKLE}"
        assert evaluator.RIGHT_ANKLE == 28, f"RIGHT_ANKLE != 28: {evaluator.RIGHT_ANKLE}"

    def test_calculate_knee_angle_normal(self, evaluator):
        """
        What: 膝角度計算テスト（正常系）
        Why: _calculate_knee_angle()の正確性検証
        Design Decision: 2Dベクトル内積で角度計算（ADR-003）

        CRITICAL: 90°、180°等の既知角度で検証
        """
        # PHASE CORE LOGIC: 90°テスト
        hip = {'x': 0.5, 'y': 0.3, 'z': 0.0}
        knee = {'x': 0.5, 'y': 0.5, 'z': 0.0}
        ankle = {'x': 0.7, 'y': 0.5, 'z': 0.0}

        angle = evaluator._calculate_knee_angle(hip, knee, ankle)

        # 検証: 90°±1°
        assert angle is not None, "角度がNoneです"
        assert 89 <= angle <= 91, f"90°期待ですが: {angle:.1f}°"

        # PHASE CORE LOGIC: 180°テスト（完全伸展）
        hip_straight = {'x': 0.5, 'y': 0.3, 'z': 0.0}
        knee_straight = {'x': 0.5, 'y': 0.5, 'z': 0.0}
        ankle_straight = {'x': 0.5, 'y': 0.7, 'z': 0.0}

        angle_straight = evaluator._calculate_knee_angle(hip_straight, knee_straight, ankle_straight)

        # 検証: 180°±1°
        assert angle_straight is not None, "角度がNoneです"
        assert 179 <= angle_straight <= 181, f"180°期待ですが: {angle_straight:.1f}°"

    def test_calculate_knee_angle_edge_cases(self, evaluator):
        """
        What: 膝角度計算テスト（エッジケース）
        Why: NaN/ゼロ除算時のNone返却確認
        Design Decision: 例外投げずにNone返却（ADR-003）

        CRITICAL: 例外投げずにNone返却
        """
        # PHASE CORE LOGIC: 同一座標（ゼロ除算）
        same_point = {'x': 0.5, 'y': 0.5, 'z': 0.0}
        angle_zero = evaluator._calculate_knee_angle(same_point, same_point, same_point)

        # 検証: Noneを返す（例外投げない）
        assert angle_zero is None, f"同一座標でNoneを返すべきですが: {angle_zero}"

        # PHASE CORE LOGIC: 不正な座標（KeyError）
        invalid_point = {'x': 0.5}  # y, z なし
        valid_point = {'x': 0.5, 'y': 0.5, 'z': 0.0}
        angle_invalid = evaluator._calculate_knee_angle(invalid_point, valid_point, valid_point)

        # 検証: Noneを返す（例外投げない）
        assert angle_invalid is None, f"不正座標でNoneを返すべきですが: {angle_invalid}"

    def test_evaluate_pelvic_stability(self, evaluator, synthetic_single_leg_data):
        """
        What: 骨盤水平性評価テスト
        Why: _evaluate_pelvic_stability()の正確性検証
        Design Decision: pelvic_stability閾値使用（ADR-002）

        CRITICAL: スコア0-3点、avg_diff/max_diff計算検証
        """
        # PHASE CORE LOGIC: 骨盤水平性評価
        result = evaluator._evaluate_pelvic_stability(synthetic_single_leg_data)

        # 検証: 必須キー存在
        assert 'score' in result, "scoreが存在しません"
        assert 'avg_diff' in result, "avg_diffが存在しません"
        assert 'max_diff' in result, "max_diffが存在しません"
        assert 'frames_analyzed' in result, "frames_analyzedが存在しません"

        # 検証: スコア範囲（0-3）
        assert 0 <= result['score'] <= 3, f"スコアが0-3の範囲外です: {result['score']}"

        # 検証: frames_analyzed
        assert result['frames_analyzed'] > 0, "frames_analyzedが0です"

        # 検証: avg_diff存在（NaNでない）
        assert result['avg_diff'] is not None, "avg_diffがNoneです"
        assert not np.isnan(result['avg_diff']), "avg_diffがNaNです"

    def test_evaluate_knee_flexion(self, evaluator, synthetic_single_leg_data):
        """
        What: 膝屈曲角度評価テスト
        Why: _evaluate_knee_flexion()の正確性検証
        Design Decision: knee_flexion_min閾値使用（ADR-002）

        CRITICAL: スコア0-3点、min_angle/avg_angle計算検証
        """
        # PHASE CORE LOGIC: 膝屈曲角度評価
        result = evaluator._evaluate_knee_flexion(synthetic_single_leg_data)

        # 検証: 必須キー存在
        assert 'score' in result, "scoreが存在しません"
        assert 'min_angle' in result, "min_angleが存在しません"
        assert 'avg_angle' in result, "avg_angleが存在しません"
        assert 'frames_analyzed' in result, "frames_analyzedが存在しません"

        # 検証: スコア範囲（0-3）
        assert 0 <= result['score'] <= 3, f"スコアが0-3の範囲外です: {result['score']}"

        # 検証: frames_analyzed
        assert result['frames_analyzed'] > 0, "frames_analyzedが0です"

        # 検証: min_angle存在（NaNでない）
        assert result['min_angle'] is not None, "min_angleがNoneです"
        assert not np.isnan(result['min_angle']), "min_angleがNaNです"

        # 検証: min_angle <= avg_angle（論理チェック）
        assert result['min_angle'] <= result['avg_angle'], \
            f"min_angle > avg_angleです: {result['min_angle']} > {result['avg_angle']}"

    def test_evaluate_knee_angle_ratio(self, evaluator, synthetic_single_leg_data):
        """
        What: 膝角度比評価テスト
        Why: _evaluate_knee_angle_ratio()の正確性検証
        Design Decision: ハードコード閾値20°使用（将来config化）（ADR-002）

        CRITICAL: スコア0-3点、avg_diff/max_diff計算検証
        """
        # PHASE CORE LOGIC: 膝角度比評価
        result = evaluator._evaluate_knee_angle_ratio(synthetic_single_leg_data)

        # 検証: 必須キー存在
        assert 'score' in result, "scoreが存在しません"
        assert 'avg_diff' in result, "avg_diffが存在しません"
        assert 'max_diff' in result, "max_diffが存在しません"
        assert 'frames_analyzed' in result, "frames_analyzedが存在しません"

        # 検証: スコア範囲（0-3）
        assert 0 <= result['score'] <= 3, f"スコアが0-3の範囲外です: {result['score']}"

        # 検証: frames_analyzed
        assert result['frames_analyzed'] > 0, "frames_analyzedが0です"

        # 検証: avg_diff存在（NaNでない）
        assert result['avg_diff'] is not None, "avg_diffがNoneです"
        assert not np.isnan(result['avg_diff']), "avg_diffがNaNです"

    def test_evaluate_total_score(self, evaluator, synthetic_single_leg_data):
        """
        What: 総合評価テスト
        Why: evaluate()の正確性検証、min(3指標)ルール確認
        Design Decision: 3指標の最小値が総合スコア（ADR-002）

        CRITICAL: 総合スコア = min(骨盤, 膝角度比, 膝屈曲)
        """
        # PHASE CORE LOGIC: 総合評価
        result = evaluator.evaluate(synthetic_single_leg_data)

        # 検証: 必須キー存在
        assert 'score' in result, "scoreが存在しません"
        assert 'pelvic_stability' in result, "pelvic_stabilityが存在しません"
        assert 'knee_angle_ratio' in result, "knee_angle_ratioが存在しません"
        assert 'knee_flexion' in result, "knee_flexionが存在しません"
        assert 'details' in result, "detailsが存在しません"

        # 検証: 総合スコア範囲（0-3）
        assert 0 <= result['score'] <= 3, f"総合スコアが0-3の範囲外です: {result['score']}"

        # 検証: 総合スコア = min(3指標)
        min_score = min(
            result['pelvic_stability']['score'],
            result['knee_angle_ratio']['score'],
            result['knee_flexion']['score']
        )
        assert result['score'] == min_score, \
            f"総合スコアがmin(3指標)と一致しません: {result['score']} != {min_score}"

        # 検証: details文字列
        assert isinstance(result['details'], str), "detailsが文字列ではありません"
        assert len(result['details']) > 0, "detailsが空文字列です"

    def test_evaluate_empty_data(self, evaluator):
        """
        What: 空データ処理テスト
        Why: landmarks_data=[]の場合のスコア0返却確認
        Design Decision: 例外投げずにスコア0返却（ADR-003）

        CRITICAL: 例外投げずにスコア0、詳細メッセージ返却
        """
        # PHASE CORE LOGIC: 空データで評価
        empty_data = []
        result = evaluator.evaluate(empty_data)

        # 検証: スコア0
        assert result['score'] == 0, f"空データでスコア0を返すべきですが: {result['score']}"

        # 検証: 各指標もスコア0
        assert result['pelvic_stability']['score'] == 0, \
            "骨盤安定性スコアが0ではありません"
        assert result['knee_angle_ratio']['score'] == 0, \
            "膝角度比スコアが0ではありません"
        assert result['knee_flexion']['score'] == 0, \
            "膝屈曲スコアが0ではありません"

        # 検証: avg_diff等はNone
        assert result['pelvic_stability']['avg_diff'] is None, \
            "骨盤avg_diffがNoneではありません"
        assert result['knee_angle_ratio']['avg_diff'] is None, \
            "膝角度比avg_diffがNoneではありません"
        assert result['knee_flexion']['min_angle'] is None, \
            "膝屈曲min_angleがNoneではありません"

        # 検証: details存在
        assert 'details' in result, "detailsが存在しません"
        assert '検出できませんでした' in result['details'], \
            "detailsに検出失敗メッセージが含まれていません"

    def test_generate_details(self, evaluator):
        """
        What: 詳細メッセージ生成テスト
        Why: _generate_details()の正確性検証
        Design Decision: 3指標すべてを含むサマリー（ADR-002）

        CRITICAL: NaN時は"データなし"表示
        """
        # PHASE CORE LOGIC: スコア3のdetails
        pelvic_result = {'score': 3, 'avg_diff': 0.01, 'max_diff': 0.02, 'frames_analyzed': 10}
        knee_result = {'score': 3, 'avg_diff': 25.0, 'max_diff': 30.0, 'frames_analyzed': 10}
        flexion_result = {'score': 3, 'min_angle': 80.0, 'avg_angle': 85.0, 'frames_analyzed': 10}

        details = evaluator._generate_details(3, pelvic_result, knee_result, flexion_result)

        # 検証: 総合評価レベル
        assert '優秀' in details, "スコア3で'優秀'が含まれていません"

        # 検証: 3指標すべて含まれる
        assert '骨盤安定性スコア' in details, "骨盤安定性が含まれていません"
        assert '膝屈曲スコア' in details, "膝屈曲が含まれていません"
        assert '膝角度比スコア' in details, "膝角度比が含まれていません"

        # PHASE CORE LOGIC: NaN時のdetails
        pelvic_none = {'score': 0, 'avg_diff': None, 'max_diff': None, 'frames_analyzed': 0}
        knee_none = {'score': 0, 'avg_diff': None, 'max_diff': None, 'frames_analyzed': 0}
        flexion_none = {'score': 0, 'min_angle': None, 'avg_angle': None, 'frames_analyzed': 0}

        details_none = evaluator._generate_details(0, pelvic_none, knee_none, flexion_none)

        # 検証: "データなし"表示
        assert 'データなし' in details_none, "NaN時に'データなし'が表示されていません"
        assert '要トレーニング' in details_none, "スコア0で'要トレーニング'が含まれていません"

    def test_real_data_integration(self, evaluator, sample_landmarks):
        """
        What: 実データ統合テスト
        Why: sample_landmarks.json全体での動作確認
        Design Decision: 全フレーム処理（ADR-005）

        CRITICAL: 全フレーム処理成功、結果構造検証
        """
        # PHASE CORE LOGIC: 全フレーム評価（最初の100フレームのみ）
        test_data = sample_landmarks[:100]
        result = evaluator.evaluate(test_data)

        # 検証: 必須キー存在
        assert 'score' in result, "scoreが存在しません"
        assert 'pelvic_stability' in result, "pelvic_stabilityが存在しません"
        assert 'knee_angle_ratio' in result, "knee_angle_ratioが存在しません"
        assert 'knee_flexion' in result, "knee_flexionが存在しません"
        assert 'details' in result, "detailsが存在しません"

        # 検証: 総合スコア範囲
        assert 0 <= result['score'] <= 3, f"総合スコアが0-3の範囲外です: {result['score']}"

        # 検証: 各指標のframes_analyzed > 0
        assert result['pelvic_stability']['frames_analyzed'] > 0, \
            "骨盤安定性のframes_analyzedが0です"
        assert result['knee_angle_ratio']['frames_analyzed'] > 0, \
            "膝角度比のframes_analyzedが0です"
        assert result['knee_flexion']['frames_analyzed'] > 0, \
            "膝屈曲のframes_analyzedが0です"

        # 検証: 総合スコア = min(3指標)
        min_score = min(
            result['pelvic_stability']['score'],
            result['knee_angle_ratio']['score'],
            result['knee_flexion']['score']
        )
        assert result['score'] == min_score, \
            f"総合スコアがmin(3指標)と一致しません: {result['score']} != {min_score}"

    def test_scoring_thresholds(self, evaluator, config_values):
        """
        What: スコアリング閾値テスト
        Why: config.json閾値が正しく適用されるか確認
        Design Decision: pelvic_stability閾値使用（ADR-002）

        CRITICAL: 閾値境界値でスコア変化確認
        """
        # PHASE CORE LOGIC: config.json閾値取得
        pelvic_thresholds = config_values['thresholds']['pelvic_stability']
        tilt_excellent = pelvic_thresholds['tilt_excellent']  # 0.02
        tilt_good = pelvic_thresholds['tilt_good']  # 0.05
        tilt_improvement = pelvic_thresholds['tilt_improvement']  # 0.10

        knee_flexion_min = config_values['thresholds']['single_leg_squat']['knee_flexion_min']  # 87

        # 検証: 閾値値確認
        assert tilt_excellent == 0.02, f"tilt_excellent != 0.02: {tilt_excellent}"
        assert tilt_good == 0.05, f"tilt_good != 0.05: {tilt_good}"
        assert tilt_improvement == 0.10, f"tilt_improvement != 0.10: {tilt_improvement}"
        assert knee_flexion_min == 87, f"knee_flexion_min != 87: {knee_flexion_min}"

        # 検証: evaluator閾値と一致
        assert evaluator.thresholds['knee_flexion_min'] == knee_flexion_min, \
            "evaluator.thresholdsとconfig.jsonが一致しません"


if __name__ == '__main__':
    """
    What: pytest実行
    Why: python -m pytest tests/test_single_leg_squat.py で実行
    Design Decision: pytest標準準拠（ADR-005）

    CRITICAL: モジュールとしてインポート時は実行されない
    """
    pytest.main([__file__, '-v'])
