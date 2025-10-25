"""
Purpose: エクスポーター基底クラス
Responsibility: 各種エクスポーターの共通インターフェース定義
Dependencies: abc
Created: 2025-10-25 by Claude
Decision Log: ADR-011（Phase 2: 出力物生成機能）

CRITICAL: 全てのエクスポーターはこの基底クラスを継承必須
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pathlib import Path


class BaseExporter(ABC):
    """
    What: エクスポーター基底クラス（抽象クラス）
    Why: 各種出力形式（CSV/PNG/PDF）の統一インターフェース提供
    Design Decision: ABC（Abstract Base Class）を使用して型安全性保証（ADR-011）

    CRITICAL: export()メソッドは全サブクラスで実装必須
    """

    def __init__(self, output_dir: str = "outputs"):
        """
        What: エクスポーター初期化
        Why: 出力ディレクトリを一元管理
        Design Decision: デフォルト出力先を "outputs" に統一

        Args:
            output_dir: 出力ディレクトリパス

        CRITICAL: output_dir が存在しない場合は自動作成
        """
        # PHASE CORE LOGIC: 出力ディレクトリ設定
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def export(self,
               result: Dict[str, Any],
               output_filename: str,
               **kwargs) -> str:
        """
        What: エクスポート処理（抽象メソッド）
        Why: 全エクスポーターに統一インターフェース強制
        Design Decision: 返り値に出力ファイルパスを返す（検証容易化）

        Args:
            result: 評価結果辞書
            output_filename: 出力ファイル名（拡張子除く）
            **kwargs: 追加オプション

        Returns:
            str: 出力ファイルの絶対パス

        CRITICAL: サブクラスで必ず実装すること
        """
        pass

    def validate_result(self, result: Dict[str, Any]) -> bool:
        """
        What: 評価結果の妥当性検証
        Why: 不正データの早期検出
        Design Decision: 必須キー（score, details）の存在確認

        Args:
            result: 評価結果辞書

        Returns:
            bool: 妥当性（True=正常、False=異常）

        CRITICAL: score が 0-3 範囲外の場合は False を返す
        """
        # PHASE CORE LOGIC: 必須キー存在確認
        if 'score' not in result or 'details' not in result:
            return False

        # スコア範囲チェック（0-3）
        score = result['score']
        if not isinstance(score, int) or score < 0 or score > 3:
            return False

        return True

    def get_output_path(self, filename: str, extension: str) -> Path:
        """
        What: 出力ファイルパス生成
        Why: ファイルパス生成ロジックを一元化
        Design Decision: output_dir + filename + extension

        Args:
            filename: ファイル名（拡張子除く）
            extension: 拡張子（.csv, .png, .pdf）

        Returns:
            Path: 出力ファイルの絶対パス

        CRITICAL: 拡張子は . を含める（例: ".csv"）
        """
        # PHASE CORE LOGIC: パス生成
        return self.output_dir / f"{filename}{extension}"
