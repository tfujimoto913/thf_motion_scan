"""
Purpose: DynamoDB操作ユーティリティ
Responsibility: DynamoDBテーブルへのCRUD操作
Dependencies: boto3, os, typing
Created: 2025-10-27 by Claude Code
Decision Log: ADR-018

CRITICAL: テーブル名は環境変数管理必須（ADR-013）
"""

import os
import boto3
from typing import Dict, List, Any, Optional
from boto3.dynamodb.conditions import Key


def get_table():
    """
    What: DynamoDBテーブルリソース取得
    Why: Lambda環境変数からテーブル名取得
    Design Decision: boto3.resource使用で簡潔なAPI（ADR-018）

    Returns:
        DynamoDB Tableリソース

    CRITICAL: TABLE_NAME環境変数は必須（template.yamlで注入）
    """
    table_name = os.environ.get('TABLE_NAME')

    if not table_name:
        raise ValueError("TABLE_NAME environment variable is not set")

    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    return table


def query_items(
    pk: str,
    sk_prefix: Optional[str] = None,
    index_name: Optional[str] = None,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    What: DynamoDB Query操作
    Why: PKとSKでの効率的な検索
    Design Decision: メインテーブルのキー名（video_id/processed_at）にマッピング（ADR-018）

    Args:
        pk: パーティションキー値（内部でvideo_idにマッピング）
        sk_prefix: ソートキープレフィックス（内部でprocessed_atにマッピング、省略時は完全一致）
        index_name: GSI名（省略時はメインテーブル）
        limit: 最大取得件数（省略時は全件）

    Returns:
        アイテムのリスト

    CRITICAL: メインテーブルはvideo_id/processed_atがキー
    CRITICAL: GSI2（TeamIndex）使用時はindex_name='GSI2-index'指定でGSI2PK/GSI2SK使用
    """
    table = get_table()

    # KeyConditionExpression構築
    # メインテーブル使用時はvideo_id/processed_at、GSI使用時は各GSIのキー名
    if index_name == 'GSI2-index':
        # GSI2: TeamIndex
        if sk_prefix:
            key_condition = Key('GSI2PK').eq(pk) & Key('GSI2SK').begins_with(sk_prefix)
        else:
            key_condition = Key('GSI2PK').eq(pk)
    else:
        # メインテーブル: video_id/processed_at
        if sk_prefix:
            key_condition = Key('video_id').eq(pk) & Key('processed_at').begins_with(sk_prefix)
        else:
            key_condition = Key('video_id').eq(pk)

    # Query実行
    query_kwargs = {'KeyConditionExpression': key_condition}

    if index_name:
        query_kwargs['IndexName'] = index_name

    if limit:
        query_kwargs['Limit'] = limit

    response = table.query(**query_kwargs)

    return response.get('Items', [])


def put_item(item: Dict[str, Any]) -> bool:
    """
    What: DynamoDB Put操作
    Why: 新規アイテム作成
    Design Decision: 上書き許可（既存アイテムは置換）（ADR-018）

    Args:
        item: 作成するアイテム（PK, SKは必須）

    Returns:
        成功時True

    CRITICAL: PK, SKは必須フィールド（呼び出し側で検証）
    """
    table = get_table()

    table.put_item(Item=item)

    return True


def update_item(
    pk: str,
    sk: str,
    update_expression: str,
    expression_attribute_values: Dict[str, Any],
    expression_attribute_names: Optional[Dict[str, str]] = None
) -> bool:
    """
    What: DynamoDB Update操作
    Why: 既存アイテムの部分更新
    Design Decision: UpdateExpression使用で柔軟な更新、メインテーブルのキー名にマッピング（ADR-018）

    Args:
        pk: パーティションキー値（内部でvideo_idにマッピング）
        sk: ソートキー値（内部でprocessed_atにマッピング）
        update_expression: 更新式（例: "SET #attr1 = :val1, #attr2 = :val2"）
        expression_attribute_values: 値マッピング（例: {':val1': 'new_value'}）
        expression_attribute_names: 属性名マッピング（例: {'#attr1': 'reserved_keyword'}）

    Returns:
        成功時True

    CRITICAL: 予約語（例: name, status）はexpression_attribute_names必須
    CRITICAL: メインテーブルはvideo_id/processed_atがキー
    """
    table = get_table()

    update_kwargs = {
        'Key': {'video_id': pk, 'processed_at': sk},
        'UpdateExpression': update_expression,
        'ExpressionAttributeValues': expression_attribute_values
    }

    if expression_attribute_names:
        update_kwargs['ExpressionAttributeNames'] = expression_attribute_names

    table.update_item(**update_kwargs)

    return True


def get_item(pk: str, sk: str) -> Optional[Dict[str, Any]]:
    """
    What: DynamoDB GetItem操作
    Why: 単一アイテムの取得
    Design Decision: 存在しない場合はNone返却、メインテーブルのキー名にマッピング（ADR-018）

    Args:
        pk: パーティションキー値（内部でvideo_idにマッピング）
        sk: ソートキー値（内部でprocessed_atにマッピング）

    Returns:
        アイテム（存在しない場合はNone）

    CRITICAL: Noneチェック必須（呼び出し側で404判定）
    CRITICAL: メインテーブルはvideo_id/processed_atがキー
    """
    table = get_table()

    response = table.get_item(Key={'video_id': pk, 'processed_at': sk})

    return response.get('Item')


def batch_write_items(items: List[Dict[str, Any]]) -> bool:
    """
    What: DynamoDB BatchWriteItem操作
    Why: 複数アイテムの一括書き込み（パフォーマンス向上）
    Design Decision: 25件ごとに分割（DynamoDB制限）（ADR-018）

    Args:
        items: 書き込むアイテムのリスト

    Returns:
        成功時True

    CRITICAL: 25件制限超過時は自動分割処理
    """
    table = get_table()
    table_name = table.name

    # 25件ごとに分割
    batch_size = 25
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]

        with table.batch_writer() as writer:
            for item in batch:
                writer.put_item(Item=item)

    return True
