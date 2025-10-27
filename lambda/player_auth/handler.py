"""
Purpose: 選手認証Lambda関数
Responsibility: 選手登録とJWT認証
Dependencies: boto3, bcrypt, sys, json, datetime
Created: 2025-10-27 by Claude Code
Decision Log: ADR-018

CRITICAL: パスワードハッシュ化必須（平文保存禁止）
"""

import os
import sys
import json
import bcrypt
from datetime import datetime
from typing import Dict, Any

# 共通モジュールのパス追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common.response_utils import success_response, error_response
from common.validators import (
    validate_required_fields,
    validate_jersey_number,
    validate_password,
    validate_player_id,
    validate_kana_name,
    validate_lateral_characteristic
)
from common.jwt_utils import generate_jwt
from common.dynamodb_utils import put_item, get_item, query_items


def hash_password(password: str) -> str:
    """
    What: パスワードハッシュ化
    Why: セキュリティ強化（平文保存禁止）
    Design Decision: bcrypt使用（ADR-018, ADR-013）

    Args:
        password: 平文パスワード

    Returns:
        ハッシュ化されたパスワード（UTF-8文字列）

    CRITICAL: bcrypt rounds=12 は変更禁止（セキュリティポリシー）
    SECURITY REQUIREMENT: 平文パスワードは保存禁止
    """
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)

    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    What: パスワード検証
    Why: ログイン認証
    Design Decision: bcrypt.checkpw使用（ADR-018）

    Args:
        password: 平文パスワード
        hashed: ハッシュ化されたパスワード

    Returns:
        検証成功時True

    CRITICAL: タイミング攻撃対策のため bcrypt 使用必須
    """
    return bcrypt.checkpw(
        password.encode('utf-8'),
        hashed.encode('utf-8')
    )


def check_jersey_duplicate(team_id: str, jersey_number: int) -> bool:
    """
    What: 背番号重複チェック
    Why: チーム内で背番号の一意性保証
    Design Decision: GSI2（TeamIndex）使用（ADR-018）

    Args:
        team_id: チームID（例: tm_sakae）
        jersey_number: 背番号

    Returns:
        重複時True

    CRITICAL: GSI2クエリは必須（メインテーブルのScanは禁止）
    """
    # GSI2: GSI2PK = TEAM#{teamId}, GSI2SK = JERSEY#{jerseyNumber}
    items = query_items(
        pk=f"TEAM#{team_id}",
        sk_prefix=f"JERSEY#{jersey_number:02d}",
        index_name='GSI2-index'
    )

    return len(items) > 0


def register_player(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    What: 選手登録エンドポイント
    Why: チーム専用URLからの選手情報登録
    Design Decision: POST /player/register（ADR-018）

    Request body:
        {
            "teamId": "tm_sakae",
            "jerseyNumber": 19,
            "firstName": "太郎",
            "lastName": "山田",
            "firstNameKana": "たろう",
            "lastNameKana": "やまだ",
            "birthDate": "2010-03-15",
            "dominantHand": "right",
            "dominantFoot": "left",
            "shootingHand": "right",
            "password": "secure123"
        }

    Response:
        {
            "success": true,
            "data": {
                "playerId": "plr_sakae_19",
                "teamId": "tm_sakae",
                "jerseyNumber": 19,
                "createdAt": "2025-10-27T12:00:00Z"
            }
        }

    CRITICAL: パスワードはハッシュ化して保存必須
    PHASE CORE LOGIC: 選手登録の核心ロジック
    """
    try:
        # リクエストボディ解析
        body = json.loads(event.get('body', '{}'))

        # 必須フィールド検証
        is_valid, error_msg = validate_required_fields(
            body,
            [
                'teamId', 'jerseyNumber',
                'firstName', 'lastName',
                'firstNameKana', 'lastNameKana',
                'birthDate',
                'dominantHand', 'dominantFoot', 'shootingHand',
                'password'
            ]
        )
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        team_id = body['teamId']
        jersey_number = body['jerseyNumber']
        first_name = body['firstName']
        last_name = body['lastName']
        first_name_kana = body['firstNameKana']
        last_name_kana = body['lastNameKana']
        birth_date = body['birthDate']
        dominant_hand = body['dominantHand'].lower()
        dominant_foot = body['dominantFoot'].lower()
        shooting_hand = body['shootingHand'].lower()
        password = body['password']

        # 背番号検証
        is_valid, error_msg = validate_jersey_number(jersey_number)
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        # パスワード検証
        is_valid, error_msg = validate_password(password)
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        # Kana名検証
        is_valid, error_msg = validate_kana_name(first_name_kana, "First name kana")
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        is_valid, error_msg = validate_kana_name(last_name_kana, "Last name kana")
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        # 身体特性検証
        is_valid, error_msg = validate_lateral_characteristic(dominant_hand, "Dominant hand")
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        is_valid, error_msg = validate_lateral_characteristic(dominant_foot, "Dominant foot")
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        is_valid, error_msg = validate_lateral_characteristic(shooting_hand, "Shooting hand")
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        # チーム存在確認
        team = get_item(f"TEAM#{team_id}", "METADATA")
        if not team:
            return error_response(
                f"Team not found: {team_id}",
                404,
                'TEAM_NOT_FOUND'
            )

        # 背番号重複チェック
        if check_jersey_duplicate(team_id, jersey_number):
            return error_response(
                f"Jersey number {jersey_number} already taken",
                409,
                'JERSEY_DUPLICATE'
            )

        # 選手ID生成
        team_slug = team['teamSlug']
        player_id = f"plr_{team_slug}_{jersey_number}"

        # 選手ID検証
        is_valid, error_msg = validate_player_id(player_id)
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        # パスワードハッシュ化
        hashed_password = hash_password(password)

        # DynamoDBにAthleteエンティティ作成
        created_at = datetime.utcnow().isoformat() + 'Z'

        athlete_item = {
            'video_id': f"ATHLETE#{player_id}",   # メインテーブルのHASHキー
            'processed_at': 'METADATA',            # メインテーブルのRANGEキー
            'playerId': player_id,
            'teamInfo': {
                'teamId': team_id,
                'jerseyNumber': jersey_number,
                'isTeamPlayer': True
            },
            'personalInfo': {
                'firstName': first_name,
                'lastName': last_name,
                'firstNameKana': first_name_kana,
                'lastNameKana': last_name_kana,
                'birthDate': birth_date
            },
            'bodyCharacteristics': {
                'dominantHand': dominant_hand,
                'dominantFoot': dominant_foot,
                'shootingHand': shooting_hand
            },
            'auth': {
                'passwordHash': hashed_password
            },
            'GSI2PK': f"TEAM#{team_id}",
            'GSI2SK': f"JERSEY#{jersey_number:02d}",
            'createdAt': created_at
        }

        put_item(athlete_item)

        # レスポンス（パスワードハッシュは含めない）
        return success_response(
            data={
                'playerId': player_id,
                'teamId': team_id,
                'jerseyNumber': jersey_number,
                'firstName': first_name,
                'lastName': last_name,
                'firstNameKana': first_name_kana,
                'lastNameKana': last_name_kana,
                'birthDate': birth_date,
                'bodyCharacteristics': {
                    'dominantHand': dominant_hand,
                    'dominantFoot': dominant_foot,
                    'shootingHand': shooting_hand
                },
                'createdAt': created_at
            },
            status_code=201,
            message='Player registered successfully'
        )

    except ValueError as e:
        return error_response(str(e), 400, 'VALIDATION_ERROR')

    except Exception as e:
        # CRITICAL: エラーログに個人情報を含めない（ADR-013）
        print(f"Error registering player: {str(e)}")
        return error_response(
            'Internal server error',
            500,
            'INTERNAL_ERROR'
        )


