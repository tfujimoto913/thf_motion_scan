"""
Purpose: DynamoDB関連のヘルパー関数
Responsibility: Decimal型変換など、DynamoDBデータの正規化処理
Dependencies: decimal
Created: 2025-11-02
Decision Log: convert_decimals関数を共通化（ADR-026）

CRITICAL: DynamoDBのDecimal型はpandasやJSONで扱えないため、必ず変換が必要
"""

from decimal import Decimal


def convert_decimals(obj):
    """
    What: DynamoDB Decimal型をfloatに再帰的に変換
    Why: DynamoDBはDecimal型を返すが、pandas/JSON/Streamlitでは扱えないため
    Design Decision: 再帰的変換で入れ子構造にも対応（ADR-026）

    CRITICAL: DataFrame作成前に必ず実行すること（Decimal型はpandas非対応）

    Args:
        obj: 変換対象（dict, list, Decimal, その他）

    Returns:
        Decimal型がfloatに変換されたオブジェクト
    """
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_decimals(value) for key, value in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj
