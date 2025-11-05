"""
Purpose: 動画アップロードURL生成Lambda関数
Responsibility: S3 Pre-signed URL生成とJWT認証
Dependencies: boto3, sys, json, datetime
Created: 2025-10-27 by Claude Code
Decision Log: ADR-018

CRITICAL: 15分有効期限とJWT認証必須
"""

import os
import sys
import json
import boto3
import time
from datetime import datetime
from typing import Dict, Any

# 共通モジュールのパス追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common.response_utils import success_response, error_response
from common.validators import validate_required_fields
from common.jwt_utils import verify_jwt, extract_bearer_token
from common.structured_logging import get_logger


logger = get_logger()


def generate_s3_key(
    player_id: str,
    test_type: str,
    timestamp: str
) -> str:
    """
    What: S3オブジェクトキー生成
    Why: 一意なパス構造でファイル整理
    Design Decision: videos/{playerId}/{testType}/{timestamp}.mp4（ADR-018）

    Args:
        player_id: 選手ID（例: plr_sakae_19）
        test_type: テスト種別（例: single_leg_squat）
        timestamp: タイムスタンプ（例: 20251027-120000）

    Returns:
        S3キー（例: videos/plr_sakae_19/single_leg_squat/20251027-120000.mp4）

    CRITICAL: パス構造は変更禁止（Lambda処理パイプラインに依存）
    """
    return f"videos/{player_id}/{test_type}/{timestamp}.mp4"


def generate_presigned_upload_url(
    bucket_name: str,
    s3_key: str,
    expiration: int = 900
) -> str:
    """
    What: S3 Pre-signed URL生成
    Why: クライアントからの直接アップロード許可
    Design Decision: PUT操作、15分有効期限（ADR-018）

    Args:
        bucket_name: S3バケット名
        s3_key: S3オブジェクトキー
        expiration: 有効期限（秒、デフォルト: 900=15分）

    Returns:
        Pre-signed URL

    CRITICAL: 有効期限は15分以下（セキュリティポリシー）
    """
    s3 = boto3.client('s3')

    presigned_url = s3.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': bucket_name,
            'Key': s3_key,
            'ContentType': 'video/mp4'
        },
        ExpiresIn=expiration
    )

    return presigned_url


def get_upload_url(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    What: アップロードURL取得エンドポイント
    Why: 選手による動画アップロード準備
    Design Decision: POST /getUploadUrl（ADR-018）

    Request headers:
        Authorization: Bearer {jwt_token}

    Request body:
        {
            "testType": "single_leg_squat"
        }

    Response:
        {
            "success": true,
            "data": {
                "uploadUrl": "https://s3.amazonaws.com/...",
                "s3Key": "videos/plr_sakae_19/single_leg_squat/20251027-120000.mp4",
                "expiresIn": 900
            }
        }

    CRITICAL: JWT認証必須（選手本人のみアップロード可能）
    PHASE CORE LOGIC: Pre-signed URL生成の核心ロジック
    """
    start_time = time.perf_counter()
    request_id = getattr(context, 'aws_request_id', None) if context else None
    function_name = getattr(context, 'function_name', os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
    environment = os.environ.get('ENVIRONMENT', os.environ.get('STAGE', 'dev'))

    logger.set_context(
        request_id=request_id,
        environment=environment,
        function_name=function_name,
    )

    try:
        headers = event.get('headers', {}) or {}
        # CORS制御用にOriginヘッダーを取得
        request_origin = headers.get('Origin') or headers.get('origin')

        auth_header = headers.get('Authorization') or headers.get('authorization')
        logger.info(
            "Upload URL request received",
            payload={"hasAuthorization": auth_header is not None},
        )

        is_valid, token, error_msg = extract_bearer_token(auth_header)
        if not is_valid:
            logger.warning("Authorization token missing or invalid", payload={"reason": error_msg})
            return error_response(error_msg, 401, 'AUTH_REQUIRED', request_origin=request_origin)

        is_valid, payload, error_msg = verify_jwt(token)
        if not is_valid:
            logger.warning("JWT verification failed", payload={"reason": error_msg})
            return error_response(error_msg, 401, 'AUTH_FAILED', request_origin=request_origin)

        player_id = payload['playerId']
        team_id = payload['teamId']

        body = json.loads(event.get('body', '{}'))
        is_valid, error_msg = validate_required_fields(body, ['testType'])
        if not is_valid:
            logger.warning("Request validation error", payload={"reason": error_msg})
            return error_response(error_msg, 400, 'VALIDATION_ERROR', request_origin=request_origin)

        test_type = body['testType']
        logger.set_context(test_code=test_type)

        valid_test_types = [
            'single_leg_squat',
            'upper_body_swing',
            'skater_lunge',
            'cross_step',
            'stride_mimic',
            'push_pull',
            'jump_landing'
        ]

        if test_type not in valid_test_types:
            logger.warning(
                "Disallowed test type requested",
                payload={"testType": test_type},
            )
            return error_response(
                f"Invalid test type: {test_type}",
                400,
                'VALIDATION_ERROR',
                details={'validTestTypes': valid_test_types},
                request_origin=request_origin
            )

        timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
        s3_key = generate_s3_key(player_id, test_type, timestamp)

        bucket_name = os.environ.get('VIDEOS_BUCKET')
        if not bucket_name:
            raise ValueError("VIDEOS_BUCKET environment variable is not set")

        upload_url = generate_presigned_upload_url(
            bucket_name,
            s3_key,
            expiration=900
        )

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.metric(
            "PresignedUrlGenerationDuration",
            duration_ms,
            unit="Milliseconds",
        )
        logger.info(
            "Upload URL generated",
            payload={
                "s3Key": s3_key,
                "teamId": team_id,
                "expiresIn": 900,
            },
        )

        return success_response(
            data={
                'uploadUrl': upload_url,
                's3Key': s3_key,
                'playerId': player_id,
                'teamId': team_id,
                'testType': test_type,
                'expiresIn': 900
            },
            message='Upload URL generated successfully',
            request_origin=request_origin
        )

    except ValueError as e:
        logger.warning("Configuration error in upload URL handler", payload={"error": str(e)})
        # ValueError時はrequest_originが取得できている可能性があるため、tryスコープから参照
        origin = locals().get('request_origin')
        return error_response(str(e), 400, 'VALIDATION_ERROR', request_origin=origin)

    except Exception as e:
        logger.error(
            "Error generating upload URL",
            payload={"testType": locals().get('test_type')},
            exc_info=e,
        )
        origin = locals().get('request_origin')
        return error_response(
            'Internal server error',
            500,
            'INTERNAL_ERROR',
            request_origin=origin
        )
    finally:
        logger.clear_context()


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    What: Lambda エントリーポイント
    Why: API Gateway統合
    Design Decision: POSTメソッドのみサポート（ADR-018）

    CRITICAL: OPTIONSリクエストはCORS preflight対応
    """
    http_method = event.get('httpMethod', '')

    # CORS preflight
    if http_method == 'OPTIONS':
        return success_response(data=None, message='CORS preflight')

    # POST /getUploadUrl
    if http_method == 'POST':
        return get_upload_url(event, context)

    return error_response('Method not allowed', 405, 'METHOD_NOT_ALLOWED')
