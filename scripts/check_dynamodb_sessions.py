#!/usr/bin/env python3
"""
Purpose: DynamoDBのセッションデータ確認スクリプト
Responsibility: DynamoDBテーブルのデータ存在確認とサマリー表示
Dependencies: boto3, sys
Created: 2025-11-02
Decision Log: デバッグ・運用支援ツール（ADR-026）

CRITICAL: AWS認証情報が設定されていることを前提
"""

import sys
import boto3
from decimal import Decimal
from pathlib import Path

# dashboard/ を sys.path に追加
dashboard_path = Path(__file__).parent.parent / "dashboard"
sys.path.insert(0, str(dashboard_path))

from config import get_resource_names, get_available_environments


def convert_decimals(obj):
    """DynamoDB Decimal型をfloat/intに変換"""
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_decimals(value) for key, value in obj.items()}
    elif isinstance(obj, Decimal):
        # 整数の場合はint、それ以外はfloat
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    return obj


def main():
    """
    What: DynamoDBのセッションデータを確認
    Why: データが実際に保存されているか、エラー原因を特定するため
    Design Decision: シンプルなCLIツール（ADR-026）
    """
    print("=" * 60)
    print("DynamoDB セッションデータ確認ツール")
    print("=" * 60)

    # 環境選択
    envs = get_available_environments()
    if not envs:
        print("❌ エラー: 利用可能な環境が見つかりません")
        print("💡 AWS認証情報を確認してください")
        return

    print(f"\n利用可能な環境: {', '.join(envs)}")
    env = envs[0]
    print(f"使用環境: {env}")

    # リソース名取得
    try:
        resources = get_resource_names(env)
        table_name = resources['table']
        print(f"DynamoDBテーブル: {table_name}")
    except Exception as e:
        print(f"❌ エラー: リソース名取得失敗 - {e}")
        return

    # DynamoDB接続
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(table_name)
        print("✅ DynamoDB接続成功")
    except Exception as e:
        print(f"❌ エラー: DynamoDB接続失敗 - {e}")
        return

    # データ取得
    try:
        print("\nデータをスキャン中...")
        response = table.scan()
        items = response.get('Items', [])

        # ページネーション対応
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        print(f"✅ 取得完了: {len(items)}件")

    except Exception as e:
        print(f"❌ エラー: データ取得失敗 - {e}")
        return

    # データ解析
    if not items:
        print("\n⚠️ データが1件も見つかりませんでした")
        print("💡 対処法:")
        print("  - 動画をアップロードしてデータを作成してください")
        print("  - 別の環境（dev/prod）を確認してください")
        return

    # Decimal型変換
    items_converted = [convert_decimals(item) for item in items]

    # メタデータとテストデータを分類
    metadata_items = [
        item for item in items_converted
        if str(item.get('video_id', '')).startswith('METADATA')
    ]
    test_items = [
        item for item in items_converted
        if not str(item.get('video_id', '')).startswith('METADATA')
    ]

    print(f"\n📊 データサマリー:")
    print(f"  - 総件数: {len(items_converted)}件")
    print(f"  - メタデータ: {len(metadata_items)}件")
    print(f"  - テスト結果: {len(test_items)}件")

    # セッション集計
    if test_items:
        athletes = set()
        sessions = set()
        test_types = set()

        for item in test_items:
            athlete_id = item.get('athlete_id')
            session_id = item.get('session_id')
            test_type = item.get('test_type')

            if athlete_id:
                athletes.add(athlete_id)
            if session_id:
                sessions.add((athlete_id, session_id))
            if test_type:
                test_types.add(test_type)

        print(f"\n📈 セッション統計:")
        print(f"  - 選手数: {len(athletes)}人")
        print(f"  - セッション数: {len(sessions)}件")
        print(f"  - 種目種類: {len(test_types)}種類")

        print(f"\n👤 選手一覧:")
        for athlete in sorted(athletes):
            athlete_sessions = [s for s in sessions if s[0] == athlete]
            print(f"  - {athlete}: {len(athlete_sessions)}セッション")

        print(f"\n🏋️ 種目一覧:")
        for test_type in sorted(test_types):
            count = sum(1 for item in test_items if item.get('test_type') == test_type)
            print(f"  - {test_type}: {count}件")

    # 最新5件の表示
    if test_items:
        print(f"\n📋 最新5件:")
        sorted_items = sorted(
            test_items,
            key=lambda x: x.get('uploaded_at', ''),
            reverse=True
        )[:5]

        for i, item in enumerate(sorted_items, 1):
            athlete_id = item.get('athlete_id', 'N/A')
            session_id = item.get('session_id', 'N/A')
            test_type = item.get('test_type', 'N/A')
            uploaded_at = item.get('uploaded_at', 'N/A')
            grand_total = item.get('grand_total', 'N/A')

            print(f"  {i}. {athlete_id} / {session_id}")
            print(f"     種目: {test_type}, スコア: {grand_total}, 日時: {uploaded_at}")

    print("\n" + "=" * 60)
    print("✅ 確認完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
