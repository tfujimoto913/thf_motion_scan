"""
Purpose: JWT認証ユーティリティ
Responsibility: JWT生成と検証
Dependencies: jwt (PyJWT), os, datetime
Created: 2025-10-27 by Claude Code
Decision Log: ADR-018

CRITICAL: JWT_SECRET_KEYは環境変数管理必須（ADR-013）
"""

import os
import jwt
import json
import boto3
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple


def get_jwt_secret() -> str:
    """
    What: JWT署名用シークレットキー取得
    Why: Secrets Managerからシークレット取得（ハードコード禁止）
    Design Decision: AWS Secrets Manager統合（ADR-018, ADR-013）

    Returns:
        JWT署名用シークレットキー

    CRITICAL: 本番環境ではAWS Secrets Manager使用必須
    SECURITY REQUIREMENT: JWT_SECRET_KEYは環境変数のみ（ローカル）、Secrets Manager（本番）
    """
    # ローカル環境: 環境変数から取得
    local_secret = os.environ.get('JWT_SECRET_KEY')
    if local_secret:
        return local_secret

    # 本番環境: Secrets Managerから取得
    secret_name = os.environ.get('JWT_SECRET_NAME')
    if not secret_name:
        raise ValueError("JWT_SECRET_NAME environment variable is not set")

    try:
        session = boto3.session.Session()
        client = session.client(service_name='secretsmanager')

        get_secret_value_response = client.get_secret_value(SecretId=secret_name)

        # JSON形式のシークレット取得
        secret_string = get_secret_value_response['SecretString']
        secret_dict = json.loads(secret_string)

        # 'secret'キーから取得
        jwt_secret = secret_dict.get('secret')

        if not jwt_secret:
            raise ValueError(f"'secret' key not found in Secrets Manager: {secret_name}")

        return jwt_secret

    except Exception as e:
        raise ValueError(f"Failed to retrieve JWT secret from Secrets Manager: {str(e)}")


def generate_jwt(
    player_id: str,
    team_id: str,
    expiration_minutes: int = 60
) -> str:
    """
    What: JWT生成
    Why: 選手認証トークン発行
    Design Decision: HS256アルゴリズム、60分有効期限（ADR-018）

    Args:
        player_id: 選手ID（例: plr_sakae_19）
        team_id: チームID（例: tm_sakae）
        expiration_minutes: 有効期限（分、デフォルト: 60）

    Returns:
        JWT文字列

    CRITICAL: 有効期限は延長禁止（セキュリティポリシー）
    """
    secret = get_jwt_secret()

    # ペイロード構築
    payload = {
        'playerId': player_id,
        'teamId': team_id,
        'iat': datetime.utcnow(),  # issued at
        'exp': datetime.utcnow() + timedelta(minutes=expiration_minutes)  # expiration
    }

    # JWT生成（HS256アルゴリズム）
    token = jwt.encode(payload, secret, algorithm='HS256')

    return token


def verify_jwt(token: str) -> Tuple[bool, Optional[Dict], Optional[str]]:
    """
    What: JWT検証
    Why: 選手認証トークンの妥当性確認
    Design Decision: 有効期限切れとシグネチャ検証の両対応（ADR-018）

    Args:
        token: JWT文字列

    Returns:
        (is_valid, payload, error_message) のタプル

    Payload structure (valid token):
        {
            'playerId': 'plr_sakae_19',
            'teamId': 'tm_sakae',
            'iat': 1698450000,
            'exp': 1698453600
        }

    CRITICAL: 検証失敗時はエラーメッセージを返す（セキュリティログ用）
    """
    secret = get_jwt_secret()

    try:
        # JWT検証（有効期限とシグネチャ）
        payload = jwt.decode(token, secret, algorithms=['HS256'])
        return True, payload, None

    except jwt.ExpiredSignatureError:
        return False, None, "Token has expired"

    except jwt.InvalidTokenError as e:
        return False, None, f"Invalid token: {str(e)}"


def extract_bearer_token(authorization_header: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    What: Authorization ヘッダーからBearerトークン抽出
    Why: API Gateway Authorization ヘッダーの標準化
    Design Decision: Bearer {token} 形式のみサポート（ADR-018）

    Args:
        authorization_header: Authorization ヘッダー値（例: "Bearer eyJ..."）

    Returns:
        (is_valid, token, error_message) のタプル

    CRITICAL: Bearer形式以外は拒否（セキュリティポリシー）
    """
    if not authorization_header:
        return False, None, "Authorization header is missing"

    parts = authorization_header.split(' ')

    if len(parts) != 2:
        return False, None, "Invalid Authorization header format"

    if parts[0] != 'Bearer':
        return False, None, "Authorization must use Bearer scheme"

    token = parts[1]

    if not token:
        return False, None, "Token is empty"

    return True, token, None
