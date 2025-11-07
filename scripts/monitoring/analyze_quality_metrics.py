#!/usr/bin/env python3
"""
Purpose: DynamoDB品質メトリクス分析スクリプト
Responsibility: motion-scan-resultsテーブルから品質メトリクスを抽出・分析
Dependencies: boto3, numpy
Created: 2025-11-06 by Claude Code
Decision Log: ADR-024

What: detection_rate, quality_score等の品質メトリクスを集計・分析
Why: CloudWatch MetricsにBCR/Kappa/OverrideRatioが存在しないため、
     DynamoDBから実データを取得して品質傾向を分析する必要がある

Design Decision:
- データ範囲: 2025-11-05以降（DynamoDB保存が正常化した日付）
- 出力: Markdown + JSON（docs/monitoring/quality_metrics_analysis.*）
- 統計: detection_rate（平均, P50, P95, 最小, 最大）
        quality_score（ヒストグラム10区間, P10/P25/P50/P75/P90）

CRITICAL: DynamoDB Scanはテーブル全体を読むため、大量データ時は注意
"""

import boto3
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List, Any, Optional
from collections import defaultdict
import numpy as np


# CRITICAL: DynamoDB Decimal型をfloatに変換（JSON出力のため）
def decimal_to_float(obj):
    """
    What: DynamoDB Decimal型をPythonネイティブ型に変換
    Why: DecimalはJSON serializeできないため、float/intに変換が必要
    """
    if isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        # 整数値の場合はintに、小数の場合はfloatに
        if obj % 1 == 0:
            return int(obj)
        else:
            return float(obj)
    else:
        return obj


def scan_dynamodb_results(
    table_name: str = "motion-scan-results",
    region: str = "ap-northeast-1",
    cutoff_date: str = "2025-11-05T00:00:00"
) -> List[Dict[str, Any]]:
    """
    What: DynamoDBテーブルから2025-11-05以降のデータを全件スキャン
    Why: 品質メトリクス分析のための生データ取得

    Design Decision:
    - FilterExpressionで日付フィルタ（cutoff_date以降）
    - ProjectionExpressionで必要な列のみ取得（通信量削減）

    Args:
        table_name: DynamoDBテーブル名
        region: AWSリージョン
        cutoff_date: 取得開始日時（ISO8601形式）

    Returns:
        レコードのリスト

    CRITICAL: Scanは全件読み込みなので、データ量が多い場合は時間がかかる
    """
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    # PHASE CORE LOGIC: 必要な列のみ取得（通信量削減）
    projection_expression = (
        "video_id, processed_at, test_type, score, max_score, "
        "health_check, quality_metrics, scoring_version"
    )

    scan_kwargs = {
        "ProjectionExpression": projection_expression,
        # FilterExpression: cutoff_date以降のレコードのみ
        "FilterExpression": "processed_at >= :cutoff",
        "ExpressionAttributeValues": {":cutoff": cutoff_date}
    }

    items = []
    print(f"DynamoDBスキャン開始: table={table_name}, cutoff={cutoff_date}")

    # CRITICAL: ページネーション対応（LastEvaluatedKeyがある限りループ）
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

        # ページネーション処理
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key
        print(f"  ... {len(items)}件取得済み（継続中）")

    print(f"スキャン完了: 総件数={len(items)}")
    return items