def login_player(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    What: 選手ログインエンドポイント
    Why: JWT発行による認証
    Design Decision: POST /player/login（ADR-018）

    Request body:
        {
            "playerId": "plr_sakae_19",
            "password": "secure123"
        }

    Response:
        {
            "success": true,
            "data": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "playerId": "plr_sakae_19",
                "teamId": "tm_sakae",
                "expiresIn": 3600
            }
        }

    CRITICAL: JWT有効期限は60分固定
    PHASE CORE LOGIC: JWT認証の核心ロジック
    """
    try:
        # リクエストボディ解析
        body = json.loads(event.get('body', '{}'))

        # 必須フィールド検証
        is_valid, error_msg = validate_required_fields(
            body,
            ['playerId', 'password']
        )
        if not is_valid:
            return error_response(error_msg, 400, 'VALIDATION_ERROR')

        player_id = body['playerId']
        password = body['password']

        # 選手情報取得
        athlete = get_item(f"ATHLETE#{player_id}", "METADATA")

        if not athlete:
            return error_response(
                'Invalid credentials',
                401,
                'AUTH_FAILED'
            )

        # パスワード検証
        hashed_password = athlete.get('auth', {}).get('passwordHash')

        if not hashed_password or not verify_password(password, hashed_password):
            return error_response(
                'Invalid credentials',
                401,
                'AUTH_FAILED'
            )

        # JWT生成
        team_id = athlete.get('teamInfo', {}).get('teamId')
        token = generate_jwt(player_id, team_id, expiration_minutes=60)

        # レスポンス
        return success_response(
            data={
                'token': token,
                'playerId': player_id,
                'teamId': team_id,
                'expiresIn': 3600  # seconds
            },
            message='Login successful'
        )

    except ValueError as e:
        return error_response(str(e), 400, 'VALIDATION_ERROR')

    except Exception as e:
        # CRITICAL: エラーログに個人情報を含めない（ADR-013）
        print(f"Error during login: {str(e)}")
        return error_response(
            'Internal server error',
            500,
            'INTERNAL_ERROR'
        )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    What: Lambda エントリーポイント
    Why: API Gateway統合
    Design Decision: パスベースのルーティング（ADR-018）

    CRITICAL: OPTIONSリクエストはCORS preflight対応
    """
    http_method = event.get('httpMethod', '')
    path = event.get('path', '')

    # CORS preflight
    if http_method == 'OPTIONS':
        return success_response(data=None, message='CORS preflight')

    # POST /player/register
    if http_method == 'POST' and path.endswith('/register'):
        return register_player(event, context)

    # POST /player/login
    if http_method == 'POST' and path.endswith('/login'):
        return login_player(event, context)

    return error_response('Method not allowed', 405, 'METHOD_NOT_ALLOWED')
