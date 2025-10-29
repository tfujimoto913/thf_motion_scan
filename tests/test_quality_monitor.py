"""
Purpose: quality_monitor.pyの単体テスト
Responsibility: 品質モニタリング機能の検証（Phase 1実装）
Dependencies: pytest, quality_monitor.py, sample_landmarks.json, config.json
Created: 2025-10-30 by Claude
Decision Log: Phase 1 - Motion Scan Quality Monitoring

CRITICAL: MediaPipe visibility取得、品質スコア計算、quality_log.json出力検証必須
"""
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
import sys

# CRITICAL: processing/モジュールをインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from processing.quality_monitor import QualityMonitor


class TestQualityMonitor:
    """
    What: QualityMonitorクラスの単体テスト
    Why: 品質モニタリング機能の正確性保証
    Design Decision: pytest標準準拠、sample_landmarks.json使用、TDD

    CRITICAL: 既存のHealthCheckerに影響を与えないこと
    """

    @pytest.fixture
    def quality_monitor(self):
        """
        What: QualityMonitorインスタンス生成
        Why: 各テストで再利用
        Design Decision: config.json使用
        """
        return QualityMonitor('config.json')

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

    def test_calculate_quality_metrics_basic(self, quality_monitor, sample_landmarks):
        """
        What: 品質メトリクス計算の基本テスト
        Why: 必須フィールドが全て計算されることを確認
        Design Decision: sample_landmarks.jsonで実データテスト

        CRITICAL: landmark_visibility_avg, frame_completeness, quality_score必須
        """
        # PHASE CORE LOGIC: 品質メトリクス計算
        metrics = quality_monitor.calculate_quality_metrics(sample_landmarks)

        # 検証: 必須フィールド存在
        assert 'landmark_visibility_avg' in metrics, "landmark_visibility_avgが存在しません"
        assert 'frame_completeness' in metrics, "frame_completenessが存在しません"
        assert 'quality_score' in metrics, "quality_scoreが存在しません"
        assert 'warnings' in metrics, "warningsが存在しません"
        assert 'recommend_retake' in metrics, "recommend_retakeが存在しません"

        # 検証: 値の型と範囲
        assert isinstance(metrics['landmark_visibility_avg'], float), \
            "landmark_visibility_avgはfloat型である必要があります"
        assert 0.0 <= metrics['landmark_visibility_avg'] <= 1.0, \
            f"landmark_visibility_avgは0.0-1.0の範囲である必要があります: {metrics['landmark_visibility_avg']}"

        assert isinstance(metrics['frame_completeness'], float), \
            "frame_completenessはfloat型である必要があります"
        assert 0.0 <= metrics['frame_completeness'] <= 1.0, \
            f"frame_completenessは0.0-1.0の範囲である必要があります: {metrics['frame_completeness']}"

        assert isinstance(metrics['quality_score'], int), \
            "quality_scoreはint型である必要があります"
        assert 0 <= metrics['quality_score'] <= 100, \
            f"quality_scoreは0-100の範囲である必要があります: {metrics['quality_score']}"

        assert isinstance(metrics['warnings'], list), \
            "warningsはlist型である必要があります"

        assert isinstance(metrics['recommend_retake'], bool), \
            "recommend_retakeはbool型である必要があります"

    def test_quality_score_calculation(self, quality_monitor):
        """
        What: 品質スコア計算式の検証
        Why: 計算式が正しく実装されていることを確認
        Design Decision: 完璧なデータで100点、最低品質で0点

        CRITICAL: quality_score = (landmark_visibility_avg * 40 + frame_completeness * 60) * 100
        """
        # PHASE CORE LOGIC: 完璧なデータ（100点）
        perfect_data = [
            {
                'frame': 0,
                'landmarks': [{'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}] * 33
            }
        ] * 100

        metrics = quality_monitor.calculate_quality_metrics(perfect_data)
        assert metrics['quality_score'] == 100, \
            f"完璧なデータでは100点である必要があります: {metrics['quality_score']}"
        assert metrics['recommend_retake'] is False, \
            "100点では再撮影推奨されないはずです"

        # PHASE CORE LOGIC: 低品質データ（70点未満）
        low_quality_data = [
            {
                'frame': 0,
                'landmarks': [{'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.3}] * 33
            }
        ] * 50  # フレーム欠損50%

        metrics = quality_monitor.calculate_quality_metrics(low_quality_data, total_frames=100)
        assert metrics['quality_score'] < 70, \
            f"低品質データでは70点未満である必要があります: {metrics['quality_score']}"
        assert metrics['recommend_retake'] is True, \
            "70点未満では再撮影推奨されるはずです"

    def test_warnings_generation(self, quality_monitor):
        """
        What: 警告生成ロジックの検証
        Why: 閾値に基づいて適切に警告が生成されることを確認
        Design Decision: config.json閾値準拠

        CRITICAL: visibility < 0.5, frame_completeness < 0.9で警告
        """
        # PHASE CORE LOGIC: 低visibilityデータ
        low_visibility_data = [
            {
                'frame': i,
                'landmarks': [{'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.3}] * 33
            }
            for i in range(100)
        ]

        metrics = quality_monitor.calculate_quality_metrics(low_visibility_data)
        assert len(metrics['warnings']) > 0, "低visibilityデータでは警告が生成されるはずです"
        assert any('visibility' in w.lower() for w in metrics['warnings']), \
            "visibility関連の警告が含まれるはずです"

        # PHASE CORE LOGIC: フレーム欠損データ
        frame_loss_data = [
            {
                'frame': i,
                'landmarks': [{'x': 0.5, 'y': 0.5, 'z': 0.0, 'visibility': 0.9}] * 33
            }
            for i in range(80)  # 20%欠損
        ]

        metrics = quality_monitor.calculate_quality_metrics(frame_loss_data, total_frames=100)
        assert len(metrics['warnings']) > 0, "フレーム欠損データでは警告が生成されるはずです"
        assert any('frame' in w.lower() for w in metrics['warnings']), \
            "フレーム欠損関連の警告が含まれるはずです"

    def test_save_quality_log(self, quality_monitor, sample_landmarks):
        """
        What: quality_log.json保存機能の検証
        Why: 正しい形式でJSONファイルが生成されることを確認
        Design Decision: 提案されたquality_log.json構造準拠

        CRITICAL: measurement_id, timestamp, quality_metrics必須
        """
        # PHASE CORE LOGIC: quality_log.json生成
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / 'quality_log.json'
            measurement_id = 'test-measurement-001'

            quality_monitor.save_quality_log(
                sample_landmarks,
                output_path=str(output_path),
                measurement_id=measurement_id
            )

            # 検証: ファイル生成確認
            assert output_path.exists(), "quality_log.jsonが生成されていません"

            # 検証: JSON読み込み
            with open(output_path, 'r') as f:
                log_data = json.load(f)

            # 検証: 必須フィールド
            assert 'measurement_id' in log_data, "measurement_idが存在しません"
            assert log_data['measurement_id'] == measurement_id, \
                f"measurement_idが一致しません: {log_data['measurement_id']}"

            assert 'timestamp' in log_data, "timestampが存在しません"
            # ISO 8601形式確認
            datetime.fromisoformat(log_data['timestamp'].replace('Z', '+00:00'))

            assert 'quality_metrics' in log_data, "quality_metricsが存在しません"

            metrics = log_data['quality_metrics']
            assert 'landmark_visibility_avg' in metrics
            assert 'frame_completeness' in metrics
            assert 'quality_score' in metrics
            assert 'warnings' in metrics
            assert 'recommend_retake' in metrics

    def test_empty_landmarks(self, quality_monitor):
        """
        What: 空ランドマークデータのエッジケーステスト
        Why: データがない場合のエラーハンドリング確認
        Design Decision: 空データではquality_score=0, recommend_retake=True

        CRITICAL: エラーではなく適切なデフォルト値を返す
        """
        # PHASE CORE LOGIC: 空データ
        metrics = quality_monitor.calculate_quality_metrics([])

        assert metrics['quality_score'] == 0, "空データではquality_score=0であるべき"
        assert metrics['recommend_retake'] is True, "空データでは再撮影推奨されるべき"
        assert len(metrics['warnings']) > 0, "空データでは警告が生成されるべき"
