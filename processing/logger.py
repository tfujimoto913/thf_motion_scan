"""
Purpose: 構造化ロギング（JSON形式）
Responsibility: CloudWatch Logs形式で検索可能なログ出力
Dependencies: json, datetime, traceback (標準ライブラリのみ)
Created: 2025-10-31 by Claude
Decision Log: Phase 5 - Stage 3（構造化ロギング強化）

CRITICAL: Lambda環境では標準出力がCloudWatch Logsに送信される
"""
import json
import sys
import traceback
from datetime import datetime
from typing import Dict, Any, Optional


def _build_log_entry(
    level: str,
    message: str,
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    exc_info: Optional[Exception] = None
) -> Dict[str, Any]:
    """
    What: JSON形式のログエントリを構築
    Why: CloudWatch Logs Insightsでの検索性向上
    Design Decision: 標準フィールド（timestamp, level, message）+ オプションフィールド

    Args:
        level: ログレベル（INFO, WARNING, ERROR）
        message: ログメッセージ
        video_id: 動画ID（オプション）
        test_type: テストタイプ（オプション）
        context: 追加コンテキスト情報（オプション）
        exc_info: 例外情報（オプション）

    Returns:
        Dict: JSON形式のログエントリ

    CRITICAL: ISO 8601形式のタイムスタンプ（UTC）
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "level": level,
        "message": message
    }

    # オプションフィールド追加
    if video_id:
        log_entry["video_id"] = video_id

    if test_type:
        log_entry["test_type"] = test_type

    if context:
        log_entry["context"] = context

    # 例外情報追加
    if exc_info:
        log_entry["error"] = {
            "type": type(exc_info).__name__,
            "message": str(exc_info),
            "traceback": traceback.format_exc()
        }

    return log_entry


def log_info(
    message: str,
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    What: INFO レベルのログ出力
    Why: 正常処理の進捗を記録
    Design Decision: JSON形式で標準出力に書き込み

    Args:
        message: ログメッセージ
        video_id: 動画ID（オプション）
        test_type: テストタイプ（オプション）
        context: 追加コンテキスト情報（オプション）

    CRITICAL: print()ではなくjson.dumps()で出力（CloudWatch Logs形式）
    """
    log_entry = _build_log_entry("INFO", message, video_id, test_type, context)
    print(json.dumps(log_entry, ensure_ascii=False), file=sys.stdout)


def log_warning(
    message: str,
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """
    What: WARNING レベルのログ出力
    Why: 注意が必要な状況を記録（処理は継続）
    Design Decision: JSON形式で標準出力に書き込み

    Args:
        message: ログメッセージ
        video_id: 動画ID（オプション）
        test_type: テストタイプ（オプション）
        context: 追加コンテキスト情報（オプション）

    CRITICAL: 品質チェック失敗、再撮影推奨等で使用
    """
    log_entry = _build_log_entry("WARNING", message, video_id, test_type, context)
    print(json.dumps(log_entry, ensure_ascii=False), file=sys.stdout)


def log_error(
    message: str,
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    exc_info: Optional[Exception] = None
) -> None:
    """
    What: ERROR レベルのログ出力
    Why: エラー発生時のコンテキスト情報を記録
    Design Decision: JSON形式 + スタックトレース

    Args:
        message: ログメッセージ
        video_id: 動画ID（オプション）
        test_type: テストタイプ（オプション）
        context: 追加コンテキスト情報（オプション）
        exc_info: 例外オブジェクト（オプション）

    CRITICAL: exc_infoがある場合はスタックトレースも含める
    """
    log_entry = _build_log_entry("ERROR", message, video_id, test_type, context, exc_info)
    print(json.dumps(log_entry, ensure_ascii=False), file=sys.stderr)


def log_processing_start(video_path: str, test_type: str, video_id: Optional[str] = None) -> None:
    """
    What: 処理開始ログ（定型）
    Why: 処理トレーサビリティの確保
    Design Decision: 共通フォーマットで呼び出し側のコード簡略化

    Args:
        video_path: 動画ファイルパス
        test_type: テストタイプ
        video_id: 動画ID（オプション）

    CRITICAL: 処理開始時の必須情報をまとめて記録
    """
    log_info(
        message="Processing started",
        video_id=video_id,
        test_type=test_type,
        context={"video_path": video_path}
    )


def log_processing_complete(
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    score: Optional[float] = None,
    max_score: Optional[float] = None
) -> None:
    """
    What: 処理完了ログ（定型）
    Why: 成功ケースのトレーサビリティ
    Design Decision: スコア情報を含める

    Args:
        video_id: 動画ID（オプション）
        test_type: テストタイプ（オプション）
        score: 評価スコア（オプション）
        max_score: 最大スコア（オプション）

    CRITICAL: 処理成功時の最終結果を記録
    """
    context = {}
    if score is not None:
        context["score"] = score
    if max_score is not None:
        context["max_score"] = max_score

    log_info(
        message="Processing completed successfully",
        video_id=video_id,
        test_type=test_type,
        context=context if context else None
    )


def log_quality_check(
    detection_rate: float,
    quality_score: int,
    video_id: Optional[str] = None,
    test_type: Optional[str] = None,
    passed: bool = True
) -> None:
    """
    What: 品質チェック結果ログ（定型）
    Why: 品質メトリクスの記録
    Design Decision: 検出率・品質スコアを含める

    Args:
        detection_rate: 姿勢検出率
        quality_score: 品質スコア（0-100）
        video_id: 動画ID（オプション）
        test_type: テストタイプ（オプション）
        passed: 品質チェック合格/不合格

    CRITICAL: 品質監視のため
    """
    level = "INFO" if passed else "WARNING"
    message = "Quality check passed" if passed else "Quality check failed - retake recommended"

    context = {
        "detection_rate": detection_rate,
        "quality_score": quality_score
    }

    if level == "INFO":
        log_info(message, video_id, test_type, context)
    else:
        log_warning(message, video_id, test_type, context)
