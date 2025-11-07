"""
Purpose: Structured logging utilities for THF Motion Scan
Responsibility: Unified structured logging (CLI/Lambda compatible)
Dependencies: json, uuid, datetime
Created: 2025-11-03 by Claude Code
Decision Log: Logging Standards implementation

CRITICAL:
- 必須キー9項目の検証
- ISO8601Z timestamp自動生成
- UUID v4自動生成（request_id, session_id）
- JSON 1行出力（stdout/ファイル）
- PII（個人情報）を含めない
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, TextIO


# ログレベル定義
class LogLevel:
    """
    What: ログレベル定義
    Why: レベル比較とフィルタリングを可能にする
    Design Decision: 数値ベース（DEBUG=10, INFO=20, WARN=30, ERROR=40）

    CRITICAL: 数値が大きいほど重要度が高い
    """
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40

    @classmethod
    def from_string(cls, level: str) -> int:
        """
        What: 文字列からログレベル数値に変換
        Why: ユーザー入力（--log-level DEBUG等）を数値化
        Design Decision: 大小文字を区別しない

        Args:
            level: ログレベル文字列（"DEBUG", "INFO", "WARN", "ERROR"）

        Returns:
            int: ログレベル数値

        Raises:
            ValueError: 不正なログレベル

        CRITICAL: 不正な値はエラー（暗黙のデフォルト値なし）
        """
        level_upper = level.upper()
        mapping = {
            "DEBUG": cls.DEBUG,
            "INFO": cls.INFO,
            "WARN": cls.WARN,
            "WARNING": cls.WARN,  # 互換性
            "ERROR": cls.ERROR,
        }
        if level_upper not in mapping:
            raise ValueError(
                f"Invalid log level: {level}. "
                f"Must be one of: DEBUG, INFO, WARN, ERROR"
            )
        return mapping[level_upper]

    @classmethod
    def to_string(cls, level: int) -> str:
        """
        What: ログレベル数値を文字列に変換
        Why: JSON出力時の可読性
        Design Decision: 標準名（DEBUG, INFO, WARN, ERROR）

        Args:
            level: ログレベル数値

        Returns:
            str: ログレベル文字列

        CRITICAL: 不明なレベルは"UNKNOWN"
        """
        mapping = {
            cls.DEBUG: "DEBUG",
            cls.INFO: "INFO",
            cls.WARN: "WARN",
            cls.ERROR: "ERROR",
        }
        return mapping.get(level, "UNKNOWN")


class Logger:
    """
    What: 構造化ログエントリを生成・出力
    Why: 統一されたログフォーマットで観測性を向上
    Design Decision: immutableなdefault_contextをベースに、動的にフィールド追加

    CRITICAL:
    - 必須キー9項目の検証（出力前チェック）
    - UUID自動生成（request_id, session_idが未指定の場合）
    - JSON 1行出力（改行なし）
    """

    # 必須キー（9項目）
    REQUIRED_KEYS = {
        "timestamp",
        "level",
        "message",
        "request_id",
        "session_id",
        "test_code",
        "rules_version",
        "normalization_version",
        "artifact_sha",
    }

    def __init__(
        self,
        component: str,
        default_context: Dict[str, Any],
        min_level: int = LogLevel.INFO,
        output_file: Optional[Path] = None,
    ):
        """
        What: Loggerインスタンス初期化
        Why: コンポーネント固有のコンテキストを保持
        Design Decision: default_contextは不変、動的フィールドは各呼び出しで追加

        Args:
            component: 実行元コンポーネント名（例: "cli", "lambda", "lambda:pose_extraction"）
            default_context: デフォルトコンテキスト（test_code, rules_version等）
            min_level: 最小ログレベル（これ未満は出力しない）
            output_file: 出力先ファイルパス（Noneの場合はstdoutのみ）

        CRITICAL:
        - request_id, session_idが未指定の場合はUUID自動生成
        - output_fileは追記モード（"a"）で開く
        """
        self.component = component
        self.default_context = default_context.copy()
        self.min_level = min_level
        self.output_file = output_file

        # request_id, session_idの自動生成（未指定の場合）
        if "request_id" not in self.default_context:
            self.default_context["request_id"] = str(uuid.uuid4())
        if "session_id" not in self.default_context:
            self.default_context["session_id"] = str(uuid.uuid4())

        # output_fileを追記モードで開く
        self._file_handle: Optional[TextIO] = None
        if self.output_file:
            self._file_handle = open(self.output_file, "a", encoding="utf-8")

    def __del__(self):
        """
        What: Loggerインスタンス破棄時の処理
        Why: ファイルハンドルをクローズ
        Design Decision: __del__でクローズ（明示的close()は不要）

        CRITICAL: ファイルハンドルのリーク防止
        """
        if self._file_handle:
            self._file_handle.close()

    def _validate_entry(self, entry: Dict[str, Any]) -> None:
        """
        What: ログエントリの必須キー検証
        Why: 出力前に不正なエントリを検出
        Design Decision: 欠落時は ValueError（開発時に検知）

        Args:
            entry: ログエントリ

        Raises:
            ValueError: 必須キー欠落

        CRITICAL: 本番環境でも厳格に検証（暗黙のデフォルト値なし）
        """
        missing_keys = self.REQUIRED_KEYS - set(entry.keys())
        if missing_keys:
            raise ValueError(
                f"Missing required log keys: {sorted(missing_keys)}. "
                f"Entry: {json.dumps(entry, ensure_ascii=False, default=str)}"
            )

    def _emit(self, level: int, message: str, **extra: Any) -> None:
        """
        What: ログエントリを生成・出力
        Why: レベルフィルタ→必須キー検証→JSON出力の統一処理
        Design Decision: stdout + ファイル（両方）に出力

        Args:
            level: ログレベル数値
            message: 人間可読メッセージ
            **extra: 追加フィールド（任意フィールド等）

        CRITICAL:
        - levelフィルタ（min_level未満は出力しない）
        - 必須キー検証（欠落時はValueError）
        - JSON 1行出力（改行なし）
        """
        # レベルフィルタ
        if level < self.min_level:
            return

        # エントリ生成
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": LogLevel.to_string(level),
            "message": message,
            "component": self.component,
        }

        # default_contextをマージ
        entry.update(self.default_context)

        # extraをマージ（上書き）
        entry.update(extra)

        # 必須キー検証
        self._validate_entry(entry)

        # JSON 1行出力
        json_line = json.dumps(entry, ensure_ascii=False, default=str)

        # stdoutに出力
        print(json_line, file=sys.stdout, flush=True)

        # ファイルに出力（指定されている場合）
        if self._file_handle:
            self._file_handle.write(json_line + "\n")
            self._file_handle.flush()

    def debug(self, message: str, **extra: Any) -> None:
        """
        What: DEBUGレベルログ出力
        Why: 詳細なデバッグ情報を記録
        Design Decision: 本番環境では通常OFF（min_level=INFO以上）

        Args:
            message: 人間可読メッセージ
            **extra: 追加フィールド

        CRITICAL: 開発時のみ有効（本番は min_level=INFO 以上推奨）
        """
        self._emit(LogLevel.DEBUG, message, **extra)

    def info(self, message: str, **extra: Any) -> None:
        """
        What: INFOレベルログ出力
        Why: 通常の動作情報を記録
        Design Decision: デフォルトの最小レベル

        Args:
            message: 人間可読メッセージ
            **extra: 追加フィールド

        CRITICAL: 本番環境の標準レベル
        """
        self._emit(LogLevel.INFO, message, **extra)

    def warn(self, message: str, **extra: Any) -> None:
        """
        What: WARNレベルログ出力
        Why: 警告（処理は継続するが注意が必要）
        Design Decision: warning() ではなく warn()（短縮形）

        Args:
            message: 人間可読メッセージ
            **extra: 追加フィールド

        CRITICAL: エラーではないが異常な状況
        """
        self._emit(LogLevel.WARN, message, **extra)

    def error(self, message: str, error_code: Optional[str] = None, error_message: Optional[str] = None, **extra: Any) -> None:
        """
        What: ERRORレベルログ出力
        Why: エラー情報を記録
        Design Decision: error_code, error_messageを明示的に引数化

        Args:
            message: 人間可読メッセージ
            error_code: エラー分類コード（例: "VALIDATION_FAILED"）
            error_message: エラー詳細
            **extra: 追加フィールド

        CRITICAL: error_code, error_messageは任意だが、ERROR時は推奨
        """
        if error_code is not None:
            extra["error_code"] = error_code
        if error_message is not None:
            extra["error_message"] = error_message

        self._emit(LogLevel.ERROR, message, **extra)


def make_logger(
    component: str,
    default_context: Optional[Dict[str, Any]] = None,
    log_level: str = "INFO",
    log_file: Optional[str] = None,
) -> Logger:
    """
    What: Loggerインスタンスを生成
    Why: ファクトリー関数による統一されたインスタンス生成
    Design Decision: log_level文字列→数値変換、log_file文字列→Path変換

    Args:
        component: 実行元コンポーネント名（例: "cli", "lambda"）
        default_context: デフォルトコンテキスト（test_code, rules_version等）
        log_level: ログレベル文字列（"DEBUG", "INFO", "WARN", "ERROR"）
        log_file: 出力先ファイルパス（Noneの場合はstdoutのみ）

    Returns:
        Logger: Loggerインスタンス

    Raises:
        ValueError: 不正なlog_level

    CRITICAL:
    - default_contextが未指定の場合は空辞書
    - request_id, session_idが未指定の場合はLogger内でUUID自動生成

    Example:
        >>> logger = make_logger(
        ...     component="cli",
        ...     default_context={
        ...         "test_code": "push_pull",
        ...         "rules_version": "1.0.0",
        ...         "normalization_version": "1.2.1",
        ...         "artifact_sha": "a3f5c8d1",
        ...     },
        ...     log_level="INFO",
        ...     log_file="output/log.jsonl",
        ... )
        >>> logger.info("Evaluation started", duration_ms=1234)
    """
    if default_context is None:
        default_context = {}

    min_level = LogLevel.from_string(log_level)
    output_file = Path(log_file) if log_file else None

    return Logger(
        component=component,
        default_context=default_context,
        min_level=min_level,
        output_file=output_file,
    )