def extract_metrics(items: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """
    What: DynamoDBレコードから品質メトリクスを抽出
    Why: detection_rate, quality_score等の統計計算のため

    Design Decision:
    - health_check.detection_rate: ランドマーク検出率（0.0〜1.0）
    - quality_metrics.quality_score: 品質スコア（0〜100）
    - 欠損値は除外（統計計算に含めない）

    Args:
        items: DynamoDBから取得したレコードリスト

    Returns:
        メトリクス名をキーとした値のリスト辞書
        {
            "detection_rate": [1.0, 0.95, ...],
            "quality_score": [85.3, 72.1, ...],
            "is_quality_ok": [True, False, ...],
            "recommend_retake": [False, True, ...]
        }
    """
    metrics = {
        "detection_rate": [],
        "quality_score": [],
        "is_quality_ok": [],
        "recommend_retake": [],
        "test_type": [],
        "processed_at": []
    }

    for item in items:
        # Decimal型を変換
        item = decimal_to_float(item)

        # detection_rate抽出
        health_check = item.get("health_check", {})
        if "detection_rate" in health_check:
            metrics["detection_rate"].append(health_check["detection_rate"])

        # quality_score抽出
        quality_metrics = item.get("quality_metrics", {})
        if "quality_score" in quality_metrics:
            metrics["quality_score"].append(quality_metrics["quality_score"])

        # is_quality_ok抽出
        if "is_quality_ok" in health_check:
            metrics["is_quality_ok"].append(health_check["is_quality_ok"])

        # recommend_retake抽出
        if "recommend_retake" in quality_metrics:
            metrics["recommend_retake"].append(quality_metrics["recommend_retake"])

        # test_type抽出
        if "test_type" in item:
            metrics["test_type"].append(item["test_type"])

        # processed_at抽出
        if "processed_at" in item:
            metrics["processed_at"].append(item["processed_at"])

    print(f"\nメトリクス抽出完了:")
    print(f"  detection_rate: {len(metrics['detection_rate'])}件")
    print(f"  quality_score: {len(metrics['quality_score'])}件")
    print(f"  is_quality_ok: {len(metrics['is_quality_ok'])}件")
    print(f"  recommend_retake: {len(metrics['recommend_retake'])}件")

    return metrics


def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """
    What: 数値リストの統計量を計算
    Why: detection_rate, quality_scoreの分布を理解するため

    Design Decision:
    - numpy.percentileで百分位数計算
    - P50=中央値, P95=95パーセンタイル

    Args:
        values: 数値のリスト

    Returns:
        統計量の辞書
        {
            "count": 件数,
            "mean": 平均,
            "min": 最小,
            "max": 最大,
            "p50": 中央値,
            "p95": 95パーセンタイル
        }
    """
    if not values:
        return {
            "count": 0,
            "mean": None,
            "min": None,
            "max": None,
            "p50": None,
            "p95": None
        }

    arr = np.array(values)

    return {
        "count": len(values),
        "mean": float(np.mean(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95))
    }


def calculate_quality_score_distribution(values: List[float]) -> Dict[str, Any]:
    """
    What: quality_scoreの分布を計算（ヒストグラム + 百分位数）
    Why: 品質スコアの傾向を可視化するため

    Design Decision:
    - ヒストグラム: 10区間（0-10, 10-20, ..., 90-100）
    - 百分位数: P10, P25, P50, P75, P90

    Args:
        values: quality_scoreのリスト

    Returns:
        分布情報の辞書
        {
            "histogram": {区間: 件数},
            "percentiles": {P10: 値, P25: 値, ...}
        }
    """
    if not values:
        return {
            "histogram": {},
            "percentiles": {}
        }

    arr = np.array(values)

    # ヒストグラム生成（10区間）
    bins = list(range(0, 101, 10))  # [0, 10, 20, ..., 100]
    hist, bin_edges = np.histogram(arr, bins=bins)

    histogram = {}
    for i in range(len(hist)):
        bin_label = f"{int(bin_edges[i])}-{int(bin_edges[i+1])}"
        histogram[bin_label] = int(hist[i])

    # 百分位数計算
    percentiles = {
        "p10": float(np.percentile(arr, 10)),
        "p25": float(np.percentile(arr, 25)),
        "p50": float(np.percentile(arr, 50)),
        "p75": float(np.percentile(arr, 75)),
        "p90": float(np.percentile(arr, 90))
    }

    return {
        "histogram": histogram,
        "percentiles": percentiles
    }


def analyze_quality_patterns(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    What: 品質パターンを分析（is_quality_ok, recommend_retake）
    Why: 低品質動画の傾向を把握するため

    Design Decision:
    - is_quality_ok=False の件数・割合
    - recommend_retake=True の件数・割合

    Args:
        items: DynamoDBから取得したレコードリスト

    Returns:
        品質パターン分析結果
        {
            "total_count": 総件数,
            "is_quality_ok_false_count": is_quality_ok=Falseの件数,
            "is_quality_ok_false_ratio": is_quality_ok=Falseの割合,
            "recommend_retake_true_count": recommend_retake=Trueの件数,
            "recommend_retake_true_ratio": recommend_retake=Trueの割合
        }
    """
    items = [decimal_to_float(item) for item in items]

    total_count = len(items)
    is_quality_ok_false_count = 0
    recommend_retake_true_count = 0

    for item in items:
        health_check = item.get("health_check", {})
        quality_metrics = item.get("quality_metrics", {})

        if health_check.get("is_quality_ok") is False:
            is_quality_ok_false_count += 1

        if quality_metrics.get("recommend_retake") is True:
            recommend_retake_true_count += 1

    return {
        "total_count": total_count,
        "is_quality_ok_false_count": is_quality_ok_false_count,
        "is_quality_ok_false_ratio": is_quality_ok_false_count / total_count if total_count > 0 else 0.0,
        "recommend_retake_true_count": recommend_retake_true_count,
        "recommend_retake_true_ratio": recommend_retake_true_count / total_count if total_count > 0 else 0.0
    }


def main():
    """
    What: Stage 1実装 - DynamoDBスキャン & 基本統計
    Why: 品質メトリクスの全体傾向を把握するため

    Design Decision:
    - データ取得: 2025-11-05以降
    - 統計計算: detection_rate, quality_scoreの基本統計
    - 出力: JSONファイル（後続Stageで利用）
    """
    print("=" * 60)
    print("DynamoDB品質メトリクス分析 - Stage 1: スキャン & 基本統計")
    print("=" * 60)

    # DynamoDBスキャン
    items = scan_dynamodb_results()

    if not items:
        print("\n⚠️  データが取得できませんでした")
        sys.exit(1)

    # メトリクス抽出
    metrics = extract_metrics(items)

    # detection_rate統計
    print("\n" + "=" * 60)
    print("detection_rate統計")
    print("=" * 60)
    detection_stats = calculate_statistics(metrics["detection_rate"])
    print(json.dumps(detection_stats, indent=2))

    # quality_score統計
    print("\n" + "=" * 60)
    print("quality_score統計")
    print("=" * 60)
    quality_stats = calculate_statistics(metrics["quality_score"])
    print(json.dumps(quality_stats, indent=2))

    # quality_score分布
    print("\n" + "=" * 60)
    print("quality_score分布")
    print("=" * 60)
    quality_distribution = calculate_quality_score_distribution(metrics["quality_score"])
    print(json.dumps(quality_distribution, indent=2))

    # 品質パターン分析
    print("\n" + "=" * 60)
    print("品質パターン分析")
    print("=" * 60)
    quality_patterns = analyze_quality_patterns(items)
    print(json.dumps(quality_patterns, indent=2))

    # 結果を辞書にまとめる
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_range": {
            "cutoff_date": "2025-11-05T00:00:00",
            "total_records": len(items)
        },
        "detection_rate": detection_stats,
        "quality_score": {
            "statistics": quality_stats,
            "distribution": quality_distribution
        },
        "quality_patterns": quality_patterns
    }

    # JSON出力
    output_path = "docs/monitoring/quality_metrics_stage1.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Stage 1完了: 結果を {output_path} に保存しました")
    print("\n次のステップ: Stage 2（低品質パターンTop3抽出）")


if __name__ == "__main__":
    main()
