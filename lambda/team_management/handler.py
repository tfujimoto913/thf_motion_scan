"""
Purpose: チーム管理Lambda関数
Responsibility: チーム作成とQRコード生成
Dependencies: boto3, qrcode, io, datetime, sys
Created: 2025-10-27 by Claude Code
Decision Log: ADR-018

CRITICAL: QRコード生成とS3保存の統合処理
"""

import os
import sys
import json
import qrcode
import boto3
from io import BytesIO
from datetime import datetime
from typing import Dict, Any

# 共通モジュールのパス追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common.response_utils import success_response, error_response
from common.validators import validate_required_fields, validate_team_id
from common.dynamodb_utils import put_item, get_item


def generate_team_id(team_slug: str) -> str:
    """
    What: チームID生成
    Why: DynamoDB PKに使用する一意な識別子
    Design Decision: tm_{teamSlug} 形式（ADR-018）

    Args:
        team_slug: チームスラッグ（例: sakae）

    Returns:
        チームID（例: tm_sakae）

    CRITICAL: 形式変更禁止（DynamoDB PKに使用）
    """
    return f"tm_{team_slug}"


def generate_team_code(team_slug: str) -> str:
    """
    What: チームコード生成
    Why: 選手登録時の確認用コード
    Design Decision: {SLUG}-{YY}{SEASON} 形式（ADR-018）

    Args:
        team_slug: チームスラッグ（例: sakae）

    Returns:
        チームコード（例: SAKAE-25FA）

    Season codes: FA=Fall, WI=Winter, SP=Spring, SU=Summer
    """
    now = datetime.now()
    year_code = now.strftime('%y')  # 25

    # シーズンコード判定（月ベース）
    month = now.month
    if month in [9, 10, 11]:
        season_code = 'FA'  # Fall
    elif month in [12, 1, 2]:
        season_code = 'WI'  # Winter
    elif month in [3, 4, 5]:
        season_code = 'SP'  # Spring
    else:
        season_code = 'SU'  # Summer

    team_code = f"{team_slug.upper()}-{year_code}{season_code}"

    return team_code


def generate_qr_code(registration_url: str) -> BytesIO:
    """
    What: QRコード画像生成
    Why: チーム登録URL配布用
    Design Decision: PNG形式、300x300px（ADR-018）

    Args:
        registration_url: 登録URL（例: https://thf.com/team-intake/sakae）

    Returns:
        PNG画像のBytesIOオブジェクト

    CRITICAL: box_size=10, border=4 は変更禁止（可読性保証）
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    qr.add_data(registration_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # PNG形式でBytesIOに変換
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    return img_buffer


def upload_qr_code_to_s3(team_id: str, img_buffer: BytesIO) -> str:
    """
    What: QRコードをS3にアップロード
    Why: Wixダッシュボードでの表示用
    Design Decision: qrcodes/{team_id}.png パス（ADR-018）

    Args:
        team_id: チームID（例: tm_sakae）
        img_buffer: PNG画像のBytesIO

    Returns:
        S3キー（例: qrcodes/tm_sakae.png）

    CRITICAL: バケット名は環境変数管理必須（ADR-013）
    """
    bucket_name = os.environ.get('QRCODE_BUCKET')

    if not bucket_name:
        raise ValueError("QRCODE_BUCKET environment variable is not set")

    s3 = boto3.client('s3')
    s3_key = f"qrcodes/{team_id}.png"

    s3.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=img_buffer,
        ContentType='image/png'
    )

    return s3_key


def create_team(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    What: チーム作成エンドポイント
    Why: THF管理者によるチーム一括登録開始
    Design Decision: POST /admin/createTeam（ADR-018）

    Request body:
        {
            "teamSlug": "sakae",
            "teamName": "栄フレッシュ",
            "registrationBaseUrl": "https://thf.com/team-intake"
        }

    Response:
        {
            "success": true,
            "data": {
                "teamId": "tm_sakae",
                "teamCode": "SAKAE-25FA",
                "teamSlug": "sakae",
                "registrationUrl": "https://thf.com/team-intake/sakae",
                "qrCodeS3Key": "qrcodes/tm_sakae.png",
                "createdAt": "2025-10-27T12:00:00Z"
            }
        }

    CRITICAL: 管理者権限チェックは将来実装（現在はオープン）
    PHASE CORE LOGIC: チーム作成の核心ロジック
    """
    try:
        # リクエストボディ解析
        body = json.loads(event.get('body', '{}'))

        # 必須フィールド検証
        is_valid, error_msg = validate_required_fields(
            body,
            ['teamSlug', 'teamName', 'registrationBaseUrl']
        )
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        team_slug = body['teamSlug'].lower()
        team_name = body['teamName']
        registration_base_url = body['registrationBaseUrl']

        # チームID生成
        team_id = generate_team_id(team_slug)

        # チームID検証
        is_valid, error_msg = validate_team_id(team_id)
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        # 既存チェック（メインテーブルのキー構造に合わせる）
        existing_team = get_item(f"TEAM#{team_id}", "METADATA")
        if existing_team:
            return error_response(
                f"Team already exists: {team_id}",
                409,
                'TEAM_ALREADY_EXISTS'
            )

        # チームコード生成
        team_code = generate_team_code(team_slug)

        # 登録URL生成
        registration_url = f"{registration_base_url}/{team_slug}"

        # QRコード生成
        img_buffer = generate_qr_code(registration_url)

        # S3にアップロード
        qr_code_s3_key = upload_qr_code_to_s3(team_id, img_buffer)

        # DynamoDBにTeamエンティティ作成
        created_at = datetime.utcnow().isoformat() + 'Z'

        team_item = {
            'video_id': f"TEAM#{team_id}",      # メインテーブルのHASHキー
            'processed_at': 'METADATA',          # メインテーブルのRANGEキー
            'teamId': team_id,
            'teamCode': team_code,
            'teamSlug': team_slug,
            'teamName': team_name,
            'registrationUrl': registration_url,
            'qrCodeS3Key': qr_code_s3_key,
            'createdAt': created_at
        }

        put_item(team_item)

        # レスポンス
        return success_response(
            data={
                'teamId': team_id,
                'teamCode': team_code,
                'teamSlug': team_slug,
                'teamName': team_name,
                'registrationUrl': registration_url,
                'qrCodeS3Key': qr_code_s3_key,
                'createdAt': created_at
            },
            status_code=201,
            message='Team created successfully'
        )

    except ValueError as e:
        return error_response(str(e), 400, 'VALIDATION_ERROR')

    except Exception as e:
        # CRITICAL: エラーログに個人情報を含めない（ADR-013）
        print(f"Error creating team: {str(e)}")
        return error_response(
            'Internal server error',
            500,
            'INTERNAL_ERROR'
        )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    What: Lambda エントリーポイント
    Why: API Gateway統合
    Design Decision: HTTPメソッドベースのルーティング（ADR-018）

    CRITICAL: OPTIONSリクエストはCORS preflight対応
    """
    http_method = event.get('httpMethod', '')

    # CORS preflight
    if http_method == 'OPTIONS':
        return success_response(data=None, message='CORS preflight')

    # POST /admin/createTeam
    if http_method == 'POST':
        return create_team(event, context)

    return error_response('Method not allowed', 405, 'METHOD_NOT_ALLOWED')
