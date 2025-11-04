"""
Purpose: change_logger のテスト（idempotency、dry-run、Apply/Undo）
Responsibility: ログ記録の品質保証
Created: 2025-11-04 by Claude Code
Decision Log: ADR-TBD（閾値変更ログシステム）

CRITICAL:
- 決定論的テスト（時刻固定、seed固定）
- dry-run環境変数のクリーンアップ
- テスト後のログディレクトリ削除
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.thresholds_editor.change_logger import ChangeLogger, get_logger
from src.thresholds_editor.changelog import ChangeLogEntry


@pytest.fixture
def temp_log_dir(tmp_path):
    """
    What: 一時ログディレクトリを提供
    Why: テスト間の独立性確保
    """
    log_dir = tmp_path / "test_logs"
    yield log_dir
    # クリーンアップ不要（tmp_pathが自動削除）


@pytest.fixture
def sample_entry():
    """
    What: テスト用のChangeLogEntryを提供
    Why: テストケース間で再利用
    """
    return ChangeLogEntry(
        id="chg_001",
        actor="test_user",
        env="dev",
        test="SLS",
        metric="pelvis_stability.left",
        prev={"ok": [0, 10], "attn": [10, 15], "ng": [15, 100]},
        next={"ok": [0, 12], "attn": [12, 18], "ng": [18, 100]},
        reclassified_rate=0.15,
        reclassified_count=3,
        sample_n=20,
        representatives={"upshift": ["rep_001"], "downshift": ["rep_002"]},
        versions={"data_version": "1.0.0", "rules_version": "1.0.0"},
        timestamp=datetime(2025, 11, 4, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture(autouse=True)
def clean_dry_run_env():
    """
    What: DRY_RUN環境変数をクリーンアップ
    Why: テスト間の干渉を防ぐ
    """
    original_value = os.environ.get("DRY_RUN")
    yield
    if original_value is not None:
        os.environ["DRY_RUN"] = original_value
    else:
        os.environ.pop("DRY_RUN", None)


def test_log_apply_creates_file(temp_log_dir, sample_entry):
    """
    What: Apply操作のログ記録
    Why: 基本的なログファイル作成を確認

    Given: ロガーインスタンス
    When: log_apply()を呼び出す
    Then: 指定パスにJSONLファイルが作成される
    """
    logger = ChangeLogger(base_dir=temp_log_dir, cache_size=10)

    # Apply記録
    idempotency_key = logger.log_apply(sample_entry)

    # ファイル存在確認
    expected_path = temp_log_dir / "202511" / "change_log-20251104.jsonl"
    assert expected_path.exists()

    # 内容確認
    with open(expected_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "apply"
        assert entry["actor"] == "test_user"
        assert entry["test"] == "SLS"
        assert entry["idempotency_key"] == idempotency_key


def test_log_apply_idempotency_prevents_duplicate(temp_log_dir, sample_entry):
    """
    What: idempotencyによる重複防止
    Why: 同一操作を2回記録しないことを確認

    Given: 同じエントリ
    When: log_apply()を2回呼び出す
    Then: 1回目のみ記録される
    """
    logger = ChangeLogger(base_dir=temp_log_dir, cache_size=10)

    # 1回目: 記録される
    key1 = logger.log_apply(sample_entry)
    assert key1 is not None

    # 2回目: 重複検出、記録されない
    key2 = logger.log_apply(sample_entry)
    assert key2 is None

    # ファイル確認（1行のみ）
    expected_path = temp_log_dir / "202511" / "change_log-20251104.jsonl"
    with open(expected_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1


def test_log_apply_different_entries_are_recorded(temp_log_dir, sample_entry):
    """
    What: 異なるエントリは両方記録される
    Why: idempotencyが異なる操作を誤ってブロックしないことを確認

    Given: 2つの異なるエントリ
    When: log_apply()を2回呼び出す
    Then: 両方記録される
    """
    logger = ChangeLogger(base_dir=temp_log_dir, cache_size=10)

    # 1回目
    key1 = logger.log_apply(sample_entry)

    # 2回目（異なるmetric）
    entry2 = ChangeLogEntry(
        id="chg_002",
        actor="test_user",
        env="dev",
        test="SLS",
        metric="knee_valgus.right",  # 異なるmetric
        prev={"ok": [0, 10], "attn": [10, 15], "ng": [15, 100]},
        next={"ok": [0, 12], "attn": [12, 18], "ng": [18, 100]},
        reclassified_rate=0.20,
        reclassified_count=4,
        sample_n=20,
        representatives={"upshift": [], "downshift": []},
        versions={"data_version": "1.0.0"},
        timestamp=datetime(2025, 11, 4, 12, 0, 0, tzinfo=timezone.utc),
    )
    key2 = logger.log_apply(entry2)

    assert key1 != key2
    assert key1 is not None
    assert key2 is not None

    # ファイル確認（2行）
    expected_path = temp_log_dir / "202511" / "change_log-20251104.jsonl"
    with open(expected_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 2


def test_log_apply_dry_run_skips_logging(temp_log_dir, sample_entry):
    """
    What: dry-run時はログ記録しない
    Why: テスト実行時の不要なログ蓄積を防ぐ

    Given: DRY_RUN=true環境
    When: log_apply()を呼び出す
    Then: ログファイルが作成されない
    """
    os.environ["DRY_RUN"] = "true"
    logger = ChangeLogger(base_dir=temp_log_dir, cache_size=10)

    # dry-run環境で実行
    key = logger.log_apply(sample_entry)
    assert key is None

    # ファイル確認（作成されていない）
    expected_path = temp_log_dir / "202511" / "change_log-20251104.jsonl"
    assert not expected_path.exists()


def test_log_undo_creates_entry(temp_log_dir):
    """
    What: Undo操作のログ記録
    Why: ロールバック履歴を残すことを確認

    Given: ロガーインスタンス
    When: log_undo()を呼び出す
    Then: undoエントリが記録される
    """
    logger = ChangeLogger(base_dir=temp_log_dir, cache_size=10)

    with patch("src.thresholds_editor.change_logger.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2025, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        key = logger.log_undo(
            actor="test_user",
            env="dev",
            rollback_of_id="chg_001",
            reverted_snapshot_path="/path/to/snapshot.json",
            versions={"data_version": "1.0.0"},
        )

    assert key is not None

    # ファイル確認
    expected_path = temp_log_dir / "202511" / "change_log-20251104.jsonl"
    with open(expected_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["action"] == "undo"
        assert entry["actor"] == "test_user"
        assert entry["rollback_of"] == "chg_001"


def test_log_undo_idempotency(temp_log_dir):
    """
    What: Undo操作のidempotency
    Why: 同じロールバックを2回記録しないことを確認

    Given: 同じundo操作
    When: log_undo()を2回呼び出す
    Then: 1回目のみ記録される
    """
    logger = ChangeLogger(base_dir=temp_log_dir, cache_size=10)

    with patch("src.thresholds_editor.change_logger.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2025, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        # 1回目
        key1 = logger.log_undo(
            actor="test_user",
            env="dev",
            rollback_of_id="chg_001",
            reverted_snapshot_path="/path/to/snapshot.json",
        )

        # 2回目（同じ操作）
        key2 = logger.log_undo(
            actor="test_user",
            env="dev",
            rollback_of_id="chg_001",
            reverted_snapshot_path="/path/to/snapshot.json",
        )

    assert key1 is not None
    assert key2 is None

    # ファイル確認（1行のみ）
    expected_path = temp_log_dir / "202511" / "change_log-20251104.jsonl"
    with open(expected_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1


def test_log_undo_dry_run_skips_logging(temp_log_dir):
    """
    What: dry-run時のUndoはログ記録しない
    Why: テスト実行時の不要なログ蓄積を防ぐ

    Given: DRY_RUN=true環境
    When: log_undo()を呼び出す
    Then: ログファイルが作成されない
    """
    os.environ["DRY_RUN"] = "true"
    logger = ChangeLogger(base_dir=temp_log_dir, cache_size=10)

    key = logger.log_undo(
        actor="test_user",
        env="dev",
        rollback_of_id="chg_001",
        reverted_snapshot_path="/path/to/snapshot.json",
    )
    assert key is None

    # ファイル確認（作成されていない）
    expected_path = temp_log_dir / "202511" / "change_log-20251104.jsonl"
    assert not expected_path.exists()


def test_load_recent_logs(temp_log_dir, sample_entry):
    """
    What: 最新N件のログ取得
    Why: UI表示用のログ取得を確認

    Given: 複数のログエントリ
    When: load_recent_logs(n=3)を呼び出す
    Then: 最新3件が新しい順で返される
    """
    with patch("src.thresholds_editor.change_logger.datetime") as mock_dt:
        # 固定日時でモック
        fixed_time = datetime(2025, 11, 4, 12, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = fixed_time
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        logger = ChangeLogger(base_dir=temp_log_dir, cache_size=10)

        # 5件記録
        for i in range(5):
            entry = ChangeLogEntry(
                id=f"chg_{i:03d}",
                actor="test_user",
                env="dev",
                test="SLS",
                metric=f"metric_{i}",
                prev={"ok": [0, 10], "attn": [10, 15], "ng": [15, 100]},
                next={"ok": [0, 12], "attn": [12, 18], "ng": [18, 100]},
                reclassified_rate=0.1,
                reclassified_count=1,
                sample_n=10,
                representatives={"upshift": [], "downshift": []},
                versions={},
                timestamp=fixed_time,
            )
            logger.log_apply(entry, force=True)  # force=Trueで重複許可

        # 最新3件取得
        recent = logger.load_recent_logs(n=3)
        assert len(recent) == 3
        # 新しい順（chg_004, chg_003, chg_002）
        assert recent[0]["metric"] == "metric_4"
        assert recent[1]["metric"] == "metric_3"
        assert recent[2]["metric"] == "metric_2"


def test_get_logger_singleton(temp_log_dir):
    """
    What: get_logger()のシングルトン動作
    Why: グローバルインスタンスが共有されることを確認

    Given: 2回get_logger()を呼び出す
    When: 同じ引数で呼び出す
    Then: 同じインスタンスが返される
    """
    # グローバルロガーをクリア（テスト用）
    import src.thresholds_editor.change_logger as cl
    cl._global_logger = None

    logger1 = get_logger(base_dir=temp_log_dir)
    logger2 = get_logger(base_dir=temp_log_dir)

    assert logger1 is logger2
