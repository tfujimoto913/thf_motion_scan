"""
Purpose: 全評価器統合テスト
Responsibility: 7種目評価器とworker.pyの統合動作確認
Dependencies: pytest, all evaluators, worker.py, sample_landmarks.json
Created: 2025-10-21 by Claude
Decision Log: ADR-002, ADR-003, ADR-004, ADR-005

CRITICAL: 全7評価器の初期化成功、スコア0-3点返却、worker.py統合動作確認必須
"""
import pytest
import json
from pathlib import Path
import sys

# CRITICAL: processing/モジュールをインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from processing.evaluators.single_leg_squat import SingleLegSquatEvaluator
from processing.evaluators.upper_body_swing import UpperBodySwingEvaluator
from processing.evaluators.skater_lunge import SkaterLungeEvaluator
from processing.evaluators.cross_step import CrossStepEvaluator
from processing.evaluators.stride_mimic import StrideMimicEvaluator
from processing.evaluators.push_pull import PushPullEvaluator
from processing.evaluators.jump_landing import JumpLandingEvaluator
from processing.worker import VideoProcessingWorker


class TestAllEvaluators:
    """
    What: 全7評価器の統合テスト
    Why: 評価器間の独立性保証、worker.py統合動作確認
    Design Decision: 全評価器を同一条件でテスト（ADR-002, ADR-005）

    CRITICAL: 全評価器が独立して動作、スコア0-3点を返却
    """

    @pytest.fixture
    def sample_landmarks(self):
        """
        What: sample_landmarks.json読み込み
        Why: 実データで全評価器テスト
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
    def config_path(self):
        """
        What: config.jsonパス取得
        Why: 全評価器で同一config使用
        Design Decision: プロジェクトルートのconfig.json（ADR-002）
        """
        return str(Path(__file__).parent.parent / 'config.json')

    @pytest.fixture
    def all_evaluators(self, config_path):
        """
        What: 全7評価器インスタンス生成
        Why: 初期化成功確認、評価器リスト提供
        Design Decision: 辞書形式で管理（ADR-002）

        CRITICAL: 全評価器の初期化成功必須
        """
        return {
            'single_leg_squat': SingleLegSquatEvaluator(config_path),
            'upper_body_swing': UpperBodySwingEvaluator(config_path),
            'skater_lunge': SkaterLungeEvaluator(config_path),
            'cross_step': CrossStepEvaluator(config_path),
            'stride_mimic': StrideMimicEvaluator(config_path),
            'push_pull': PushPullEvaluator(config_path),
            'jump_landing': JumpLandingEvaluator(config_path)
        }

    def test_all_evaluators_initialization(self, all_evaluators):
        """
        What: 全評価器初期化テスト
        Why: config.json読み込み成功確認
        Design Decision: 全7評価器を一括検証（ADR-002）

        CRITICAL: 全評価器でconfig読み込み成功
        """
        # 検証: 7評価器すべて存在
        expected_evaluators = [
            'single_leg_squat',
            'upper_body_swing',
            'skater_lunge',
            'cross_step',
            'stride_mimic',
            'push_pull',
            'jump_landing'
        ]

        for evaluator_name in expected_evaluators:
            assert evaluator_name in all_evaluators, \
                f"{evaluator_name}が評価器リストに存在しません"

        # 検証: 全評価器でconfig読み込み成功
        for evaluator_name, evaluator in all_evaluators.items():
            assert hasattr(evaluator, 'config'), \
                f"{evaluator_name}にconfigが存在しません"
            assert evaluator.config is not None, \
                f"{evaluator_name}のconfigがNoneです"

    def test_all_evaluators_evaluate_method(self, all_evaluators):
        """
        What: 全評価器のevaluate()メソッド存在確認
        Why: 共通インターフェース保証
        Design Decision: 全評価器で同一メソッド名（ADR-002）

        CRITICAL: 全評価器でevaluate()メソッド実装必須
        """
        # 検証: 全評価器でevaluate()メソッド存在
        for evaluator_name, evaluator in all_evaluators.items():
            assert hasattr(evaluator, 'evaluate'), \
                f"{evaluator_name}にevaluate()メソッドが存在しません"
            assert callable(evaluator.evaluate), \
                f"{evaluator_name}のevaluate()がcallableではありません"

    def test_all_evaluators_with_empty_data(self, all_evaluators):
        """
        What: 全評価器の空データ処理テスト
        Why: エッジケース処理統一性確認
        Design Decision: 空データでスコア0返却（ADR-003）

        CRITICAL: 全評価器で例外投げずにスコア0返却
        """
        # PHASE CORE LOGIC: 空データで評価
        empty_data = []

        for evaluator_name, evaluator in all_evaluators.items():
            result = evaluator.evaluate(empty_data)

            # 検証: スコア0
            assert 'score' in result, \
                f"{evaluator_name}の結果にscoreが存在しません"
            assert result['score'] == 0, \
                f"{evaluator_name}が空データでスコア0を返していません: {result['score']}"

            # 検証: details存在
            assert 'details' in result, \
                f"{evaluator_name}の結果にdetailsが存在しません"

    def test_all_evaluators_score_range(self, all_evaluators, sample_landmarks):
        """
        What: 全評価器のスコア範囲テスト
        Why: スコア0-3点の範囲保証
        Design Decision: 全評価器で0-3点スコアリング（ADR-002）

        CRITICAL: 全評価器でスコア0-3点返却
        """
        # PHASE CORE LOGIC: 実データで評価（最初の50フレーム）
        test_data = sample_landmarks[:50]

        for evaluator_name, evaluator in all_evaluators.items():
            result = evaluator.evaluate(test_data)

            # 検証: スコア範囲（0-3）
            assert 'score' in result, \
                f"{evaluator_name}の結果にscoreが存在しません"
            assert 0 <= result['score'] <= 3, \
                f"{evaluator_name}のスコアが0-3の範囲外です: {result['score']}"

            # 検証: スコアは整数
            assert isinstance(result['score'], int), \
                f"{evaluator_name}のスコアが整数ではありません: {type(result['score'])}"

    def test_all_evaluators_result_structure(self, all_evaluators, sample_landmarks):
        """
        What: 全評価器の結果構造テスト
        Why: 結果フォーマット統一性確認
        Design Decision: 全評価器で'score'と'details'必須（ADR-002）

        CRITICAL: 全評価器で統一された結果構造返却
        """
        # PHASE CORE LOGIC: 実データで評価（最初の30フレーム）
        test_data = sample_landmarks[:30]

        for evaluator_name, evaluator in all_evaluators.items():
            result = evaluator.evaluate(test_data)

            # 検証: 必須キー存在
            assert 'score' in result, \
                f"{evaluator_name}の結果にscoreが存在しません"
            assert 'details' in result, \
                f"{evaluator_name}の結果にdetailsが存在しません"

            # 検証: detailsは文字列
            assert isinstance(result['details'], str), \
                f"{evaluator_name}のdetailsが文字列ではありません"
            assert len(result['details']) > 0, \
                f"{evaluator_name}のdetailsが空文字列です"

    def test_all_evaluators_independence(self, all_evaluators, sample_landmarks):
        """
        What: 全評価器の独立性テスト
        Why: 評価器間の依存関係排除確認
        Design Decision: 各評価器は独立して動作（ADR-002）

        CRITICAL: 全評価器が互いに影響せず独立動作
        """
        # PHASE CORE LOGIC: 同一データで全評価器を実行
        test_data = sample_landmarks[:40]

        # 1回目の評価
        results_1 = {}
        for evaluator_name, evaluator in all_evaluators.items():
            results_1[evaluator_name] = evaluator.evaluate(test_data)

        # 2回目の評価（同じデータ）
        results_2 = {}
        for evaluator_name, evaluator in all_evaluators.items():
            results_2[evaluator_name] = evaluator.evaluate(test_data)

        # 検証: 2回の評価で同一結果（再現性確認）
        for evaluator_name in all_evaluators.keys():
            assert results_1[evaluator_name]['score'] == results_2[evaluator_name]['score'], \
                f"{evaluator_name}の評価結果が再現できません: " \
                f"{results_1[evaluator_name]['score']} != {results_2[evaluator_name]['score']}"

    def test_worker_initialization(self, config_path):
        """
        What: VideoProcessingWorker初期化テスト
        Why: worker.pyの統合動作確認
        Design Decision: 全評価器を含むworker初期化（ADR-004）

        CRITICAL: worker初期化時に全評価器とhealth_checker初期化成功
        """
        # PHASE CORE LOGIC: worker初期化
        worker = VideoProcessingWorker(config_path)

        # 検証: 必須コンポーネント存在
        assert hasattr(worker, 'pose_extractor'), \
            "workerにpose_extractorが存在しません"
        assert hasattr(worker, 'evaluators'), \
            "workerにevaluatorsが存在しません"
        assert hasattr(worker, 'health_checker'), \
            "workerにhealth_checkerが存在しません"

        # 検証: 全7評価器存在
        expected_evaluators = [
            'single_leg_squat',
            'upper_body_swing',
            'skater_lunge',
            'cross_step',
            'stride_mimic',
            'push_pull',
            'jump_landing'
        ]

        for evaluator_name in expected_evaluators:
            assert evaluator_name in worker.evaluators, \
                f"workerの評価器リストに{evaluator_name}が存在しません"

    def test_worker_evaluators_access(self, config_path):
        """
        What: workerの評価器アクセステスト
        Why: worker経由の評価器呼び出し確認
        Design Decision: worker.evaluators辞書でアクセス（ADR-004）

        CRITICAL: worker経由で全評価器にアクセス可能
        """
        # PHASE CORE LOGIC: worker初期化
        worker = VideoProcessingWorker(config_path)

        # 検証: 全評価器にアクセス可能
        for evaluator_name in worker.evaluators.keys():
            evaluator = worker.evaluators[evaluator_name]

            # evaluate()メソッド存在確認
            assert hasattr(evaluator, 'evaluate'), \
                f"worker.evaluators['{evaluator_name}']にevaluate()が存在しません"

            # config読み込み確認
            assert hasattr(evaluator, 'config'), \
                f"worker.evaluators['{evaluator_name}']にconfigが存在しません"

    def test_worker_supported_test_types(self, config_path):
        """
        What: workerのサポートテストタイプ確認
        Why: 全7種目がサポート対象か確認
        Design Decision: evaluators辞書のキーがサポート対象（ADR-004）

        CRITICAL: 全7種目がworker.evaluatorsに登録済み
        """
        # PHASE CORE LOGIC: worker初期化
        worker = VideoProcessingWorker(config_path)

        # 検証: 7種目すべてサポート
        expected_test_types = {
            'single_leg_squat',
            'upper_body_swing',
            'skater_lunge',
            'cross_step',
            'stride_mimic',
            'push_pull',
            'jump_landing'
        }

        actual_test_types = set(worker.evaluators.keys())

        assert expected_test_types == actual_test_types, \
            f"サポート対象テストタイプが一致しません: " \
            f"期待={expected_test_types}, 実際={actual_test_types}"


if __name__ == '__main__':
    """
    What: pytest実行
    Why: python -m pytest tests/test_all_evaluators.py で実行
    Design Decision: pytest標準準拠（ADR-005）

    CRITICAL: モジュールとしてインポート時は実行されない
    """
    pytest.main([__file__, '-v'])
