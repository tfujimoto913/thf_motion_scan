"""
Purpose: normalizer.pyの単体テスト
Responsibility: 身体スケール正規化処理の検証
Dependencies: pytest, normalizer.py, sample_landmarks.json
Created: 2025-10-21 by Claude
Decision Log: ADR-003, ADR-005

CRITICAL: NaN処理検証必須、中央値計算検証必須
"""
import pytest
import json
import numpy as np
from pathlib import Path
import sys

# CRITICAL: processing/モジュールをインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from processing.normalizer import BodyNormalizer, normalize_value


class TestBodyNormalizer:
    """
    What: BodyNormalizerクラスの単体テスト
    Why: 正規化処理の正確性保証
    Design Decision: pytest標準準拠、sample_landmarks.json使用（ADR-005）

    CRITICAL: 全テストはsample_landmarks.jsonを使用（実データ検証）
    """

    @pytest.fixture
    def normalizer(self):
        """
        What: BodyNormalizerインスタンス生成
        Why: 各テストで再利用
        Design Decision: pytest fixture使用（ADR-005）
        """
        return BodyNormalizer()

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

    def test_calculate_shoulder_width(self, normalizer, sample_landmarks):
        """
        What: 肩幅計算テスト
        Why: shoulder_width計算の正確性検証
        Design Decision: 実データで検証、landmarks 11-12間距離（ADR-003）

        CRITICAL: 0より大きい値、NaNでないこと
        """
        # PHASE CORE LOGIC: 最初のフレームで肩幅計算
        first_frame_landmarks = sample_landmarks[0]['landmarks']
        shoulder_width = normalizer.calculate_shoulder_width(first_frame_landmarks)

        # 検証
        assert shoulder_width is not None, "肩幅がNoneです"
        assert not np.isnan(shoulder_width), "肩幅がNaNです"
        assert shoulder_width > 0, f"肩幅が0以下です: {shoulder_width}"
        assert shoulder_width < 1.0, f"肩幅が1.0以上です（正規化済み座標のため異常値）: {shoulder_width}"

    def test_calculate_pelvis_width(self, normalizer, sample_landmarks):
        """
        What: 骨盤幅計算テスト
        Why: pelvis_width計算の正確性検証
        Design Decision: 実データで検証、landmarks 23-24間距離（ADR-003）

        CRITICAL: 0より大きい値、NaNでないこと
        """
        # PHASE CORE LOGIC: 最初のフレームで骨盤幅計算
        first_frame_landmarks = sample_landmarks[0]['landmarks']
        pelvis_width = normalizer.calculate_pelvis_width(first_frame_landmarks)

        # 検証
        assert pelvis_width is not None, "骨盤幅がNoneです"
        assert not np.isnan(pelvis_width), "骨盤幅がNaNです"
        assert pelvis_width > 0, f"骨盤幅が0以下です: {pelvis_width}"
        assert pelvis_width < 1.0, f"骨盤幅が1.0以上です（正規化済み座標のため異常値）: {pelvis_width}"

    def test_calculate_leg_length(self, normalizer, sample_landmarks):
        """
        What: 下肢長計算テスト
        Why: leg_length計算の正確性検証
        Design Decision: 実データで検証、hip to ankle平均距離（ADR-003）

        CRITICAL: 0より大きい値、NaNでないこと
        """
        # PHASE CORE LOGIC: 最初のフレームで下肢長計算
        first_frame_landmarks = sample_landmarks[0]['landmarks']
        leg_length = normalizer.calculate_leg_length(first_frame_landmarks)

        # 検証
        assert leg_length is not None, "下肢長がNoneです"
        assert not np.isnan(leg_length), "下肢長がNaNです"
        assert leg_length > 0, f"下肢長が0以下です: {leg_length}"
        assert leg_length < 2.0, f"下肢長が2.0以上です（正規化済み座標のため異常値）: {leg_length}"

    def test_calculate_base_width(self, normalizer, sample_landmarks):
        """
        What: 基準幅計算テスト
        Why: base_width計算の正確性検証
        Design Decision: max(shoulder_width, pelvis_width)（ADR-003）

        CRITICAL: shoulder_widthまたはpelvis_widthの大きい方と一致
        """
        # PHASE CORE LOGIC: 最初のフレームで基準幅計算
        first_frame_landmarks = sample_landmarks[0]['landmarks']
        base_width = normalizer.calculate_base_width(first_frame_landmarks)
        shoulder_width = normalizer.calculate_shoulder_width(first_frame_landmarks)
        pelvis_width = normalizer.calculate_pelvis_width(first_frame_landmarks)

        # 検証
        assert base_width is not None, "基準幅がNoneです"
        assert not np.isnan(base_width), "基準幅がNaNです"
        assert base_width > 0, f"基準幅が0以下です: {base_width}"

        # CRITICAL: max(shoulder_width, pelvis_width)と一致すること
        expected_base_width = max(shoulder_width, pelvis_width)
        assert abs(base_width - expected_base_width) < 1e-6, \
            f"基準幅が期待値と一致しません: {base_width} != {expected_base_width}"

    def test_normalize_frame_data(self, normalizer, sample_landmarks):
        """
        What: 1フレーム正規化テスト
        Why: normalize_frame_data()の正確性検証
        Design Decision: 4種の基準値を一括返却（ADR-003）

        CRITICAL: 辞書キー4つ（shoulder_width, pelvis_width, leg_length, base_width）
        """
        # PHASE CORE LOGIC: 最初のフレームで正規化基準計算
        first_frame_landmarks = sample_landmarks[0]['landmarks']
        norm_values = normalizer.normalize_frame_data(first_frame_landmarks)

        # 検証: 辞書キー確認
        assert 'shoulder_width' in norm_values, "shoulder_widthキーが存在しません"
        assert 'pelvis_width' in norm_values, "pelvis_widthキーが存在しません"
        assert 'leg_length' in norm_values, "leg_lengthキーが存在しません"
        assert 'base_width' in norm_values, "base_widthキーが存在しません"

        # 検証: 値の妥当性
        for key, value in norm_values.items():
            assert value is not None, f"{key}がNoneです"
            assert not np.isnan(value), f"{key}がNaNです"
            assert value > 0, f"{key}が0以下です: {value}"

    def test_normalize_landmarks_sequence(self, normalizer, sample_landmarks):
        """
        What: 全フレーム正規化テスト
        Why: normalize_landmarks_sequence()の正確性検証
        Design Decision: 代表値は中央値使用（外れ値耐性）（ADR-003）

        CRITICAL: 代表値はNaN除外後の中央値、フレーム数と一致
        """
        # PHASE CORE LOGIC: 全フレーム正規化（最初の100フレームのみテスト）
        test_data = sample_landmarks[:100]
        rep_values, frame_values = normalizer.normalize_landmarks_sequence(test_data)

        # 検証: 代表値の存在
        assert 'shoulder_width' in rep_values, "代表値にshoulder_widthが存在しません"
        assert 'pelvis_width' in rep_values, "代表値にpelvis_widthが存在しません"
        assert 'leg_length' in rep_values, "代表値にleg_lengthが存在しません"
        assert 'base_width' in rep_values, "代表値にbase_widthが存在しません"

        # 検証: 代表値の妥当性
        for key, value in rep_values.items():
            if not np.isnan(value):
                assert value > 0, f"代表値{key}が0以下です: {value}"

        # 検証: フレーム別値の数
        assert len(frame_values) == len(test_data), \
            f"フレーム別値の数が一致しません: {len(frame_values)} != {len(test_data)}"

        # CRITICAL: 代表値が中央値と一致することを検証
        for key in ['shoulder_width', 'pelvis_width', 'leg_length', 'base_width']:
            valid_values = [f[key] for f in frame_values if f[key] is not None]
            if valid_values:
                expected_median = float(np.median(valid_values))
                actual_value = rep_values[key]
                assert abs(actual_value - expected_median) < 1e-6, \
                    f"代表値{key}が中央値と一致しません: {actual_value} != {expected_median}"

    def test_normalize_value_normal(self):
        """
        What: 正規化ヘルパー関数テスト（正常系）
        Why: normalize_value()の正確性検証
        Design Decision: value / reference の単純比（ADR-003）

        CRITICAL: 単純な除算結果と一致
        """
        # PHASE CORE LOGIC: 正常系テスト
        value = 1.5
        reference = 1.0
        result = normalize_value(value, reference)

        # 検証
        assert result is not None, "結果がNoneです"
        assert result == 1.5, f"正規化値が期待値と一致しません: {result} != 1.5"

    def test_normalize_value_zero_reference(self):
        """
        What: 正規化ヘルパー関数テスト（ゼロ除算）
        Why: reference=0の場合のNone返却確認
        Design Decision: ゼロ除算時はNone返却（ADR-003）

        CRITICAL: reference=0の場合はNone返却（例外投げない）
        """
        # PHASE CORE LOGIC: ゼロ除算テスト
        value = 1.5
        reference = 0.0
        result = normalize_value(value, reference)

        # 検証
        assert result is None, f"reference=0でNoneを返すべきですが: {result}"

    def test_normalize_value_none_reference(self):
        """
        What: 正規化ヘルパー関数テスト（None入力）
        Why: reference=Noneの場合のNone返却確認
        Design Decision: None入力時はNone返却（ADR-003）

        CRITICAL: reference=NoneまたはNaNの場合はNone返却
        """
        # PHASE CORE LOGIC: None入力テスト
        value = 1.5
        reference = None
        result = normalize_value(value, reference)

        # 検証
        assert result is None, f"reference=NoneでNoneを返すべきですが: {result}"

        # NaN入力テスト
        reference_nan = np.nan
        result_nan = normalize_value(value, reference_nan)
        assert result_nan is None, f"reference=NaNでNoneを返すべきですが: {result_nan}"

    def test_nan_handling(self, normalizer):
        """
        What: NaN処理テスト
        Why: NaN保持ルール準拠確認
        Design Decision: 計算不可時はNone返却（ADR-003）

        CRITICAL: ランドマーク不足時はNone返却（例外投げない）
        """
        # PHASE CORE LOGIC: ランドマーク不足データ作成
        insufficient_landmarks = [
            {'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}
            for _ in range(10)  # 33個未満
        ]

        # 検証: 計算不可時はNone返却
        shoulder_width = normalizer.calculate_shoulder_width(insufficient_landmarks)
        assert shoulder_width is None, f"ランドマーク不足時はNoneを返すべきですが: {shoulder_width}"

        pelvis_width = normalizer.calculate_pelvis_width(insufficient_landmarks)
        assert pelvis_width is None, f"ランドマーク不足時はNoneを返すべきですが: {pelvis_width}"

        leg_length = normalizer.calculate_leg_length(insufficient_landmarks)
        assert leg_length is None, f"ランドマーク不足時はNoneを返すべきですが: {leg_length}"

        base_width = normalizer.calculate_base_width(insufficient_landmarks)
        assert base_width is None, f"ランドマーク不足時はNoneを返すべきですが: {base_width}"

    def test_real_data_integration(self, normalizer, sample_landmarks):
        """
        What: 実データ統合テスト
        Why: sample_landmarks.json全体での動作確認
        Design Decision: 全フレーム処理（ADR-005）

        CRITICAL: 全フレームで正規化成功、代表値が妥当な範囲
        """
        # PHASE CORE LOGIC: 全フレーム正規化
        rep_values, frame_values = normalizer.normalize_landmarks_sequence(sample_landmarks)

        # 検証: 代表値が妥当な範囲
        assert 0.1 < rep_values['shoulder_width'] < 0.5, \
            f"肩幅代表値が異常: {rep_values['shoulder_width']}"
        assert 0.1 < rep_values['pelvis_width'] < 0.5, \
            f"骨盤幅代表値が異常: {rep_values['pelvis_width']}"
        assert 0.3 < rep_values['leg_length'] < 1.5, \
            f"下肢長代表値が異常: {rep_values['leg_length']}"
        assert 0.1 < rep_values['base_width'] < 0.5, \
            f"基準幅代表値が異常: {rep_values['base_width']}"

        # 検証: フレーム数一致
        assert len(frame_values) == len(sample_landmarks), \
            f"フレーム数不一致: {len(frame_values)} != {len(sample_landmarks)}"

        # 検証: 全フレームでNoneでない値が存在
        non_none_counts = {
            'shoulder_width': sum(1 for f in frame_values if f['shoulder_width'] is not None),
            'pelvis_width': sum(1 for f in frame_values if f['pelvis_width'] is not None),
            'leg_length': sum(1 for f in frame_values if f['leg_length'] is not None),
            'base_width': sum(1 for f in frame_values if f['base_width'] is not None)
        }

        for key, count in non_none_counts.items():
            assert count > 0, f"{key}が全フレームでNoneです"
            assert count / len(frame_values) > 0.8, \
                f"{key}のNone率が高すぎます: {1 - count/len(frame_values):.1%}"


if __name__ == '__main__':
    """
    What: pytest実行
    Why: python -m pytest tests/test_normalizer.py で実行
    Design Decision: pytest標準準拠（ADR-005）

    CRITICAL: モジュールとしてインポート時は実行されない
    """
    pytest.main([__file__, '-v'])
