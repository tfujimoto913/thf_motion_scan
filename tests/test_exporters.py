"""
Purpose: Exportersモジュールの単体テスト
Responsibility: CSV/PNG/PDFエクスポーターの動作検証
Dependencies: pytest, processing.exporters
Created: 2025-10-25 by Claude
Decision Log: ADR-011（Phase 2: 出力物生成機能）

CRITICAL: 全エクスポーターの基本機能をテスト必須
"""
import pytest
import json
import tempfile
from pathlib import Path
from processing.exporters import BaseExporter, CSVExporter, PNGPlotter, PDFReporter


# テスト用サンプルデータ
@pytest.fixture
def sample_result():
    """
    What: テスト用評価結果
    Why: 全エクスポーターで共通使用
    """
    return {
        'test_type': 'single_leg_squat',
        'score': 3,
        'details': 'Total Score: 3/3, Excellent performance',
        'video_path': 'tests/test_videos/sample.mp4',
        'evaluation': {
            'pelvic_stability': {
                'score': 3,
                'hip_height_diff': 0.01
            },
            'knee_flexion': {
                'score': 3,
                'min_angle': 85.0
            }
        },
        'health_check': {
            'quality': 'excellent',
            'warnings': []
        }
    }


@pytest.fixture
def temp_output_dir():
    """
    What: テスト用一時ディレクトリ
    Why: ファイル出力テストに使用
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestBaseExporter:
    """
    What: BaseExporter テストクラス
    Why: 基底クラスの基本機能を検証
    """

    def test_validate_result_valid(self, sample_result):
        """
        What: 正常データの検証
        Why: validate_result が True を返すことを確認
        """
        # BaseExporter は抽象クラスなので、具象クラスで検証
        exporter = CSVExporter()
        assert exporter.validate_result(sample_result) is True

    def test_validate_result_missing_score(self):
        """
        What: score欠落データの検証
        Why: validate_result が False を返すことを確認
        """
        result = {'details': 'test'}
        exporter = CSVExporter()
        assert exporter.validate_result(result) is False

    def test_validate_result_invalid_score(self):
        """
        What: 不正スコアデータの検証
        Why: スコア範囲外（0-3以外）は False を返すことを確認
        """
        result = {'score': 5, 'details': 'test'}
        exporter = CSVExporter()
        assert exporter.validate_result(result) is False

    def test_get_output_path(self, temp_output_dir):
        """
        What: 出力パス生成テスト
        Why: 正しいパスが生成されることを確認
        """
        exporter = CSVExporter(temp_output_dir)
        path = exporter.get_output_path('test_file', '.csv')
        assert path == Path(temp_output_dir) / 'test_file.csv'


class TestCSVExporter:
    """
    What: CSVExporter テストクラス
    Why: CSV出力機能を検証
    """

    def test_export_creates_csv_file(self, sample_result, temp_output_dir):
        """
        What: CSV出力テスト
        Why: CSVファイルが正常に作成されることを確認
        """
        exporter = CSVExporter(temp_output_dir)
        output_path = exporter.export(sample_result, 'test_result')

        assert Path(output_path).exists()
        assert output_path.endswith('.csv')

    def test_export_invalid_result_raises_error(self, temp_output_dir):
        """
        What: 不正データ時のエラー発生テスト
        Why: ValueError が発生することを確認
        """
        exporter = CSVExporter(temp_output_dir)
        invalid_result = {'invalid': 'data'}

        with pytest.raises(ValueError, match="Invalid result format"):
            exporter.export(invalid_result, 'test_result')

    def test_export_batch_empty_list(self, temp_output_dir):
        """
        What: 空リスト一括出力テスト
        Why: ヘッダーのみのCSVが作成されることを確認
        """
        exporter = CSVExporter(temp_output_dir)
        output_path = exporter.export_batch([], 'test_batch')

        assert Path(output_path).exists()


class TestPNGPlotter:
    """
    What: PNGPlotter テストクラス
    Why: PNG出力機能を検証
    """

    def test_export_creates_png_file(self, sample_result, temp_output_dir):
        """
        What: PNG出力テスト
        Why: PNGファイルが正常に作成されることを確認
        """
        exporter = PNGPlotter(temp_output_dir)
        output_path = exporter.export(sample_result, 'test_result')

        assert Path(output_path).exists()
        assert output_path.endswith('.png')

    def test_export_invalid_result_raises_error(self, temp_output_dir):
        """
        What: 不正データ時のエラー発生テスト
        Why: ValueError が発生することを確認
        """
        exporter = PNGPlotter(temp_output_dir)
        invalid_result = {'invalid': 'data'}

        with pytest.raises(ValueError, match="Invalid result format"):
            exporter.export(invalid_result, 'test_result')

    def test_export_batch_creates_png(self, sample_result, temp_output_dir):
        """
        What: 一括PNG出力テスト
        Why: 複数結果の比較グラフが作成されることを確認
        """
        exporter = PNGPlotter(temp_output_dir)
        results = [sample_result, sample_result]
        output_path = exporter.export_batch(results, 'test_batch')

        assert Path(output_path).exists()
        assert output_path.endswith('.png')


class TestPDFReporter:
    """
    What: PDFReporter テストクラス
    Why: PDF出力機能を検証
    """

    def test_export_creates_pdf_file(self, sample_result, temp_output_dir):
        """
        What: PDF出力テスト
        Why: PDFファイルが正常に作成されることを確認
        """
        exporter = PDFReporter(temp_output_dir)
        output_path = exporter.export(sample_result, 'test_result')

        assert Path(output_path).exists()
        assert output_path.endswith('.pdf')

    def test_export_invalid_result_raises_error(self, temp_output_dir):
        """
        What: 不正データ時のエラー発生テスト
        Why: ValueError が発生することを確認
        """
        exporter = PDFReporter(temp_output_dir)
        invalid_result = {'invalid': 'data'}

        with pytest.raises(ValueError, match="Invalid result format"):
            exporter.export(invalid_result, 'test_result')

    def test_export_with_custom_title(self, sample_result, temp_output_dir):
        """
        What: カスタムタイトルPDF出力テスト
        Why: title オプションが正常に動作することを確認
        """
        exporter = PDFReporter(temp_output_dir)
        output_path = exporter.export(
            sample_result,
            'test_result',
            title='Custom Test Report'
        )

        assert Path(output_path).exists()


class TestExportersIntegration:
    """
    What: エクスポーター統合テストクラス
    Why: 全エクスポーターの統合動作を検証
    """

    def test_all_exporters_work_together(self, sample_result, temp_output_dir):
        """
        What: 全エクスポーター同時実行テスト
        Why: CSV/PNG/PDF が同時に正常出力されることを確認
        """
        csv_exporter = CSVExporter(temp_output_dir)
        png_exporter = PNGPlotter(temp_output_dir)
        pdf_exporter = PDFReporter(temp_output_dir)

        csv_path = csv_exporter.export(sample_result, 'test_result')
        png_path = png_exporter.export(sample_result, 'test_result')
        pdf_path = pdf_exporter.export(sample_result, 'test_result')

        assert Path(csv_path).exists()
        assert Path(png_path).exists()
        assert Path(pdf_path).exists()
