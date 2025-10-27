"""
Purpose: single_leg_squat.pyの単体テスト（12点満点システム）
Responsibility: 片脚スタンススクワット評価器の検証、評価器単体テストのテンプレート
Dependencies: pytest, single_leg_squat.py, sample_landmarks.json, config.json
Created: 2025-10-21 by Claude
Updated: 2025-10-27 - ADR-016対応（12点満点システム）
Decision Log: ADR-002, ADR-003, ADR-005, ADR-016

CRITICAL: execution(0-3点) + principles(0-9点) = 12点満点検証必須
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
    What: SingleLegSquatEvaluatorクラスの単体テスト（12点満点システム）
    Why: 片脚スタンススクワット評価の正確性保証、評価器単体テストのテンプレート
    Design Decision: pytest標準準拠、sample_landmarks.json使用（ADR-005, ADR-016）

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
    def base_width(self):
        """
        What: テスト用base_width値
        Why: 正規化パラメータとして必須（ADR-016）
        Design Decision: 典型的な値0.2を使用

        CRITICAL: evaluator.evaluate()にはbase_width必須
        """
        return 0.2

    @pytest.fixture
    def synthetic_single_leg_data(self):
        """
        What: 片脚スクワットの合成データ生成
        Why: 特定パターンのテスト用
        Design Decision: 軸脚右、遊脚左でテスト（ADR-003）

        CRITICAL: 評価可能な最小限のランドマークデータ
        """
        # PHASE CORE LOGIC: 片脚スクワットデータ生成
        data = []
        for i in range(10):
            landmarks = [{'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 1.0} for _ in range(33)]

            # 骨盤（水平）
            landmarks[23] = {'x': 0.4, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}  # LEFT_HIP
            landmarks[24] = {'x': 0.6, 'y': 0.501, 'z': 0.0, 'visibility': 1.0}  # RIGHT_HIP

            # 右脚軸脚（膝屈曲）
            landmarks[24] = {'x': 0.6, 'y': 0.4, 'z': 0.0, 'visibility': 1.0}  # RIGHT_HIP
            landmarks[26] = {'x': 0.6, 'y': 0.6, 'z': 0.0, 'visibility': 1.0}  # RIGHT_KNEE
            landmarks[28] = {'x': 0.65, 'y': 0.8, 'z': 0.0, 'visibility': 1.0}  # RIGHT_ANKLE

            # 左脚遊脚（伸展）
            landmarks[23] = {'x': 0.4, 'y': 0.401, 'z': 0.0, 'visibility': 1.0}  # LEFT_HIP
            landmarks[25] = {'x': 0.4, 'y': 0.6, 'z': 0.0, 'visibility': 1.0}  # LEFT_KNEE
            landmarks[27] = {'x': 0.39, 'y': 0.8, 'z': 0.0, 'visibility': 1.0}  # LEFT_ANKLE

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
        Design Decision: config.json一元管理（ADR-002, ADR-016）

        CRITICAL: 12点満点システム用閾値読み込み確認
        """
        # 検証: config読み込み成功
        assert evaluator.config is not None, "configが読み込まれていません"
        assert 'thresholds' in evaluator.config, "thresholdsが存在しません"

        # 検証: T01_single_leg_squat閾値（ADR-016: 12点満点システム構造）
        assert 'T01_single_leg_squat' in evaluator.config['thresholds'], \
            "T01_single_leg_squat閾値が存在しません"

        # 検証: execution + principles構造
        thresholds = config_values['thresholds']['T01_single_leg_squat']
        assert 'execution' in thresholds, "execution閾値が存在しません"
        assert 'principles' in thresholds, "principles閾値が存在しません"

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

    def test_evaluate_with_base_width(self, evaluator, synthetic_single_leg_data, base_width):
        """
        What: base_widthパラメータテスト
        Why: ADR-016で必須化されたパラメータの動作確認
        Design Decision: base_widthは正規化パラメータとして必須

        CRITICAL: base_widthなしでは実行不可
        """
        # PHASE CORE LOGIC: base_widthありで評価
        result = evaluator.evaluate(synthetic_single_leg_data, base_width=base_width)

        # 検証: 必須キー存在（ADR-016: 12点満点システム）
        assert 'test_id' in result, "test_idが存在しません"
        assert 'execution' in result, "executionが存在しません"
        assert 'principles' in result, "principlesが存在しません"
        assert 'total' in result, "totalが存在しません"
        assert 'max_score' in result, "max_scoreが存在しません"

        # 検証: max_score = 12.0
        assert result['max_score'] == 12.0, f"max_scoreが12.0ではありません: {result['max_score']}"

        # 検証: スコア範囲（0-12）
        assert 0 <= result['total'] <= 12, f"totalスコアが0-12の範囲外です: {result['total']}"

        # 検証: execution + principles = total
        execution_total = result['execution']['total']
        principles_total = result['principles']['total']
        assert abs(result['total'] - (execution_total + principles_total)) < 0.01, \
            f"total != execution + principles: {result['total']} != {execution_total} + {principles_total}"

    def test_evaluate_empty_data(self, evaluator, base_width):
        """
        What: 空データ処理テスト
        Why: landmarks_data=[]の場合のスコア0返却確認
        Design Decision: 例外投げずにスコア0返却（ADR-003, ADR-016）

        CRITICAL: 例外投げずにスコア0、詳細メッセージ返却
        """
        # PHASE CORE LOGIC: 空データで評価
        empty_data = []
        result = evaluator.evaluate(empty_data, base_width=base_width)

        # 検証: total = 0
        assert result['total'] == 0, f"空データでtotal=0を返すべきですが: {result['total']}"

        # 検証: execution.total = 0
        assert result['execution']['total'] == 0.0, \
            f"execution.totalが0.0ではありません: {result['execution']['total']}"

        # 検証: principles.total = 0
        assert result['principles']['total'] == 0.0, \
            f"principles.totalが0.0ではありません: {result['principles']['total']}"

        # 検証: details存在
        assert 'details' in result, "detailsが存在しません"
        assert '検出できませんでした' in result['details'], \
            "detailsに検出失敗メッセージが含まれていません"

    def test_evaluate_score_range(self, evaluator, synthetic_single_leg_data, base_width):
        """
        What: スコア範囲テスト
        Why: execution(0-3) + principles(0-9) = total(0-12)検証
        Design Decision: ADR-016の12点満点システム検証

        CRITICAL: 各スコア範囲の境界値確認
        """
        # PHASE CORE LOGIC: 評価実行
        result = evaluator.evaluate(synthetic_single_leg_data, base_width=base_width)

        # 検証: execution範囲（0-3）
        execution_total = result['execution']['total']
        assert 0 <= execution_total <= 3, \
            f"execution.totalが0-3の範囲外です: {execution_total}"

        # 検証: principles範囲（0-9）
        principles_total = result['principles']['total']
        assert 0 <= principles_total <= 9, \
            f"principles.totalが0-9の範囲外です: {principles_total}"

        # 検証: total範囲（0-12）
        assert 0 <= result['total'] <= 12, \
            f"totalが0-12の範囲外です: {result['total']}"

        # 検証: total = execution + principles
        expected_total = execution_total + principles_total
        assert abs(result['total'] - expected_total) < 0.01, \
            f"total != execution + principles: {result['total']} != {expected_total}"

    def test_evaluate_result_structure(self, evaluator, synthetic_single_leg_data, base_width):
        """
        What: 結果構造テスト
        Why: 12点満点システムの結果フォーマット検証
        Design Decision: ADR-016で規定された構造準拠

        CRITICAL: execution/principles内部構造確認
        """
        # PHASE CORE LOGIC: 評価実行
        result = evaluator.evaluate(synthetic_single_leg_data, base_width=base_width)

        # 検証: トップレベルキー
        required_keys = ['test_id', 'execution', 'principles', 'total', 'max_score']
        for key in required_keys:
            assert key in result, f"{key}が存在しません"

        # 検証: executionはDict with 'total'
        assert isinstance(result['execution'], dict), "executionがdictではありません"
        assert 'total' in result['execution'], "execution.totalが存在しません"

        # 検証: principlesはDict with 'total'
        assert isinstance(result['principles'], dict), "principlesがdictではありません"
        assert 'total' in result['principles'], "principles.totalが存在しません"

        # 検証: totalはfloat/int
        assert isinstance(result['total'], (int, float)), \
            f"totalがint/floatではありません: {type(result['total'])}"

        # 検証: test_id形式
        assert result['test_id'] == 'T01_single_leg_squat', \
            f"test_idが期待値と異なります: {result['test_id']}"

    def test_real_data_integration(self, evaluator, sample_landmarks, base_width):
        """
        What: 実データ統合テスト
        Why: sample_landmarks.json全体での動作確認
        Design Decision: 全フレーム処理（ADR-005, ADR-016）

        CRITICAL: 全フレーム処理成功、12点満点システム結果構造検証
        """
        # PHASE CORE LOGIC: 実データ評価（最初の100フレーム）
        test_data = sample_landmarks[:100]
        result = evaluator.evaluate(test_data, base_width=base_width)

        # 検証: 必須キー存在
        assert 'test_id' in result, "test_idが存在しません"
        assert 'execution' in result, "executionが存在しません"
        assert 'principles' in result, "principlesが存在しません"
        assert 'total' in result, "totalが存在しません"

        # 検証: totalスコア範囲
        assert 0 <= result['total'] <= 12, f"totalが0-12の範囲外です: {result['total']}"

        # 検証: execution範囲
        assert 0 <= result['execution']['total'] <= 3, \
            f"execution.totalが0-3の範囲外です: {result['execution']['total']}"

        # 検証: principles範囲
        assert 0 <= result['principles']['total'] <= 9, \
            f"principles.totalが0-9の範囲外です: {result['principles']['total']}"

        # 検証: total = execution + principles
        expected_total = result['execution']['total'] + result['principles']['total']
        assert abs(result['total'] - expected_total) < 0.01, \
            f"total != execution + principles: {result['total']} != {expected_total}"

    def test_scoring_thresholds(self, evaluator, config_values):
        """
        What: スコアリング閾値テスト
        Why: config.json閾値が正しく適用されるか確認
        Design Decision: ADR-016の12点満点システム閾値構造

        CRITICAL: execution/principles各閾値確認
        """
        # PHASE CORE LOGIC: config.json閾値取得
        thresholds = config_values['thresholds']['T01_single_leg_squat']

        # 検証: execution閾値存在
        assert 'execution' in thresholds, "execution閾値が存在しません"
        execution_thresholds = thresholds['execution']
        assert 'knee_flexion' in execution_thresholds, "knee_flexion閾値が存在しません"
        assert 'completion' in execution_thresholds, "completion閾値が存在しません"

        # 検証: principles閾値存在
        assert 'principles' in thresholds, "principles閾値が存在しません"
        principles_thresholds = thresholds['principles']
        assert 'P1_compensation' in principles_thresholds, "P1_compensation閾値が存在しません"
        assert 'P2_stability' in principles_thresholds, "P2_stability閾値が存在しません"
        assert 'P4_pelvis_level' in principles_thresholds, "P4_pelvis_level閾値が存在しません"

        # 検証: evaluator閾値と一致
        assert evaluator.thresholds == thresholds, \
            "evaluator.thresholdsとconfig.jsonが一致しません"

    def test_evaluate_without_base_width_fails(self, evaluator, synthetic_single_leg_data):
        """
        What: base_widthなしでのエラーテスト
        Why: ADR-016でbase_widthが必須パラメータであることの確認
        Design Decision: base_widthなしではTypeError発生

        CRITICAL: base_widthは省略不可
        """
        # PHASE CORE LOGIC: base_widthなしで評価（エラー期待）
        with pytest.raises(TypeError):
            evaluator.evaluate(synthetic_single_leg_data)  # base_widthなし


if __name__ == '__main__':
    """
    What: pytest実行
    Why: python -m pytest tests/test_single_leg_squat.py で実行
    Design Decision: pytest標準準拠（ADR-005）

    CRITICAL: モジュールとしてインポート時は実行されない
    """
    pytest.main([__file__, '-v'])
