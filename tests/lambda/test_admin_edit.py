"""
Purpose: admin_edit Lambda関数のユニットテスト
Responsibility: チーム・選手編集APIのテスト
Dependencies: pytest, moto, boto3, sys, os
Created: 2025-10-29 by Claude Code
Decision Log: Phase 2.5 - Stage 1

CRITICAL: モックを使用してAWSサービスをシミュレート
"""

import os
import sys
import json
import pytest
from moto import mock_dynamodb
import boto3

# lambdaモジュールのパス追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda'))

# 環境変数設定（テスト前）
os.environ['TABLE_NAME'] = 'test-table'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'


# ========================================
# update_team tests
# ========================================

@mock_dynamodb
def test_update_team_success():
    """
    What: チーム編集エンドポイントのテスト（成功ケース）
    Why: チーム名変更機能の動作保証
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
            {'AttributeName': 'processed_at', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # 既存チームエンティティを作成
    table.put_item(Item={
        'video_id': 'TEAM#tm_sakae',
        'processed_at': 'METADATA',
        'teamId': 'tm_sakae',
        'teamSlug': 'sakae',
        'teamName': '栄フレッシュ',
        'teamCode': 'SAK001',
        'registrationUrl': 'https://thf.com/team-intake/tm_sakae',
        'qrCodeS3Key': 'qrcodes/tm_sakae.png'
    })

    # admin_editハンドラーをインポート
    from admin_edit.handler import update_team

    # リクエストイベント（teamName変更）
    event = {
        'httpMethod': 'PATCH',
        'pathParameters': {'teamId': 'tm_sakae'},
        'body': json.dumps({
            'teamName': '栄フレッシュ2025'
        })
    }

    # Lambda実行
    response = update_team(event, None)

    # 検証
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['data']['teamName'] == '栄フレッシュ2025'

    # DynamoDBに保存されたことを確認
    item = table.get_item(Key={'video_id': 'TEAM#tm_sakae', 'processed_at': 'METADATA'})['Item']
    assert item['teamName'] == '栄フレッシュ2025'
    # 他のフィールドは変更されていないことを確認
    assert item['teamSlug'] == 'sakae'
    assert item['registrationUrl'] == 'https://thf.com/team-intake/tm_sakae'


@mock_dynamodb
def test_update_team_not_found():
    """
    What: チーム編集エンドポイントのテスト（チーム未存在）
    Why: 404エラーハンドリングの動作保証
    """
    # DynamoDBテーブル作成
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='test-table',
        KeySchema=[
            {'AttributeName': 'video_id', 'KeyType': 'HASH'},
            {'AttributeName': 'processed_at', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'video_id', 'AttributeType': 'S'},
            {'AttributeName': 'processed_at', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # admin_editハンドラーをインポート
    from admin_edit.handler import update_team

    # リクエストイベント（存在しないチーム）
    event = {
        'httpMethod': 'PATCH',
        'pathParameters': {'teamId': 'tm_nonexistent'},
        'body': json.dumps({
            'teamName': '存在しないチーム'
        })
    }

    # Lambda実行
    response = update_team(event, None)

    # 検証
    assert response['statusCode'] == 404
    body = json.loads(response['body'])
    assert body['success'] is False
    assert 'not found' in body['error'].lower()


@mock_dynamodb
def test_update_team_forbidden_fields():
    """
    What: チーム編集エンドポイントのテスト（編集不可フィールド）
    Why: teamSlug等の変更を明示的に拒否
    """
    # DynamoDBテーブル作成
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    table = dynamodb.create_table(
        TableName='test-table',
        KeySchema=[
            {'AttributeName': 'video_id', 'KeyType': 'HASH'},
            {'AttributeName': 'processed_at', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'video_id', 'AttributeType': 'S'},
            {'AttributeName': 'processed_at', 'AttributeType': 'S'}
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    # 既存チームエンティティを作成
    table.put_item(Item={
        'video_id': 'TEAM#tm_sakae',
        'processed_at': 'METADATA',
        'teamId': 'tm_sakae',
        'teamSlug': 'sakae',
        'teamName': '栄フレッシュ'
    })

    # admin_editハンドラーをインポート
    from admin_edit.handler import update_team

    # リクエストイベント（teamSlug変更試行）
    event = {
        'httpMethod': 'PATCH',
        'pathParameters': {'teamId': 'tm_sakae'},
        'body': json.dumps({
            'teamSlug': 'newslug'  # 編集不可
        })
    }

    # Lambda実行
    response = update_team(event, None)

    # 検証
    assert response['statusCode'] == 400
    body = json.loads(response['body'])
    assert body['success'] is False
    assert 'not allowed' in body['error'].lower() or 'forbidden' in body['error'].lower()
