"""
Purpose: PNG可視化エクスポーター
Responsibility: 評価結果をグラフ画像（PNG）として出力
Dependencies: matplotlib, base_exporter.py
Created: 2025-10-25 by Claude
Decision Log: ADR-011（Phase 2: 出力物生成機能）

CRITICAL: matplotlib依存、requirements.txtに追加必須
"""
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # GUIバックエンド不要の設定
from typing import Dict, Any, List
from pathlib import Path
from .base_exporter import BaseExporter


class PNGPlotter(BaseExporter):
    """
    What: PNG可視化エクスポータークラス
    Why: 評価結果を視覚的に表示し、理解を容易化
    Design Decision: matplotlib を使用してバーグラフ生成（ADR-011）

    CRITICAL: matplotlib >= 3.7.0 が必要
    """

    def export(self,
               result: Dict[str, Any],
               output_filename: str,
               **kwargs) -> str:
        """
        What: 評価結果をPNG画像で出力
        Why: グラフで視覚的に評価結果を表示
        Design Decision: バーグラフで各指標のスコアを表示

        Args:
            result: 評価結果辞書
            output_filename: 出力ファイル名（拡張子除く）
            **kwargs: 追加オプション
                - dpi: 解像度（デフォルト 100）
                - figsize: 図のサイズ（デフォルト (10, 6)）

        Returns:
            str: 出力ファイルの絶対パス

        CRITICAL: result が不正な場合は ValueError を発生させる
        """
        # PHASE CORE LOGIC: 妥当性検証
        if not self.validate_result(result):
            raise ValueError("Invalid result format: missing 'score' or 'details'")

        # PHASE CORE LOGIC: グラフ作成
        dpi = kwargs.get('dpi', 100)
        figsize = kwargs.get('figsize', (10, 6))

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

        # PHASE CORE LOGIC: データ抽出
        test_type = result.get('test_type', 'Unknown Test')
        total_score = result.get('score', 0)
        evaluation = result.get('evaluation', {})

        # PHASE CORE LOGIC: バーグラフ描画
        self._plot_bar_chart(ax, test_type, total_score, evaluation)

        # PHASE CORE LOGIC: PNG 出力
        output_path = self.get_output_path(output_filename, ".png")
        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        plt.close(fig)

        return str(output_path.absolute())

    def _plot_bar_chart(self,
                        ax: plt.Axes,
                        test_type: str,
                        total_score: int,
                        evaluation: Dict[str, Any]) -> None:
        """
        What: バーグラフ描画
        Why: 各評価指標のスコアを視覚化
        Design Decision: 横棒グラフ、0-3点スケール

        Args:
            ax: matplotlib Axes オブジェクト
            test_type: テスト種別名
            total_score: 総合スコア
            evaluation: 評価指標詳細

        CRITICAL: スコアは 0-3 範囲に制限
        """
        # PHASE CORE LOGIC: 評価指標抽出
        labels = []
        scores = []

        # 総合スコア追加
        labels.append('Total Score')
        scores.append(total_score)

        # 各評価指標のスコア追加
        for key, value in evaluation.items():
            if isinstance(value, dict) and 'score' in value:
                # キー名を整形（例: pelvic_stability → Pelvic Stability）
                label = key.replace('_', ' ').title()
                labels.append(label)
                scores.append(value['score'])

        # PHASE CORE LOGIC: 横棒グラフ描画
        y_pos = range(len(labels))
        colors = ['#4CAF50' if s == 3 else '#FFC107' if s == 2 else '#FF9800' if s == 1 else '#F44336'
                  for s in scores]

        ax.barh(y_pos, scores, color=colors, edgecolor='black', linewidth=1.2)

        # PHASE CORE LOGIC: ラベル設定
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)
        ax.set_xlabel('Score', fontsize=12, fontweight='bold')
        ax.set_title(f'{test_type} - Evaluation Results', fontsize=14, fontweight='bold')
        ax.set_xlim(0, 3)

        # グリッド表示
        ax.grid(axis='x', linestyle='--', alpha=0.7)

        # スコア数値表示
        for i, (label, score) in enumerate(zip(labels, scores)):
            ax.text(score + 0.1, i, f'{score}/3', va='center', fontsize=10, fontweight='bold')

    def export_batch(self,
                     results: List[Dict[str, Any]],
                     output_filename: str,
                     **kwargs) -> str:
        """
        What: 複数評価結果を一括PNG出力
        Why: 複数動画の評価結果を1つのグラフに統合
        Design Decision: 各動画の総合スコアを比較グラフ化

        Args:
            results: 評価結果リスト
            output_filename: 出力ファイル名（拡張子除く）
            **kwargs: 追加オプション

        Returns:
            str: 出力ファイルの絶対パス

        CRITICAL: 空リストの場合は空グラフを出力
        """
        # PHASE CORE LOGIC: グラフ作成
        dpi = kwargs.get('dpi', 100)
        figsize = kwargs.get('figsize', (12, 6))

        fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

        # PHASE CORE LOGIC: データ抽出
        labels = []
        scores = []

        for i, result in enumerate(results):
            if self.validate_result(result):
                video_path = result.get('video_path', f'Video {i+1}')
                # ファイル名のみ抽出
                video_name = Path(video_path).name if video_path else f'Video {i+1}'
                labels.append(video_name)
                scores.append(result.get('score', 0))

        # PHASE CORE LOGIC: 比較グラフ描画
        if labels:
            x_pos = range(len(labels))
            colors = ['#4CAF50' if s == 3 else '#FFC107' if s == 2 else '#FF9800' if s == 1 else '#F44336'
                      for s in scores]

            ax.bar(x_pos, scores, color=colors, edgecolor='black', linewidth=1.2)

            # ラベル設定
            ax.set_xticks(x_pos)
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.set_ylabel('Score', fontsize=12, fontweight='bold')
            ax.set_title('Batch Evaluation Results Comparison', fontsize=14, fontweight='bold')
            ax.set_ylim(0, 3)

            # グリッド表示
            ax.grid(axis='y', linestyle='--', alpha=0.7)

            # スコア数値表示
            for i, score in enumerate(scores):
                ax.text(i, score + 0.1, f'{score}/3', ha='center', fontsize=10, fontweight='bold')
        else:
            # 空グラフ
            ax.text(0.5, 0.5, 'No valid results', ha='center', va='center',
                    transform=ax.transAxes, fontsize=16)

        # PHASE CORE LOGIC: PNG 出力
        output_path = self.get_output_path(output_filename, ".png")
        plt.tight_layout()
        plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
        plt.close(fig)

        return str(output_path.absolute())
