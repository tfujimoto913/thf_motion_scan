"""
Purpose: 閾値変更履歴を自動記録（idempotency保証、dry-run対応）
Responsibility: Apply/Undo時のログ記録、重複防止、監査証跡
Created: 2025-11-04 by Claude Code
Decision Log: ADR-TBD（閾値変更ログシステム）

CRITICAL:
- idempotencyキー：sha256(normalized_diff + versions + actor + scope)
- dry-run時は記録しない（DRY_RUN=true）
- 直近N件のキーをメモリ保持で重複チェック
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Deque, Dict, Optional

from .changelog import ChangeLogEntry


class ChangeLogger:
    """
    What: 閾値変更履歴のロガー（idempotency保証）
    Why: 重複記録を防ぎ、監査証跡を確保するため

    Design Decision:
    - パス構造：logs/change_log/YYYYMM/change_log-YYYYMMDD.jsonl
    - 月単位でディレクトリ分割（ローテーション容易化）
    - 日単位でファイル分割（検索効率化）
    """

    def __init__(
        self,
        base_dir: Path = Path("logs/change_log"),
        cache_size: int = 100,
    ):
        """
        Args:
            base_dir: ログディレクトリのベース（デフォルト: logs/change_log）
            cache_size: idempotencyキャッシュサイズ（デフォルト: 100件）
        """
        self.base_dir = base_dir
        self.cache_size = cache_size
        # What: 直近N件のidempotencyキーをメモリ保持
        # Why: 高速な重複チェックのため（ファイルI/O削減）
        self._idempotency_cache: Deque[str] = deque(maxlen=cache_size)
        self._load_recent_keys()

    def _load_recent_keys(self) -> None:
        """
        What: 起動時に最新ログファイルからキーを読み込み
        Why: キャッシュを初期化し、重複チェックを即座に可能にするため
        """
        today = datetime.now(timezone.utc)
        log_path = self._get_log_path(today)

        if not log_path.exists():
            return

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # 直近N件を読み込み
                for line in lines[-self.cache_size:]:
                    entry = json.loads(line)
                    if "idempotency_key" in entry:
                        self._idempotency_cache.append(entry["idempotency_key"])
        except (json.JSONDecodeError, IOError):
            # ファイル破損・アクセスエラー時はキャッシュ空で継続
            pass

    def _get_log_path(self, timestamp: datetime) -> Path:
        """
        What: ログファイルパスを生成
        Why: YYYYMM/change_log-YYYYMMDD.jsonl 形式で整理

        Args:
            timestamp: タイムスタンプ

        Returns:
            Path: logs/change_log/YYYYMM/change_log-YYYYMMDD.jsonl
        """
        year_month = timestamp.strftime("%Y%m")
        date = timestamp.strftime("%Y%m%d")
        month_dir = self.base_dir / year_month
        return month_dir / f"change_log-{date}.jsonl"

    def _generate_idempotency_key(
        self,
        entry: ChangeLogEntry,
        action: str = "apply",
    ) -> str:
        """
        What: idempotencyキーを生成
        Why: 同一操作の重複記録を防ぐため

        Design Decision:
        - sha256(normalized_diff + versions + actor + scope)
        - action="apply"/"undo"で区別

        Args:
            entry: ChangeLogEntryオブジェクト
            action: "apply" or "undo"

        Returns:
            str: SHA256ハッシュ（16進数）
        """
        # What: 正規化された差分データを作成
        # Why: フィールドの順序に依存しない一貫性のため
        normalized_diff = json.dumps(
            {
                "action": action,
                "test": entry.test,
                "metric": entry.metric,
                "prev": sorted(json.dumps(entry.prev, sort_keys=True)),
                "next": sorted(json.dumps(entry.next, sort_keys=True)),
                "actor": entry.actor,
                "env": entry.env,
                "versions": sorted(json.dumps(entry.versions, sort_keys=True)),
            },
            sort_keys=True,
        )

        return hashlib.sha256(normalized_diff.encode("utf-8")).hexdigest()

    def _is_dry_run(self) -> bool:
        """
        What: dry-runモード判定
        Why: テスト実行時はログ記録を抑制するため

        Returns:
            bool: DRY_RUN=true の場合 True
        """
        dry_run_env = os.environ.get("DRY_RUN", "").lower()
        return dry_run_env in ("true", "1", "yes")

    def log_apply(
        self,
        entry: ChangeLogEntry,
        force: bool = False,
    ) -> Optional[str]:
        """
        What: Apply操作のログ記録
        Why: 閾値適用履歴を監査証跡として残すため

        Args:
            entry: ChangeLogEntryオブジェクト
            force: idempotencyチェックをスキップ（デフォルト: False）

        Returns:
            Optional[str]: 記録成功時はidempotencyキー、スキップ時はNone
        """
        # dry-runガード
        if self._is_dry_run():
            return None

        # idempotencyチェック
        idempotency_key = self._generate_idempotency_key(entry, action="apply")
        if not force and idempotency_key in self._idempotency_cache:
            # 重複検出：記録しない
            return None

        # ログエントリ作成
        log_entry = {
            **entry.to_dict(),
            "action": "apply",
            "idempotency_key": idempotency_key,
        }

        # ファイル追記
        self._append_to_log(log_entry, entry.timestamp)

        # キャッシュ更新
        self._idempotency_cache.append(idempotency_key)

        return idempotency_key

    def log_undo(
        self,
        actor: str,
        env: str,
        rollback_of_id: str,
        reverted_snapshot_path: str,
        versions: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        What: Undo操作のログ記録
        Why: ロールバック履歴を監査証跡として残すため

        Args:
            actor: 操作者名
            env: 環境（dev/stg/prod）
            rollback_of_id: 取り消し対象のエントリID
            reverted_snapshot_path: 復元したスナップショットパス
            versions: バージョン情報

        Returns:
            Optional[str]: 記録成功時はidempotencyキー、スキップ時はNone
        """
        # dry-runガード
        if self._is_dry_run():
            return None

        timestamp = datetime.now(timezone.utc)
        entry_id = f"undo_{timestamp.isoformat()}"

        # ログエントリ作成
        log_entry = {
            "id": entry_id,
            "action": "undo",
            "actor": actor,
            "env": env,
            "rollback_of": rollback_of_id,
            "reverted_snapshot": reverted_snapshot_path,
            "versions": versions or {},
            "timestamp": timestamp.isoformat(),
        }

        # idempotencyキー生成（undo専用）
        normalized_undo = json.dumps(
            {
                "action": "undo",
                "rollback_of": rollback_of_id,
                "actor": actor,
                "env": env,
            },
            sort_keys=True,
        )
        idempotency_key = hashlib.sha256(normalized_undo.encode("utf-8")).hexdigest()

        # 重複チェック
        if idempotency_key in self._idempotency_cache:
            return None

        log_entry["idempotency_key"] = idempotency_key

        # ファイル追記
        self._append_to_log(log_entry, timestamp)

        # キャッシュ更新
        self._idempotency_cache.append(idempotency_key)

        return idempotency_key

    def _append_to_log(self, entry: Dict, timestamp: datetime) -> None:
        """
        What: JSONLファイルに1行追記
        Why: 日単位でログを分割管理するため

        Args:
            entry: ログエントリ（辞書）
            timestamp: タイムスタンプ（パス決定用）
        """
        log_path = self._get_log_path(timestamp)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def load_recent_logs(self, n: int = 10) -> list[Dict]:
        """
        What: 最新N件のログを取得
        Why: UI表示用

        Args:
            n: 取得件数

        Returns:
            list[Dict]: 最新N件のログエントリ（新しい順）
        """
        today = datetime.now(timezone.utc)
        log_path = self._get_log_path(today)

        if not log_path.exists():
            return []

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                recent = [json.loads(line) for line in lines[-n:]] if lines else []
                return list(reversed(recent))
        except (json.JSONDecodeError, IOError):
            return []


# What: グローバルロガーインスタンス
# Why: モジュール内で共有し、インスタンス生成コストを削減
_global_logger: Optional[ChangeLogger] = None


def get_logger(
    base_dir: Path = Path("logs/change_log"),
    cache_size: int = 100,
) -> ChangeLogger:
    """
    What: ChangeLoggerインスタンスを取得（シングルトン）
    Why: アプリ全体で1つのキャッシュを共有するため

    Args:
        base_dir: ログディレクトリのベース
        cache_size: キャッシュサイズ

    Returns:
        ChangeLogger: ロガーインスタンス
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = ChangeLogger(base_dir=base_dir, cache_size=cache_size)
    return _global_logger
