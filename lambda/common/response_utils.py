"""
Purpose: API Gateway レスポンスヘルパー
Responsibility: 統一的なHTTPレスポンス生成
Dependencies: json
Created: 2025-10-27 by Claude Code
Decision Log: ADR-018

CRITICAL: CORS対応とエラーハンドリングの一元管理
SECURITY REQUIREMENT: 本番環境ではALLOWED_ORIGINS環境変数でオリジン制限必須
"""

import json
import os
from decimal import Decimal
from typing import Dict, Any, Optional


class DecimalEncoder(json.JSONEncoder):
    """
    What: DynamoDB Decimal型のJSON変換エンコーダー
    Why: DynamoDBから取得した数値データ（Decimal型）をJSON化
    Design Decision: 整数はint、小数はfloatに変換（Phase 2.5 - Stage 1）

    CRITICAL: DynamoDBはすべての数値をDecimalで保存
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            # 整数の場合はint、小数の場合はfloatに変換
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)


def cors_headers(request_origin: Optional[str] = None) -> Dict[str, str]:
    """
    What: CORS対応のHTTPヘッダーを生成（環境別オリジン制限）
    Why: Wixフロントエンドからのクロスオリジンリクエストを許可しつつ、本番環境ではセキュリティを確保
    Design Decision: ALLOWED_ORIGINS環境変数でホワイトリスト管理（ADR-018, Phase 5）

    Args:
        request_origin: リクエストのOriginヘッダー値（API Gatewayから渡される）

    CRITICAL: 本番環境ではALLOWED_ORIGINS環境変数で特定オリジンのみ許可
    SECURITY REQUIREMENT: dev以外では'*'禁止、ホワイトリスト方式採用
    """
    environment = os.environ.get('ENVIRONMENT', 'dev')
    allowed_origins_str = os.environ.get('ALLOWED_ORIGINS', '*')

    # カンマ区切りでパース（前後の空白を除去）
    allowed_origins = [origin.strip() for origin in allowed_origins_str.split(',')]

    # dev環境では'*'を許可（開発効率優先）
    if environment == 'dev' and '*' in allowed_origins:
        allowed_origin = '*'
    else:
        # stg/prod環境: リクエストOriginがホワイトリストにあるか検証
        if request_origin and request_origin in allowed_origins:
            allowed_origin = request_origin
        else:
            # マッチしない場合は最初のホワイトリストオリジンを返す（デフォルト）
            allowed_origin = allowed_origins[0] if allowed_origins else '*'

    return {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': allowed_origin,
        'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
    }


def success_response(
    data: Any,
    status_code: int = 200,
    message: Optional[str] = None,
    request_origin: Optional[str] = None
) -> Dict[str, Any]:
    """
    What: 成功レスポンスを生成
    Why: API Gateway統合レスポンスの標準化
    Design Decision: dataとmessageを分離して柔軟性確保（ADR-018）

    Args:
        data: レスポンスデータ
        status_code: HTTPステータスコード（デフォルト: 200）
        message: オプションのメッセージ
        request_origin: リクエストのOriginヘッダー値（CORS制御用）

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
        'headers': cors_headers(request_origin=request_origin),
        'body': json.dumps(body, ensure_ascii=False, cls=DecimalEncoder)
    }


def error_response(
    error_message: str,
    status_code: int = 400,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    request_origin: Optional[str] = None
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
        request_origin: リクエストのOriginヘッダー値（CORS制御用）

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
        'headers': cors_headers(request_origin=request_origin),
        'body': json.dumps(body, ensure_ascii=False, cls=DecimalEncoder)
    }
