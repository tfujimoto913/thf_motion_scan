"""
Purpose: CSV出力エクスポーター
Responsibility: 評価結果をCSV形式で出力
Dependencies: pandas, base_exporter.py
Created: 2025-10-25 by Claude
Decision Log: ADR-011（Phase 2: 出力物生成機能）

CRITICAL: pandas依存、requirements.txtに追加必須
"""
import pandas as pd
from typing import Dict, Any
from pathlib import Path
from .base_exporter import BaseExporter


class CSVExporter(BaseExporter):
    """
    What: CSV出力エクスポータークラス
    Why: 評価結果を表形式で出力し、Excelでの分析を容易化
    Design Decision: pandas DataFrame を使用して CSV 出力（ADR-011）

    CRITICAL: pandas >= 2.0.0 が必要
    """

    def export(self,
               result: Dict[str, Any],
               output_filename: str,
               **kwargs) -> str:
        """
        What: 評価結果を CSV 形式で出力
        Why: 表計算ソフトでの分析・可視化を可能にする
        Design Decision: フラット化した辞書を DataFrame に変換

        Args:
            result: 評価結果辞書
                {
                    'test_type': str,
                    'score': int (0-3),
                    'details': str,
                    'video_path': str,
                    'health_check': Dict,
                    'evaluation': Dict (評価指標ごとの詳細)
                }
            output_filename: 出力ファイル名（拡張子除く）
            **kwargs: 追加オプション
                - include_health_check: bool (デフォルト True)
                - include_evaluation_details: bool (デフォルト True)

        Returns:
            str: 出力ファイルの絶対パス

        CRITICAL: result が不正な場合は ValueError を発生させる
        """
        # PHASE CORE LOGIC: 妥当性検証
        if not self.validate_result(result):
            raise ValueError("Invalid result format: missing 'score' or 'details'")

        # PHASE CORE LOGIC: データフラット化
        csv_data = self._flatten_result(result, **kwargs)

        # PHASE CORE LOGIC: DataFrame 作成
        df = pd.DataFrame([csv_data])

        # PHASE CORE LOGIC: CSV 出力
        output_path = self.get_output_path(output_filename, ".csv")
        df.to_csv(output_path, index=False, encoding='utf-8-sig')

        return str(output_path.absolute())

    def _flatten_result(self,
                        result: Dict[str, Any],
                        include_health_check: bool = True,
                        include_evaluation_details: bool = True) -> Dict[str, Any]:
        """
        What: 評価結果をフラット化
        Why: CSV は階層構造を扱えないため、1階層に変換
        Design Decision: ネストした辞書をドット記法でフラット化（例: evaluation.pelvic_stability.score）

        Args:
            result: 評価結果辞書
            include_health_check: health_check情報を含めるか
            include_evaluation_details: 評価指標詳細を含めるか

        Returns:
            Dict[str, Any]: フラット化された辞書

        CRITICAL: NaN値は空文字列に変換（CSV互換性）
        """
        # PHASE CORE LOGIC: 基本情報抽出
        flattened = {
            'test_type': result.get('test_type', ''),
            'score': result.get('score', 0),
            'details': result.get('details', ''),
            'video_path': result.get('video_path', '')
        }

        # PHASE CORE LOGIC: health_check情報追加
        if include_health_check and 'health_check' in result:
            hc = result['health_check']
            flattened['health_check_quality'] = hc.get('quality', '')
            flattened['health_check_warnings'] = ', '.join(hc.get('warnings', []))

        # PHASE CORE LOGIC: 評価指標詳細追加
        if include_evaluation_details and 'evaluation' in result:
            eval_data = result['evaluation']
            for key, value in eval_data.items():
                if isinstance(value, dict):
                    # ネストした辞書をフラット化
                    for sub_key, sub_value in value.items():
                        flattened[f'evaluation.{key}.{sub_key}'] = sub_value
                else:
                    flattened[f'evaluation.{key}'] = value

        # CRITICAL: NaN値を空文字列に変換
        for key, value in flattened.items():
            if pd.isna(value):
                flattened[key] = ''

        return flattened

    def export_batch(self,
                     results: list[Dict[str, Any]],
                     output_filename: str,
                     **kwargs) -> str:
        """
        What: 複数評価結果を一括CSV出力
        Why: 複数動画の評価結果を1つのCSVに統合
        Design Decision: 全結果をフラット化してDataFrame化

        Args:
            results: 評価結果リスト
            output_filename: 出力ファイル名（拡張子除く）
            **kwargs: 追加オプション

        Returns:
            str: 出力ファイルの絶対パス

        CRITICAL: 空リストの場合はヘッダーのみのCSVを出力
        """
        # PHASE CORE LOGIC: 空リスト処理
        if not results:
            # ヘッダーのみのCSV作成
            df = pd.DataFrame(columns=['test_type', 'score', 'details', 'video_path'])
        else:
            # PHASE CORE LOGIC: 全結果をフラット化
            flattened_results = [
                self._flatten_result(result, **kwargs)
                for result in results
                if self.validate_result(result)
            ]
            df = pd.DataFrame(flattened_results)

        # PHASE CORE LOGIC: CSV 出力
        output_path = self.get_output_path(output_filename, ".csv")
        df.to_csv(output_path, index=False, encoding='utf-8-sig')

        return str(output_path.absolute())
