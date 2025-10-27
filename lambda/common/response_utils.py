"""
Purpose: API Gateway レスポンスヘルパー
Responsibility: 統一的なHTTPレスポンス生成
Dependencies: json
Created: 2025-10-27 by Claude Code
Decision Log: ADR-018

CRITICAL: CORS対応とエラーハンドリングの一元管理
"""

import json
from typing import Dict, Any, Optional


def cors_headers() -> Dict[str, str]:
    """
    What: CORS対応のHTTPヘッダーを生成
    Why: Wixフロントエンドからのクロスオリジンリクエストを許可
    Design Decision: 本番環境ではAccess-Control-Allow-Originを制限（ADR-018）

    CRITICAL: 本番環境では特定オリジンのみ許可すること
    """
    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',  # TODO: 本番環境では特定オリジンに制限
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }


def success_response(
    data: Any,
    status_code: int = 200,
    message: Optional[str] = None
) -> Dict[str, Any]:
    """
    What: 成功レスポンスを生成
    Why: API Gateway統合レスポンスの標準化
    Design Decision: dataとmessageを分離して柔軟性確保（ADR-018）

    Args:
        data: レスポンスデータ
        status_code: HTTPステータスコード（デフォルト: 200）
        message: オプションのメッセージ

    Returns:
        API Gateway統合レスポンス形式の辞書

    CRITICAL: statusCodeとbodyの構造は変更禁止（API Gateway仕様）
    """
    body = {'success': True}

    if message:
        body['message'] = message

    if data is not None:
        body['data'] = data

    return {
        'statusCode': status_code,
        'headers': cors_headers(),
        'body': json.dumps(body, ensure_ascii=False)
    }


def error_response(
    error_message: str,
    status_code: int = 400,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    What: エラーレスポンスを生成
    Why: エラーハンドリングの統一とクライアント側での適切なエラー処理
    Design Decision: error_code追加でエラー種別の識別を容易化（ADR-018）

    Args:
        error_message: エラーメッセージ
        status_code: HTTPステータスコード（デフォルト: 400）
        error_code: エラーコード（例: VALIDATION_ERROR, AUTH_FAILED）
        details: 追加のエラー詳細

    Returns:
        API Gateway統合レスポンス形式の辞書

    CRITICAL: error_messageに個人情報を含めない（ADR-013）
    """
    body = {
        'success': False,
        'error': error_message
    }

    if error_code:
        body['errorCode'] = error_code

    if details:
        body['details'] = details

    return {
        'statusCode': status_code,
        'headers': cors_headers(),
        'body': json.dumps(body, ensure_ascii=False)
    }
