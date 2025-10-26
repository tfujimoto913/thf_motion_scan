"""
Purpose: single_leg_squat.pyの単体テスト（2軸評価システム版）
Responsibility: 片脚スタンススクワット評価器の検証（A評価3点 + B評価9点 = 計12点）
Dependencies: pytest, single_leg_squat.py, normalizer.py, sample_landmarks.json, config.json
Created: 2025-10-26 by Claude
Decision Log: ADR-002, ADR-003, ADR-005

CRITICAL: 2軸評価システム検証必須（execution + principles）、主観的指標禁止
"""
import pytest
import json
import numpy as np
from pathlib import Path
import sys

# CRITICAL: processing/モジュールをインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from processing.evaluators.single_leg_squat import SingleLegSquatEvaluator
from processing.normalizer import BodyNormalizer


class TestSingleLegSquatEvaluatorV2:
    """
    What: SingleLegSquatEvaluatorクラスの単体テスト（2軸評価システム版）
    Why: 片脚スタンススクワット評価の正確性保証（A評価3点 + B評価9点）
    Design Decision: pytest標準準拠、sample_landmarks.json使用

    CRITICAL: 2軸評価システム検証（execution + principles）
    """

    @pytest.fixture
    def evaluator(self):
        """
        What: SingleLegSquatEvaluatorインスタンス生成
        Why: 各テストで再利用
        Design Decision: config.json使用
        """
        return SingleLegSquatEvaluator('config.json')

    @pytest.fixture
    def normalizer(self):
        """
        What: BodyNormalizerインスタンス生成
        Why: base_width計算用
        Design Decision: config.json使用
        """
        return BodyNormalizer('config.json')

    @pytest.fixture
    def sample_landmarks(self):
        """
        What: sample_landmarks.json読み込み
        Why: 実データでテスト
        Design Decision: tests/fixtures/sample_landmarks.json使用

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
        Design Decision: config.json一元管理
        """
        config_path = Path(__file__).parent.parent / 'config.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config

    def test_evaluator_initialization(self, evaluator, config_values):
        """
        What: 初期化テスト
        Why: config.json読み込みと閾値設定確認
        Design Decision: T01_single_leg_squat閾値使用

        CRITICAL: T01_single_leg_squat閾値が正しく読み込まれること
        """
        # 検証: config読み込み成功
        assert evaluator.config is not None, "configが読み込まれていません"
        assert 'thresholds' in evaluator.config, "thresholdsが存在しません"

        # 検証: T01_single_leg_squat閾値
        assert 'T01_single_leg_squat' in evaluator.config['thresholds'], \
            "T01_single_leg_squat閾値が存在しません"

        assert evaluator.thresholds == config_values['thresholds']['T01_single_leg_squat'], \
            "閾値が一致しません"

        # 検証: execution閾値
        assert 'execution' in evaluator.thresholds, "execution閾値が存在しません"
        assert 'principles' in evaluator.thresholds, "principles閾値が存在しません"

    def test_evaluation_structure(self, evaluator, normalizer, sample_landmarks):
        """
        What: 評価結果構造テスト
        Why: 2軸評価システムの出力形式確認
        Design Decision: execution + principles構造

        CRITICAL: test_id, execution, principles, total, max_score が含まれること
        """
        # base_width計算
        rep_values, _ = normalizer.normalize_landmarks_sequence(sample_landmarks[:100])
        base_width = rep_values['base_width']

        # 評価実行
        result = evaluator.evaluate(sample_landmarks[:100], base_width)

        # 検証: 必須キー存在
        assert 'test_id' in result, "test_idが存在しません"
        assert 'execution' in result, "executionが存在しません"
        assert 'principles' in result, "principlesが存在しません"
        assert 'total' in result, "totalが存在しません"
        assert 'max_score' in result, "max_scoreが存在しません"

        # 検証: test_id
        assert result['test_id'] == 'T01_single_leg_squat', \
            f"test_idが一致しません: {result['test_id']}"

        # 検証: max_score
        assert result['max_score'] == 12.0, \
            f"max_scoreが12.0ではありません: {result['max_score']}"

        # 検証: 総合スコア範囲
        assert 0 <= result['total'] <= 12.0, \
            f"総合スコアが0-12の範囲外です: {result['total']}"

    def test_execution_evaluation(self, evaluator, sample_landmarks):
        """
        What: A評価（動作完全性）テスト
        Why: knee_flexion(1.5点) + completion(1.5点) = 3点
        Design Decision: 2評価項目検証

        CRITICAL: knee_flexion, completion, total が含まれること
        """
        # A評価実行
        execution = evaluator.evaluate_execution(sample_landmarks[:100])

        # 検証: 必須キー存在
        assert 'knee_flexion' in execution, "knee_flexionが存在しません"
        assert 'completion' in execution, "completionが存在しません"
        assert 'total' in execution, "totalが存在しません"

        # 検証: knee_flexion構造
        assert 'value' in execution['knee_flexion'], "knee_flexion.valueが存在しません"
        assert 'score' in execution['knee_flexion'], "knee_flexion.scoreが存在しません"
        assert 'max' in execution['knee_flexion'], "knee_flexion.maxが存在しません"
        assert execution['knee_flexion']['max'] == 1.5, \
            f"knee_flexion.maxが1.5ではありません: {execution['knee_flexion']['max']}"

        # 検証: completion構造
        assert 'value' in execution['completion'], "completion.valueが存在しません"
        assert 'score' in execution['completion'], "completion.scoreが存在しません"
        assert 'max' in execution['completion'], "completion.maxが存在しません"
        assert execution['completion']['max'] == 1.5, \
            f"completion.maxが1.5ではありません: {execution['completion']['max']}"

        # 検証: スコア範囲
        assert 0 <= execution['knee_flexion']['score'] <= 1.5, \
            f"knee_flexion.scoreが範囲外: {execution['knee_flexion']['score']}"
        assert 0 <= execution['completion']['score'] <= 1.5, \
            f"completion.scoreが範囲外: {execution['completion']['score']}"
        assert 0 <= execution['total'] <= 3.0, \
            f"execution.totalが範囲外: {execution['total']}"

        # 検証: total = knee_flexion + completion
        expected_total = execution['knee_flexion']['score'] + execution['completion']['score']
        assert abs(execution['total'] - expected_total) < 1e-6, \
            f"execution.totalが合計と一致しません: {execution['total']} != {expected_total}"

    def test_principles_evaluation(self, evaluator, normalizer, sample_landmarks):
        """
        What: B評価（7原則達成度）テスト
        Why: P1(3点) + P2(3点) + P4(3点) = 9点
        Design Decision: 3原則検証

        CRITICAL: P1_compensation, P2_stability, P4_pelvis_level が含まれること
        """
        # base_width計算
        rep_values, _ = normalizer.normalize_landmarks_sequence(sample_landmarks[:100])
        base_width = rep_values['base_width']

        # B評価実行
        principles = evaluator.evaluate_principles(sample_landmarks[:100], base_width)

        # 検証: 必須キー存在
        assert 'P1_compensation' in principles, "P1_compensationが存在しません"
        assert 'P2_stability' in principles, "P2_stabilityが存在しません"
        assert 'P4_pelvis_level' in principles, "P4_pelvis_levelが存在しません"
        assert 'total' in principles, "totalが存在しません"

        # 検証: P1構造
        assert 'score' in principles['P1_compensation'], "P1.scoreが存在しません"
        assert 'max' in principles['P1_compensation'], "P1.maxが存在しません"
        assert principles['P1_compensation']['max'] == 3.0, \
            f"P1.maxが3.0ではありません: {principles['P1_compensation']['max']}"

        # 検証: P2構造
        assert 'score' in principles['P2_stability'], "P2.scoreが存在しません"
        assert 'max' in principles['P2_stability'], "P2.maxが存在しません"
        assert principles['P2_stability']['max'] == 3.0, \
            f"P2.maxが3.0ではありません: {principles['P2_stability']['max']}"

        # 検証: P4構造
        assert 'score' in principles['P4_pelvis_level'], "P4.scoreが存在しません"
        assert 'max' in principles['P4_pelvis_level'], "P4.maxが存在しません"
        assert principles['P4_pelvis_level']['max'] == 3.0, \
            f"P4.maxが3.0ではありません: {principles['P4_pelvis_level']['max']}"

        # 検証: スコア範囲
        assert 0 <= principles['P1_compensation']['score'] <= 3.0, \
            f"P1.scoreが範囲外: {principles['P1_compensation']['score']}"
        assert 0 <= principles['P2_stability']['score'] <= 3.0, \
            f"P2.scoreが範囲外: {principles['P2_stability']['score']}"
        assert 0 <= principles['P4_pelvis_level']['score'] <= 3.0, \
            f"P4.scoreが範囲外: {principles['P4_pelvis_level']['score']}"
        assert 0 <= principles['total'] <= 9.0, \
            f"principles.totalが範囲外: {principles['total']}"

        # 検証: total = P1 + P2 + P4
        expected_total = (
            principles['P1_compensation']['score'] +
            principles['P2_stability']['score'] +
            principles['P4_pelvis_level']['score']
        )
        assert abs(principles['total'] - expected_total) < 1e-6, \
            f"principles.totalが合計と一致しません: {principles['total']} != {expected_total}"

    def test_knee_angle_calculation(self, evaluator):
        """
        What: 膝角度計算テスト（正常系）
        Why: _calculate_knee_angle()の正確性検証
        Design Decision: 3Dベクトル内積で角度計算

        CRITICAL: 90°、180°等の既知角度で検証
        """
        # 90°テスト
        hip = {'x': 0.5, 'y': 0.3, 'z': 0.0}
        knee = {'x': 0.5, 'y': 0.5, 'z': 0.0}
        ankle = {'x': 0.7, 'y': 0.5, 'z': 0.0}

        angle = evaluator._calculate_knee_angle(hip, knee, ankle)

        # 検証: 90°±1°
        assert angle is not None, "角度がNoneです"
        assert 89 <= angle <= 91, f"90°期待ですが: {angle:.1f}°"

        # 180°テスト（完全伸展）
        hip_straight = {'x': 0.5, 'y': 0.3, 'z': 0.0}
        knee_straight = {'x': 0.5, 'y': 0.5, 'z': 0.0}
        ankle_straight = {'x': 0.5, 'y': 0.7, 'z': 0.0}

        angle_straight = evaluator._calculate_knee_angle(hip_straight, knee_straight, ankle_straight)

        # 検証: 180°±1°
        assert angle_straight is not None, "角度がNoneです"
        assert 179 <= angle_straight <= 181, f"180°期待ですが: {angle_straight:.1f}°"

    def test_pelvis_tilt_calculation(self, evaluator):
        """
        What: 骨盤傾き計算テスト
        Why: _calculate_pelvis_tilt()の正確性検証
        Design Decision: atan2で角度計算

        CRITICAL: 主観性チェック ✅ 客観的（角度測定）
        """
        # 水平（0°）
        left_hip_level = {'x': 0.4, 'y': 0.5, 'z': 0.0}
        right_hip_level = {'x': 0.6, 'y': 0.5, 'z': 0.0}

        tilt_level = evaluator._calculate_pelvis_tilt(left_hip_level, right_hip_level)

        # 検証: 0°±1°
        assert tilt_level is not None, "傾きがNoneです"
        assert tilt_level < 1, f"水平で0°期待ですが: {tilt_level:.1f}°"

        # 傾斜（10°程度）
        left_hip_tilt = {'x': 0.4, 'y': 0.5, 'z': 0.0}
        right_hip_tilt = {'x': 0.6, 'y': 0.53, 'z': 0.0}  # Y差 = 0.03

        tilt_angle = evaluator._calculate_pelvis_tilt(left_hip_tilt, right_hip_tilt)

        # 検証: 0°より大きい
        assert tilt_angle is not None, "傾きがNoneです"
        assert tilt_angle > 0, f"傾斜があるはずですが: {tilt_angle:.1f}°"

    def test_knee_deviation_calculation(self, evaluator):
        """
        What: 膝逸脱計算テスト
        Why: _calculate_knee_deviation()の正確性検証
        Design Decision: 外積で垂直距離計算

        CRITICAL: 主観性チェック ✅ 客観的（距離測定）
        """
        # 正常（膝がライン上）
        hip_normal = {'x': 0.5, 'y': 0.4, 'z': 0.0}
        knee_normal = {'x': 0.5, 'y': 0.6, 'z': 0.0}
        ankle_normal = {'x': 0.5, 'y': 0.8, 'z': 0.0}

        deviation_normal = evaluator._calculate_knee_deviation(hip_normal, knee_normal, ankle_normal)

        # 検証: ほぼ0（ライン上）
        assert deviation_normal is not None, "逸脱がNoneです"
        assert deviation_normal < 0.01, f"ライン上で0期待ですが: {deviation_normal:.4f}"

        # 異常（膝が逸脱）
        hip_deviated = {'x': 0.5, 'y': 0.4, 'z': 0.0}
        knee_deviated = {'x': 0.6, 'y': 0.6, 'z': 0.0}  # X方向に逸脱
        ankle_deviated = {'x': 0.5, 'y': 0.8, 'z': 0.0}

        deviation_abnormal = evaluator._calculate_knee_deviation(hip_deviated, knee_deviated, ankle_deviated)

        # 検証: 0より大きい
        assert deviation_abnormal is not None, "逸脱がNoneです"
        assert deviation_abnormal > 0.05, f"逸脱があるはずですが: {deviation_abnormal:.4f}"

    def test_empty_data_handling(self, evaluator):
        """
        What: 空データ処理テスト
        Why: landmarks_data=[]の場合のスコア0返却確認
        Design Decision: 例外投げずにスコア0返却

        CRITICAL: 例外投げずにスコア0、詳細メッセージ返却
        """
        # 空データで評価
        empty_data = []
        result = evaluator.evaluate(empty_data, base_width=0.2)

        # 検証: スコア0
        assert result['total'] == 0.0, f"空データでスコア0を返すべきですが: {result['total']}"
        assert result['execution']['total'] == 0.0, "execution.totalが0ではありません"
        assert result['principles']['total'] == 0.0, "principles.totalが0ではありません"

        # 検証: details存在
        assert 'details' in result, "detailsが存在しません"
        assert '検出できませんでした' in result['details'], \
            "detailsに検出失敗メッセージが含まれていません"

    def test_real_data_integration(self, evaluator, normalizer, sample_landmarks):
        """
        What: 実データ統合テスト
        Why: sample_landmarks.json全体での動作確認
        Design Decision: 全フレーム処理

        CRITICAL: 全フレーム処理成功、結果構造検証
        """
        # base_width計算
        rep_values, _ = normalizer.normalize_landmarks_sequence(sample_landmarks[:100])
        base_width = rep_values['base_width']

        # 評価実行
        result = evaluator.evaluate(sample_landmarks[:100], base_width)

        # 検証: 必須キー存在
        assert 'test_id' in result, "test_idが存在しません"
        assert 'execution' in result, "executionが存在しません"
        assert 'principles' in result, "principlesが存在しません"
        assert 'total' in result, "totalが存在しません"
        assert 'max_score' in result, "max_scoreが存在しません"

        # 検証: 総合スコア範囲
        assert 0 <= result['total'] <= 12.0, \
            f"総合スコアが0-12の範囲外です: {result['total']}"

        # 検証: total = execution.total + principles.total
        expected_total = result['execution']['total'] + result['principles']['total']
        assert abs(result['total'] - expected_total) < 1e-6, \
            f"総合スコアが合計と一致しません: {result['total']} != {expected_total}"

        # デバッグ出力
        print(f"\n=== 実データ評価結果 ===")
        print(f"総合スコア: {result['total']:.2f} / 12.0")
        print(f"A評価（動作完全性）: {result['execution']['total']:.2f} / 3.0")
        print(f"  - 膝屈曲角度: {result['execution']['knee_flexion']['score']:.2f} (値: {result['execution']['knee_flexion']['value']:.1f}°)")
        print(f"  - 完遂回数: {result['execution']['completion']['score']:.2f} (値: {result['execution']['completion']['value']}回)")
        print(f"B評価（7原則達成度）: {result['principles']['total']:.2f} / 9.0")
        print(f"  - P1 代償動作: {result['principles']['P1_compensation']['score']:.2f} / 3.0")
        print(f"  - P2 安定性: {result['principles']['P2_stability']['score']:.2f} / 3.0")
        print(f"  - P4 骨盤水平: {result['principles']['P4_pelvis_level']['score']:.2f} / 3.0")


if __name__ == '__main__':
    """
    What: pytest実行
    Why: python -m pytest tests/test_single_leg_squat_v2.py で実行
    Design Decision: pytest標準準拠

    CRITICAL: モジュールとしてインポート時は実行されない
    """
    pytest.main([__file__, '-v', '-s'])
