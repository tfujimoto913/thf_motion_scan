"""
Worker のユニットテスト
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from processing.worker import VideoProcessingWorker, process_video
from processing.evaluators.single_leg_squat import SingleLegSquatEvaluator


class TestVideoProcessingWorker:
    """VideoProcessingWorkerのテストクラス"""

    @pytest.fixture
    def worker(self):
        """Workerインスタンスを返すフィクスチャ"""
        return VideoProcessingWorker()

    @pytest.fixture
    def mock_landmarks_data(self):
        """モックランドマークデータを返すフィクスチャ"""
        landmarks = []
        # 33個のランドマークを作成（MediaPipeの標準）
        for i in range(33):
            landmarks.append({
                'x': 0.5,
                'y': 0.5 + i * 0.01,  # 各ポイントで少しずつY座標を変える
                'z': 0.0,
                'visibility': 0.9
            })

        return [
            {
                'frame': i,
                'timestamp': i * 0.033,  # 30fps想定
                'landmarks': landmarks
            }
            for i in range(10)  # 10フレーム分
        ]

    @pytest.fixture
    def mock_extraction_result(self, mock_landmarks_data):
        """モック抽出結果を返すフィクスチャ"""
        return {
            'landmarks': mock_landmarks_data,
            'fps': 30.0,
            'frame_count': 100,
            'duration': 3.33,
            'detected_frames': len(mock_landmarks_data)
        }

    def test_worker_initialization(self, worker):
        """Workerが正しく初期化されることを確認"""
        assert worker.pose_extractor is not None
        assert 'single_leg_squat' in worker.evaluators
        assert isinstance(worker.evaluators['single_leg_squat'], SingleLegSquatEvaluator)

    def test_process_video_file_not_found(self, worker):
        """存在しない動画ファイルでエラーが発生することを確認"""
        with pytest.raises(FileNotFoundError):
            worker.process_video('non_existent_video.mp4')

    def test_process_video_invalid_test_type(self, worker, tmp_path):
        """サポートされていないテストタイプでエラーが発生することを確認"""
        # ダミー動画ファイルを作成
        dummy_video = tmp_path / "dummy.mp4"
        dummy_video.write_text("dummy")

        with pytest.raises(ValueError, match="サポートされていないテストタイプ"):
            worker.process_video(str(dummy_video), test_type='invalid_test')

    @patch('processing.worker.PoseExtractor')
    def test_process_video_success(self, mock_pose_extractor_class,
                                   worker, mock_extraction_result, tmp_path):
        """正常に動画処理が完了することを確認"""
        # ダミー動画ファイルを作成
        dummy_video = tmp_path / "dummy.mp4"
        dummy_video.write_text("dummy")

        # PoseExtractorのモック設定
        mock_extractor = MagicMock()
        mock_extractor.extract_landmarks.return_value = mock_extraction_result
        worker.pose_extractor = mock_extractor

        # 実行
        result = worker.process_video(str(dummy_video))

        # 検証
        assert result['video_path'] == str(dummy_video)
        assert result['test_type'] == 'single_leg_squat'
        assert 'score' in result
        assert 'evaluation' in result
        assert 'video_info' in result
        assert 'processed_at' in result
        assert result['score'] >= 0 and result['score'] <= 3

    @patch('processing.worker.PoseExtractor')
    def test_process_video_with_output(self, mock_pose_extractor_class,
                                       worker, mock_extraction_result, tmp_path):
        """結果がファイルに保存されることを確認"""
        # ダミー動画ファイルを作成
        dummy_video = tmp_path / "dummy.mp4"
        dummy_video.write_text("dummy")

        output_dir = tmp_path / "output"

        # PoseExtractorのモック設定
        mock_extractor = MagicMock()
        mock_extractor.extract_landmarks.return_value = mock_extraction_result
        worker.pose_extractor = mock_extractor

        # 実行
        result = worker.process_video(str(dummy_video), output_dir=str(output_dir))

        # 検証
        assert 'output_file' in result
        assert Path(result['output_file']).exists()

        # 保存されたファイルの内容を確認
        with open(result['output_file'], 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
            assert saved_data['score'] == result['score']
            assert saved_data['test_type'] == 'single_leg_squat'

    def test_get_summary(self, worker, mock_extraction_result, tmp_path):
        """サマリーが正しく生成されることを確認"""
        # ダミー動画ファイルを作成
        dummy_video = tmp_path / "dummy.mp4"
        dummy_video.write_text("dummy")

        # PoseExtractorのモック設定
        mock_extractor = MagicMock()
        mock_extractor.extract_landmarks.return_value = mock_extraction_result
        worker.pose_extractor = mock_extractor

        # 処理を実行
        result = worker.process_video(str(dummy_video))

        # サマリーを生成
        summary = worker.get_summary(result)

        # 検証
        assert isinstance(summary, str)
        assert 'スコア' in summary
        assert 'single_leg_squat' in summary
        assert str(result['score']) in summary

    @patch('processing.worker.VideoProcessingWorker')
    def test_process_video_function(self, mock_worker_class, tmp_path):
        """便利関数process_videoが正しく動作することを確認"""
        # ダミー動画ファイルを作成
        dummy_video = tmp_path / "dummy.mp4"
        dummy_video.write_text("dummy")

        # Workerのモック設定
        mock_worker = MagicMock()
        mock_result = {
            'video_path': str(dummy_video),
            'test_type': 'single_leg_squat',
            'score': 2
        }
        mock_worker.process_video.return_value = mock_result
        mock_worker_class.return_value = mock_worker

        # 実行
        result = process_video(str(dummy_video))

        # 検証
        assert result == mock_result
        mock_worker.process_video.assert_called_once_with(
            str(dummy_video), 'single_leg_squat', None
        )


class TestSingleLegSquatEvaluator:
    """SingleLegSquatEvaluatorの基本テスト"""

    @pytest.fixture
    def evaluator(self):
        """Evaluatorインスタンスを返すフィクスチャ"""
        return SingleLegSquatEvaluator()

    def test_evaluator_initialization(self, evaluator):
        """Evaluatorが正しく初期化されることを確認"""
        # CRITICAL: config.json閾値参照に変更（ADR-002）
        assert evaluator.config is not None
        assert evaluator.thresholds is not None
        assert 'knee_flexion_min' in evaluator.thresholds

    def test_evaluate_empty_data(self, evaluator):
        """空のデータで評価した場合"""
        result = evaluator.evaluate([])
        assert result['score'] == 0
        assert '姿勢が検出できませんでした' in result['details']

    def test_evaluate_with_perfect_form(self, evaluator):
        """理想的なフォームのデータで評価"""
        # 完璧な骨盤水平性と膝角度差を持つデータを作成
        landmarks = []
        for i in range(33):
            landmarks.append({
                'x': 0.5,
                'y': 0.5,  # 全て同じY座標
                'z': 0.0,
                'visibility': 0.9
            })

        # Hip, Knee, Ankleの座標を調整して理想的な角度差を作る
        # 左脚（軸脚）: より曲がった状態
        landmarks[23] = {'x': 0.4, 'y': 0.5, 'z': 0.0, 'visibility': 0.9}  # LEFT_HIP
        landmarks[25] = {'x': 0.4, 'y': 0.7, 'z': 0.0, 'visibility': 0.9}  # LEFT_KNEE
        landmarks[27] = {'x': 0.4, 'y': 0.9, 'z': 0.0, 'visibility': 0.9}  # LEFT_ANKLE

        # 右脚（遊脚）: より伸びた状態
        landmarks[24] = {'x': 0.6, 'y': 0.5, 'z': 0.0, 'visibility': 0.9}  # RIGHT_HIP
        landmarks[26] = {'x': 0.6, 'y': 0.65, 'z': 0.0, 'visibility': 0.9}  # RIGHT_KNEE
        landmarks[28] = {'x': 0.6, 'y': 0.8, 'z': 0.0, 'visibility': 0.9}  # RIGHT_ANKLE

        landmarks_data = [
            {
                'frame': i,
                'timestamp': i * 0.033,
                'landmarks': landmarks
            }
            for i in range(10)
        ]

        result = evaluator.evaluate(landmarks_data)

        # スコアが0-3の範囲内であることを確認
        assert 0 <= result['score'] <= 3
        assert 'pelvic_stability' in result
        assert 'knee_angle_ratio' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
