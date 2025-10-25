"""
Purpose: PDFレポートエクスポーター
Responsibility: 評価結果を包括的なPDFレポートとして出力
Dependencies: reportlab, base_exporter.py
Created: 2025-10-25 by Claude
Decision Log: ADR-011（Phase 2: 出力物生成機能）

CRITICAL: reportlab依存、requirements.txtに追加必須
"""
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime
from .base_exporter import BaseExporter


class PDFReporter(BaseExporter):
    """
    What: PDFレポートエクスポータークラス
    Why: 評価結果を印刷可能な包括的レポートとして提供
    Design Decision: reportlab を使用して構造化PDFレポート生成（ADR-011）

    CRITICAL: reportlab >= 4.0.0 が必要
    """

    def __init__(self, output_dir: str = "outputs", pagesize=letter):
        """
        What: PDFレポーター初期化
        Why: ページサイズを設定可能にする
        Design Decision: デフォルトは letter サイズ（8.5" x 11"）

        Args:
            output_dir: 出力ディレクトリパス
            pagesize: ページサイズ（letter または A4）

        CRITICAL: pagesize は reportlab.lib.pagesizes のサイズを使用
        """
        super().__init__(output_dir)
        self.pagesize = pagesize
        self.styles = getSampleStyleSheet()

        # PHASE CORE LOGIC: カスタムスタイル追加
        self.styles.add(ParagraphStyle(
            name='CenterTitle',
            parent=self.styles['Heading1'],
            alignment=TA_CENTER,
            fontSize=18,
            textColor=colors.HexColor('#2E86AB'),
            spaceAfter=20
        ))
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#06A77D'),
            spaceAfter=12
        ))

    def export(self,
               result: Dict[str, Any],
               output_filename: str,
               **kwargs) -> str:
        """
        What: 評価結果をPDFレポートで出力
        Why: 印刷可能な包括的レポートを提供
        Design Decision: タイトル、サマリー、詳細評価、ヘルスチェックの4セクション構成

        Args:
            result: 評価結果辞書
            output_filename: 出力ファイル名（拡張子除く）
            **kwargs: 追加オプション
                - title: レポートタイトル（デフォルト "Motion Analysis Report"）

        Returns:
            str: 出力ファイルの絶対パス

        CRITICAL: result が不正な場合は ValueError を発生させる
        """
        # PHASE CORE LOGIC: 妥当性検証
        if not self.validate_result(result):
            raise ValueError("Invalid result format: missing 'score' or 'details'")

        # PHASE CORE LOGIC: PDF 作成
        output_path = self.get_output_path(output_filename, ".pdf")
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=self.pagesize,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )

        # PHASE CORE LOGIC: コンテンツ構築
        story = []
        title = kwargs.get('title', 'Motion Analysis Report')

        # 1. タイトル
        story.extend(self._build_title(title))

        # 2. サマリーセクション
        story.extend(self._build_summary(result))

        # 3. 詳細評価セクション
        story.extend(self._build_detailed_evaluation(result))

        # 4. ヘルスチェックセクション
        if 'health_check' in result:
            story.extend(self._build_health_check(result['health_check']))

        # PHASE CORE LOGIC: PDF 生成
        doc.build(story)

        return str(output_path.absolute())

    def _build_title(self, title: str) -> List:
        """
        What: タイトルセクション構築
        Why: レポートのヘッダー情報を提供
        Design Decision: タイトル、日時、区切り線

        Args:
            title: レポートタイトル

        Returns:
            List: reportlab elements
        """
        elements = []

        # タイトル
        elements.append(Paragraph(title, self.styles['CenterTitle']))

        # 生成日時
        generated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        elements.append(Paragraph(f"Generated: {generated_at}", self.styles['Normal']))
        elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _build_summary(self, result: Dict[str, Any]) -> List:
        """
        What: サマリーセクション構築
        Why: 評価結果の概要を提供
        Design Decision: テーブル形式で表示

        Args:
            result: 評価結果辞書

        Returns:
            List: reportlab elements
        """
        elements = []

        elements.append(Paragraph("Summary", self.styles['SectionTitle']))

        # サマリーテーブル
        data = [
            ['Test Type', result.get('test_type', 'Unknown')],
            ['Total Score', f"{result.get('score', 0)}/3"],
            ['Video Path', result.get('video_path', 'N/A')],
            ['Details', result.get('details', 'N/A')]
        ]

        table = Table(data, colWidths=[2 * inch, 4 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F4F8')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP')
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _build_detailed_evaluation(self, result: Dict[str, Any]) -> List:
        """
        What: 詳細評価セクション構築
        Why: 各評価指標のスコアと詳細を提供
        Design Decision: テーブル形式で表示

        Args:
            result: 評価結果辞書

        Returns:
            List: reportlab elements
        """
        elements = []

        if 'evaluation' not in result:
            return elements

        elements.append(Paragraph("Detailed Evaluation", self.styles['SectionTitle']))

        # 詳細評価テーブル
        evaluation = result['evaluation']
        data = [['Metric', 'Score', 'Details']]

        for key, value in evaluation.items():
            if isinstance(value, dict):
                metric_name = key.replace('_', ' ').title()
                score = value.get('score', 'N/A')
                # 詳細情報を抽出（scoreキー以外）
                details = ', '.join([f"{k}: {v}" for k, v in value.items() if k != 'score'])
                data.append([metric_name, str(score), details[:50] + '...' if len(details) > 50 else details])

        if len(data) > 1:
            table = Table(data, colWidths=[2 * inch, 1 * inch, 3 * inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#06A77D')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F0F0')])
            ]))

            elements.append(table)
            elements.append(Spacer(1, 0.3 * inch))

        return elements

    def _build_health_check(self, health_check: Dict[str, Any]) -> List:
        """
        What: ヘルスチェックセクション構築
        Why: データ品質情報を提供
        Design Decision: テーブル形式で表示

        Args:
            health_check: ヘルスチェック結果

        Returns:
            List: reportlab elements
        """
        elements = []

        elements.append(Paragraph("Health Check", self.styles['SectionTitle']))

        # ヘルスチェックテーブル
        data = [
            ['Quality', health_check.get('quality', 'Unknown')],
            ['Warnings', ', '.join(health_check.get('warnings', []))]
        ]

        table = Table(data, colWidths=[2 * inch, 4 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FFF4E6')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey)
        ]))

        elements.append(table)

        return elements
