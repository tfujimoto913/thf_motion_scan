"""
Purpose: Lambda関数ハンドラーの統合テスト
Responsibility: team_management, player_auth, upload_urlのエンドツーエンドテスト
Dependencies: pytest, moto, boto3, sys, os
Created: 2025-10-27 by Claude Code
Decision Log: ADR-018

CRITICAL: モックを使用してAWSサービスをシミュレート
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock
from moto import mock_dynamodb, mock_s3
import boto3

# lambdaモジュールのパス追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda'))

# 環境変数設定（テスト前）
os.environ['TABLE_NAME'] = 'test-table'
os.environ['QRCODE_BUCKET'] = 'test-qrcode-bucket'
os.environ['VIDEOS_BUCKET'] = 'test-videos-bucket'
os.environ['JWT_SECRET_KEY'] = 'test-secret-key'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


# ========================================
# team_management tests
# ========================================

@mock_dynamodb
@mock_s3
def test_create_team_success():
    """
    What: チーム作成エンドポイントのテスト（成功ケース）
    Why: チーム作成機能の動作保証
    """
    # DynamoDBテーブル作成
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='test-table',
        KeySchema=[
            {'AttributeName': 'PK', 'KeyType': 'HASH'},
            {'AttributeName': 'SK', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'PK', 'AttributeType': 'S'},
            {'AttributeName': 'SK', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # S3バケット作成
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket='test-qrcode-bucket')

    # team_managementハンドラーをインポート
    from team_management.handler import lambda_handler

    # リクエストイベント
    event = {
        'httpMethod': 'POST',
        'body': json.dumps({
            'teamSlug': 'sakae',
            'teamName': '栄フレッシュ',
            'registrationBaseUrl': 'https://thf.com/team-intake'
        })
    }

    # Lambda実行
    response = lambda_handler(event, None)

    # 検証
    assert response['statusCode'] == 201
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['data']['teamId'] == 'tm_sakae'
    assert body['data']['teamSlug'] == 'sakae'
    assert 'qrCodeS3Key' in body['data']


# ========================================
# player_auth tests
# ========================================

@mock_dynamodb
def test_register_player_success():
    """
    What: 選手登録エンドポイントのテスト（成功ケース）
    Why: 選手登録機能の動作保証
    """
    # DynamoDBテーブル作成（ADR-020: video_id/processed_atキー構造）
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='test-table',
        KeySchema=[
            {'AttributeName': 'video_id', 'KeyType': 'HASH'},
            {'AttributeName': 'processed_at', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'video_id', 'AttributeType': 'S'},
            {'AttributeName': 'processed_at', 'AttributeType': 'S'},
            {'AttributeName': 'GSI2PK', 'AttributeType': 'S'},
            {'AttributeName': 'GSI2SK', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'GSI2-index',
                'KeySchema': [
                    {'AttributeName': 'GSI2PK', 'KeyType': 'HASH'},
                    {'AttributeName': 'GSI2SK', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # チームエンティティを作成
    table.put_item(Item={
        'video_id': 'TEAM#tm_sakae',
        'processed_at': 'METADATA',
        'teamId': 'tm_sakae',
        'teamSlug': 'sakae',
        'teamName': '栄フレッシュ'
    })

    # player_authハンドラーをインポート
    from player_auth.handler import lambda_handler

    # リクエストイベント
    event = {
        'httpMethod': 'POST',
        'path': '/player/register',
        'body': json.dumps({
            'teamId': 'tm_sakae',
            'jerseyNumber': 19,
            'firstName': '太郎',
            'lastName': '山田',
            'firstNameKana': 'たろう',
            'lastNameKana': 'やまだ',
            'birthDate': '2010-03-15',
            'dominantHand': 'right',
            'dominantFoot': 'left',
            'shootingHand': 'right',
            'password': 'secure123'
        })
    }

    # Lambda実行
    response = lambda_handler(event, None)

    # 検証
    assert response['statusCode'] == 201
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['data']['playerId'] == 'plr_sakae_19'
    assert body['data']['teamId'] == 'tm_sakae'
    # heightはオプショナルなので、含まれていてもNoneでもOK
    assert body['data']['bodyCharacteristics']['height'] is None


@mock_dynamodb
def test_register_player_with_height():
    """
    What: 選手登録エンドポイントのテスト（身長付き）
    Why: 身長フィールドの動作保証（Phase 2.5 - Stage 1）
    """
    # DynamoDBテーブル作成（ADR-020: video_id/processed_atキー構造）
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='test-table',
        KeySchema=[
            {'AttributeName': 'video_id', 'KeyType': 'HASH'},
            {'AttributeName': 'processed_at', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'video_id', 'AttributeType': 'S'},
            {'AttributeName': 'processed_at', 'AttributeType': 'S'},
            {'AttributeName': 'GSI2PK', 'AttributeType': 'S'},
            {'AttributeName': 'GSI2SK', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'GSI2-index',
                'KeySchema': [
                    {'AttributeName': 'GSI2PK', 'KeyType': 'HASH'},
                    {'AttributeName': 'GSI2SK', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # チームエンティティを作成
    table.put_item(Item={
        'video_id': 'TEAM#tm_sakae',
        'processed_at': 'METADATA',
        'teamId': 'tm_sakae',
        'teamSlug': 'sakae',
        'teamName': '栄フレッシュ'
    })

    # player_authハンドラーをインポート
    from player_auth.handler import lambda_handler

    # リクエストイベント（身長付き）
    event = {
        'httpMethod': 'POST',
        'path': '/player/register',
        'body': json.dumps({
            'teamId': 'tm_sakae',
            'jerseyNumber': 20,
            'firstName': '花子',
            'lastName': '佐藤',
            'firstNameKana': 'はなこ',
            'lastNameKana': 'さとう',
            'birthDate': '2011-05-20',
            'dominantHand': 'left',
            'dominantFoot': 'right',
            'shootingHand': 'left',
            'height': 165,
            'password': 'secure456'
        })
    }

    # Lambda実行
    response = lambda_handler(event, None)

    # 検証
    assert response['statusCode'] == 201
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['data']['playerId'] == 'plr_sakae_20'
    assert body['data']['bodyCharacteristics']['height'] == 165


@mock_dynamodb
def test_login_player_success():
    """
    What: 選手ログインエンドポイントのテスト（成功ケース）
    Why: JWT発行機能の動作保証
    """
    # DynamoDBテーブル作成
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='test-table',
        KeySchema=[
            {'AttributeName': 'PK', 'KeyType': 'HASH'},
            {'AttributeName': 'SK', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'PK', 'AttributeType': 'S'},
            {'AttributeName': 'SK', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # bcryptでパスワードハッシュ生成
    import bcrypt
    hashed_password = bcrypt.hashpw('secure123'.encode('utf-8'), bcrypt.gensalt(rounds=12))

    # 選手エンティティを作成
    table.put_item(Item={
        'PK': 'ATHLETE#plr_sakae_19',
        'SK': 'METADATA',
        'playerId': 'plr_sakae_19',
        'teamInfo': {
            'teamId': 'tm_sakae',
            'jerseyNumber': 19
        },
        'auth': {
            'passwordHash': hashed_password.decode('utf-8')
        }
    })

    # player_authハンドラーをインポート
    from player_auth.handler import lambda_handler

    # リクエストイベント
    event = {
        'httpMethod': 'POST',
        'path': '/player/login',
        'body': json.dumps({
            'playerId': 'plr_sakae_19',
            'password': 'secure123'
        })
    }

    # Lambda実行
    response = lambda_handler(event, None)

    # 検証
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert 'token' in body['data']
    assert body['data']['playerId'] == 'plr_sakae_19'


# ========================================
# upload_url tests
# ========================================

@mock_s3
def test_get_upload_url_success():
    """
    What: アップロードURL取得エンドポイントのテスト（成功ケース）
    Why: Pre-signed URL生成機能の動作保証
    """
    # S3バケット作成
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket='test-videos-bucket')

    # JWT生成
    from common.jwt_utils import generate_jwt
    token = generate_jwt('plr_sakae_19', 'tm_sakae', expiration_minutes=60)

    # upload_urlハンドラーをインポート
    from upload_url.handler import lambda_handler

    # リクエストイベント
    event = {
        'httpMethod': 'POST',
        'headers': {
            'Authorization': f'Bearer {token}'
        },
        'body': json.dumps({
            'testType': 'single_leg_squat'
        })
    }

    # Lambda実行
    response = lambda_handler(event, None)

    # 検証
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert 'uploadUrl' in body['data']
    assert 's3Key' in body['data']
    assert body['data']['playerId'] == 'plr_sakae_19'


def test_get_upload_url_unauthorized():
    """
    What: アップロードURL取得エンドポイントのテスト（認証失敗ケース）
    Why: JWT認証の動作保証
    """
    # upload_urlハンドラーをインポート
    from upload_url.handler import lambda_handler

    # リクエストイベント（Authorizationヘッダーなし）
    event = {
        'httpMethod': 'POST',
        'headers': {},
        'body': json.dumps({
            'testType': 'single_leg_squat'
        })
    }

    # Lambda実行
    response = lambda_handler(event, None)

    # 検証
    assert response['statusCode'] == 401
    body = json.loads(response['body'])
    assert body['success'] is False
