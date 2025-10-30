"""
Purpose: evaluators_v2統合テスト（8原則・560点満点システム）
Responsibility: 全7種目の評価器動作検証（A+B評価、JSON形式、点数範囲）
Dependencies: pytest, evaluators_v2/, sample_landmarks.json
Created: 2025-10-30 by Claude
Decision Log: Phase B - 8原則評価システム完全実装検証

CRITICAL: v2システム検証必須（version="v2", 8原則, 234点満点）
"""
import pytest
import json
from pathlib import Path
import sys

# CRITICAL: processing/モジュールをインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from processing.evaluators_v2.single_leg_squat_v2 import SingleLegSquatEvaluatorV2
from processing.evaluators_v2.skater_lunge_v2 import SkaterLungeEvaluatorV2
from processing.evaluators_v2.stride_mimic_v2 import StrideMimicEvaluatorV2
from processing.evaluators_v2.jump_landing_v2 import JumpLandingEvaluatorV2
from processing.evaluators_v2.upper_body_swing_v2 import UpperBodySwingEvaluatorV2
from processing.evaluators_v2.push_pull_v2 import PushPullEvaluatorV2
from processing.evaluators_v2.cross_step_v2 import CrossStepEvaluatorV2


class TestEvaluatorsV2Integration:
    """
    What: evaluators_v2統合テストクラス
    Why: 全7種目の評価器が8原則・560点満点システムで動作することを保証
    Design Decision: pytest標準準拠、sample_landmarks.json使用

    CRITICAL: 7種目すべての動作検証（JSON形式、点数範囲、8原則）
    """

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
    def test_base_width(self):
        """
        What: テスト用base_width値
        Why: 正規化に必要
        Design Decision: 固定値0.2（典型的な肩幅）
        """
        return 0.2

    # ==================== 標準構造テスト（33点満点×5） ====================

    def test_single_leg_squat_v2(self, sample_landmarks, test_base_width):
        """
        What: ①片脚スタンススクワット評価テスト（80点満点）
        Why: B2支持基盤・B4骨盤水平が主評価
        Design Decision: Eccentric/Concentric局面別評価
        """
        evaluator = SingleLegSquatEvaluatorV2()
        result = evaluator.evaluate(sample_landmarks[:100], test_base_width)

        # JSON形式検証
        assert result['version'] == 'v2.1', f"version='v2.1'期待: {result.get('version')}"
        assert result['test_id'] == 'T01_single_leg_squat', f"test_id不一致: {result.get('test_id')}"
        assert result['max_possible'] == 80, f"max_possible=80期待: {result.get('max_possible')}"

        # 点数範囲検証
        assert 0 <= result['A_execution_score'] <= 20, f"A評価範囲外(0-20): {result['A_execution_score']}"
        assert 0 <= result['B_total'] <= 60, f"B評価範囲外(0-60): {result['B_total']}"
        assert 0 <= result['total_score'] <= 80, f"総合スコア範囲外(0-80): {result['total_score']}"

        # 8原則検証（B1, B2, B3, B4）
        assert 'B_principles' in result, "B_principlesが存在しません"
        assert 'eccentric' in result['B_principles'], "eccentric局面が存在しません"
        assert 'concentric' in result['B_principles'], "concentric局面が存在しません"

        ecc = result['B_principles']['eccentric']
        con = result['B_principles']['concentric']
        assert 'B1_core_stability' in ecc, "B1が存在しません"
        assert 'B2_support_foundation' in ecc, "B2が存在しません"
        assert 'B3_3joint_coordination' in ecc, "B3が存在しません"
        assert 'B4_pelvis_horizontal' in ecc, "B4が存在しません"

        print(f"\n✅ ①single_leg_squat: {result['total_score']:.1f}/80点")

    def test_skater_lunge_v2(self, sample_landmarks, test_base_width):
        """
        What: ②スケータランジ評価テスト（80点満点）
        Why: B4骨盤水平・B7上下身分離が主評価
        Design Decision: Eccentric/Concentric局面別評価
        """
        evaluator = SkaterLungeEvaluatorV2()
        result = evaluator.evaluate(sample_landmarks[:100], test_base_width)

        assert result['version'] == 'v2.1'
        assert result['test_id'] == 'T02_skater_lunge'
        assert result['max_possible'] == 80
        assert 0 <= result['total_score'] <= 80

        # B7（上下身分離性）検証
        ecc = result['B_principles']['eccentric']
        assert 'B7_upper_lower_separation' in ecc, "B7が存在しません"

        print(f"✅ ②skater_lunge: {result['total_score']:.1f}/80点")

    def test_stride_mimic_v2(self, sample_landmarks, test_base_width):
        """
        What: ③ストライド模倣評価テスト（80点満点）
        Why: B3関節連動・B7上下身分離が主評価
        Design Decision: Eccentric/Concentric局面別評価
        """
        evaluator = StrideMimicEvaluatorV2()
        result = evaluator.evaluate(sample_landmarks[:100], test_base_width)

        assert result['version'] == 'v2.1'
        assert result['test_id'] == 'T03_stride_mimic'
        assert result['max_possible'] == 80
        assert 0 <= result['total_score'] <= 80

        # B6（後方筋群）検証
        ecc = result['B_principles']['eccentric']
        assert 'B6_posterior_chain' in ecc, "B6が存在しません"

        print(f"✅ ③stride_mimic: {result['total_score']:.1f}/80点")

    def test_upper_body_swing_v2(self, sample_landmarks, test_base_width):
        """
        What: ⑤上体スイング評価テスト（80点満点）
        Why: B7上下身分離・B8肩周り独立制御が主評価
        Design Decision: Eccentric/Concentric局面別評価
        """
        evaluator = UpperBodySwingEvaluatorV2()
        result = evaluator.evaluate(sample_landmarks[:100], test_base_width)

        assert result['version'] == 'v2.1'
        assert result['test_id'] == 'T05_upper_body_swing'
        assert result['max_possible'] == 80
        assert 0 <= result['total_score'] <= 80

        # B8（肩周り独立制御）検証
        ecc = result['B_principles']['eccentric']
        assert 'B8_shoulder_independent_control' in ecc, "B8が存在しません"

        print(f"✅ ⑤upper_body_swing: {result['total_score']:.1f}/80点")

    def test_cross_step_v2(self, sample_landmarks, test_base_width):
        """
        What: ⑦クロスステップ評価テスト（80点満点）
        Why: B3関節連動・B5重心移動が主評価
        Design Decision: Eccentric/Concentric局面別評価
        """
        evaluator = CrossStepEvaluatorV2()
        result = evaluator.evaluate(sample_landmarks[:100], test_base_width)

        assert result['version'] == 'v2.1'
        assert result['test_id'] == 'T07_cross_step'
        assert result['max_possible'] == 80
        assert 0 <= result['total_score'] <= 80

        # B5（重心移動）検証
        ecc = result['B_principles']['eccentric']
        assert 'B5_weight_shift' in ecc, "B5が存在しません"

        print(f"✅ ⑦cross_step: {result['total_score']:.1f}/80点")

    # ==================== 特殊構造テスト ====================

    def test_jump_landing_v2_eccentric_only(self, sample_landmarks, test_base_width):
        """
        What: ④ジャンプ着地評価テスト（80点満点: Eccentricのみ特殊構造）
        Why: B2支持基盤・B6後方筋群が主評価、着地衝撃吸収のみ評価
        Design Decision: Eccentric局面のみ33点（A評価3点 + B評価33点）
        """
        evaluator = JumpLandingEvaluatorV2()
        result = evaluator.evaluate(sample_landmarks[:100], test_base_width)

        assert result['version'] == 'v2.1'
        assert result['test_id'] == 'T04_jump_landing'
        assert result['max_possible'] == 80, f"max_possible=80期待: {result.get('max_possible')}"
        assert result['special_structure'] == 'eccentric_focus', "special_structure不一致"

        # 点数範囲検証（Eccentricのみ33点）
        assert 0 <= result['A_execution_score'] <= 20, f"A評価範囲外(0-20): {result['A_execution_score']}"
        assert 0 <= result['B_total'] <= 60, f"B評価範囲外（Eccentricのみ60点）: {result['B_total']}"
        assert 0 <= result['total_score'] <= 80, f"総合スコア範囲外(0-80): {result['total_score']}"

        # Eccentric局面のみ存在確認
        assert 'B_principles' in result
        assert 'eccentric' in result['B_principles'], "eccentric局面が存在しません"
        assert 'concentric' not in result['B_principles'], "concentric局面は存在すべきでありません"

        # B6（後方筋群）検証
        ecc = result['B_principles']['eccentric']
        assert 'B6_posterior_chain' in ecc, "B6が存在しません"

        print(f"✅ ④jump_landing: {result['total_score']:.1f}/80点（Eccentricのみ）")

    def test_push_pull_v2_pull_push_separate(self, sample_landmarks, test_base_width):
        """
        What: ⑥プッシュ・プル評価テスト（33点満点: Pull/Push局面別特殊構造）
        Why: B7上下身分離・B8肩周り独立制御が主評価
        Design Decision: Pull/Push局面別評価（各15点）
        """
        evaluator = PushPullEvaluatorV2()
        result = evaluator.evaluate(sample_landmarks[:100], test_base_width)

        assert result['version'] == 'v2.1'
        assert result['test_id'] == 'T06_push_pull'
        assert result['max_possible'] == 80
        assert result['special_structure'] == 'pull_push_separate', "special_structure不一致"

        # Pull/Push局面確認
        assert 'B_principles' in result
        assert 'pull' in result['B_principles'], "pull局面が存在しません"
        assert 'push' in result['B_principles'], "push局面が存在しません"

        # B8（肩周り独立制御）検証
        pull = result['B_principles']['pull']
        assert 'B8_shoulder_independent_control' in pull, "B8が存在しません（pull）"

        print(f"✅ ⑥push_pull: {result['total_score']:.1f}/80点（Pull/Push別）")

    # ==================== 統合テスト ====================

    def test_all_evaluators_total_points(self, sample_landmarks, test_base_width):
        """
        What: 全7種目合計点数テスト
        Why: 560点満点システム検証
        Design Decision: 80×7 = 560点

        CRITICAL: 全7種目の合計が560点満点であることを確認
        """
        evaluators = [
            ('①single_leg_squat', SingleLegSquatEvaluatorV2(), 80),
            ('②skater_lunge', SkaterLungeEvaluatorV2(), 80),
            ('③stride_mimic', StrideMimicEvaluatorV2(), 80),
            ('④jump_landing', JumpLandingEvaluatorV2(), 80),
            ('⑤upper_body_swing', UpperBodySwingEvaluatorV2(), 80),
            ('⑥push_pull', PushPullEvaluatorV2(), 80),
            ('⑦cross_step', CrossStepEvaluatorV2(), 80)
        ]

        total_max_score = 0
        total_actual_score = 0

        print("\n\n===== 全7種目評価結果（8原則・560点満点システム） =====")

        for name, evaluator, max_score in evaluators:
            result = evaluator.evaluate(sample_landmarks[:100], test_base_width)
            total_max_score += max_score
            total_actual_score += result['total_score']

            print(f"{name}: {result['total_score']:.1f}/{max_score}点 "
                  f"(A:{result['A_execution_score']:.1f} + B:{result['B_total']:.1f})")

        print(f"\n合計: {total_actual_score:.1f}/{total_max_score}点")
        print("=" * 60)

        # 合計234点満点検証
        assert total_max_score == 560, f"合計max_scoreが560ではありません: {total_max_score}"
        assert 0 <= total_actual_score <= 560, f"合計スコアが範囲外(0-560): {total_actual_score}"

    def test_json_output_format_consistency(self, sample_landmarks, test_base_width):
        """
        What: JSON出力形式一貫性テスト
        Why: 全種目が同じJSON構造を返すことを保証
        Design Decision: version, test_id, A_execution_score, B_total, total_score必須

        CRITICAL: 全種目のJSON出力形式が一貫していること
        """
        evaluators = [
            SingleLegSquatEvaluatorV2(),
            SkaterLungeEvaluatorV2(),
            StrideMimicEvaluatorV2(),
            JumpLandingEvaluatorV2(),
            UpperBodySwingEvaluatorV2(),
            PushPullEvaluatorV2(),
            CrossStepEvaluatorV2()
        ]

        required_keys = ['version', 'test_id', 'timestamp', 'A_execution_score',
                         'B_principles', 'B_total', 'total_score', 'total_percentage', 'max_possible']

        for evaluator in evaluators:
            result = evaluator.evaluate(sample_landmarks[:100], test_base_width)

            # 必須キー存在確認
            for key in required_keys:
                assert key in result, f"{evaluator.__class__.__name__}: {key}が存在しません"

            # version='v2'確認
            assert result['version'] == 'v2.1', \
                f"{evaluator.__class__.__name__}: version='v2'ではありません"

            # timestamp形式確認（ISO 8601 + Z）
            assert result['timestamp'].endswith('Z'), \
                f"{evaluator.__class__.__name__}: timestamp形式不正"

            # 点数一貫性確認
            assert abs(result['total_score'] - (result['A_execution_score'] + result['B_total'])) < 0.1, \
                f"{evaluator.__class__.__name__}: total_score = A + B が成立しません"

            # percentage計算確認
            expected_percentage = int((result['total_score'] / result['max_possible']) * 100)
            assert result['total_percentage'] == expected_percentage, \
                f"{evaluator.__class__.__name__}: total_percentage計算エラー"

        print("\n✅ 全7種目のJSON出力形式が一貫しています")

    def test_empty_data_handling_all_evaluators(self, test_base_width):
        """
        What: 空データ処理テスト（全種目）
        Why: landmarks_data=[]で例外を投げずにスコア0を返すことを確認
        Design Decision: 全種目で一貫した空データ処理

        CRITICAL: 全種目が空データで例外を投げずにスコア0を返すこと
        """
        evaluators = [
            SingleLegSquatEvaluatorV2(),
            SkaterLungeEvaluatorV2(),
            StrideMimicEvaluatorV2(),
            JumpLandingEvaluatorV2(),
            UpperBodySwingEvaluatorV2(),
            PushPullEvaluatorV2(),
            CrossStepEvaluatorV2()
        ]

        for evaluator in evaluators:
            result = evaluator.evaluate([], test_base_width)

            # スコア0確認
            assert result['total_score'] == 0.0, \
                f"{evaluator.__class__.__name__}: 空データでスコア0を返すべきです"

            # エラーメッセージ確認
            assert 'details' in result, \
                f"{evaluator.__class__.__name__}: detailsが存在しません"

        print("\n✅ 全7種目が空データで正常にスコア0を返しています")


if __name__ == '__main__':
    """
    What: pytest実行
    Why: python -m pytest tests/test_evaluators_v2_integration.py で実行
    Design Decision: pytest標準準拠

    CRITICAL: モジュールとしてインポート時は実行されない
    """
    pytest.main([__file__, '-v', '-s'])
