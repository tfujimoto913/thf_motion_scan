#!/usr/bin/env python3
"""
Purpose: S3結果JSONファイルから品質メトリクスを分析
Responsibility: S3バケットから結果ファイル取得→品質メトリクス集計・分析
Dependencies: boto3, numpy
Created: 2025-11-06 by Claude Code
Decision Log: ADR-024

What: S3結果JSONファイルからquality_metrics, detection_rate等を抽出・統計分析
Why: DynamoDBにquality_metricsが保存されていないため、S3から直接取得

Design Decision:
- データソース: S3バケット（thf-motion-scan-results-417081976353/results/）
- データ範囲: 2025-11-01以降の処理済みJSONファイル
- 出力: Markdown + JSON（docs/monitoring/quality_metrics_analysis.*）
- 統計: detection_rate（平均, P50, P95, 最小, 最大）
        quality_score（ヒストグラム10区間, P10/P25/P50/P75/P90）
        低品質パターンTop3抽出

CRITICAL: S3 GetObject APIコール数に注意（N件のファイル取得）
"""

import boto3
import json
import sys
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
import numpy as np


def list_s3_result_files(
    bucket: str = "thf-motion-scan-results-417081976353",
    prefix: str = "results/",
    region: str = "ap-northeast-1",
    cutoff_date: str = "2025-11-01"
) -> List[str]:
    """
    What: S3バケットから結果JSONファイルのキーリストを取得
    Why: 品質分析対象のファイルを列挙するため

    Design Decision:
    - cutoff_date以降のファイルのみ取得
    - パス形式: results/YYYY/MM/DD/*.json

    Args:
        bucket: S3バケット名
        prefix: ファイルプレフィックス
        region: AWSリージョン
        cutoff_date: 取得開始日（YYYY-MM-DD形式）

    Returns:
        S3キーのリスト
    """
    s3 = boto3.client("s3", region_name=region)

    # PHASE CORE LOGIC: 日付フィルタ処理
    cutoff_parts = cutoff_date.split("-")
    cutoff_year = cutoff_parts[0]
    cutoff_month = cutoff_parts[1]
    cutoff_day = cutoff_parts[2]

    keys = []
    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if not key.endswith(".json"):
                continue

            # パス形式: results/YYYY/MM/DD/*.json
            parts = key.split("/")
            if len(parts) >= 4:
                year = parts[1]
                month = parts[2]
                day = parts[3]

                # 日付比較（YYYY-MM-DD形式）
                file_date = f"{year}-{month}-{day}"
                if file_date >= cutoff_date:
                    keys.append(key)

    print(f"S3ファイル列挙完了: {len(keys)}件（{cutoff_date}以降）")
    return keys


def fetch_s3_json(
    bucket: str,
    key: str,
    region: str = "ap-northeast-1"
) -> Optional[Dict[str, Any]]:
    """
    What: S3からJSONファイルを取得してパース
    Why: 品質メトリクスデータ抽出のため

    Args:
        bucket: S3バケット名
        key: S3キー
        region: AWSリージョン

    Returns:
        パースされたJSONデータ（失敗時はNone）
    """
    s3 = boto3.client("s3", region_name=region)

    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        content = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except Exception as e:
        print(f"  ⚠️  {key} の取得失敗: {e}")
        return None


def extract_metrics_from_results(
    results: List[Dict[str, Any]]
) -> Dict[str, List[Any]]:
    """
    What: 結果JSONリストから品質メトリクスを抽出
    Why: 統計分析のためのデータ準備

    Design Decision:
    - quality_metrics.quality_score: 品質スコア（0〜100）
    - health_check.detection_rate: ランドマーク検出率（0.0〜1.0）
    - health_check.is_quality_ok: 品質OK/NG判定
    - quality_metrics.recommend_retake: 再撮影推奨フラグ
    - quality_metrics.warnings: 警告リスト

    Args:
        results: S3から取得したJSONデータのリスト

    Returns:
        メトリクス名をキーとした値のリスト辞書
    """
    metrics = {
        "detection_rate": [],
        "quality_score": [],
        "is_quality_ok": [],
        "recommend_retake": [],
        "warnings": [],
        "test_type": [],
        "processed_at": [],
        "landmark_visibility_avg": [],
        "frame_completeness": [],
        "low_visibility_frames": [],
        "total_frames": []
    }

    for result in results:
        # health_check
        health_check = result.get("health_check", {})
        if "detection_rate" in health_check:
            metrics["detection_rate"].append(health_check["detection_rate"])
        if "is_quality_ok" in health_check:
            metrics["is_quality_ok"].append(health_check["is_quality_ok"])
        if "low_visibility_frames" in health_check:
            metrics["low_visibility_frames"].append(health_check["low_visibility_frames"])
        if "total_frames" in health_check:
            metrics["total_frames"].append(health_check["total_frames"])

        # quality_metrics
        quality_metrics = result.get("quality_metrics", {})
        if "quality_score" in quality_metrics:
            metrics["quality_score"].append(quality_metrics["quality_score"])
        if "recommend_retake" in quality_metrics:
            metrics["recommend_retake"].append(quality_metrics["recommend_retake"])
        if "warnings" in quality_metrics:
            # 警告リストを展開
            for warning in quality_metrics["warnings"]:
                metrics["warnings"].append(warning)
        if "landmark_visibility_avg" in quality_metrics:
            metrics["landmark_visibility_avg"].append(quality_metrics["landmark_visibility_avg"])
        if "frame_completeness" in quality_metrics:
            metrics["frame_completeness"].append(quality_metrics["frame_completeness"])

        # その他
        if "test_type" in result:
            metrics["test_type"].append(result["test_type"])
        if "processed_at" in result:
            metrics["processed_at"].append(result["processed_at"])

    print(f"\nメトリクス抽出完了:")
    print(f"  detection_rate: {len(metrics['detection_rate'])}件")
    print(f"  quality_score: {len(metrics['quality_score'])}件")
    print(f"  is_quality_ok: {len(metrics['is_quality_ok'])}件")
    print(f"  recommend_retake: {len(metrics['recommend_retake'])}件")
    print(f"  warnings: {len(metrics['warnings'])}件")

    return metrics


def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """
    What: 数値リストの統計量を計算
    Why: detection_rate, quality_scoreの分布を理解するため

    Args:
        values: 数値のリスト

    Returns:
        統計量の辞書
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

    Args:
        values: quality_scoreのリスト

    Returns:
        分布情報の辞書
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


def analyze_quality_patterns(
    metrics: Dict[str, List[Any]]
) -> Dict[str, Any]:
    """
    What: 品質パターンを分析（is_quality_ok, recommend_retake）
    Why: 低品質動画の傾向を把握するため

    Args:
        metrics: 抽出されたメトリクス

    Returns:
        品質パターン分析結果
    """
    total_count = len(metrics["is_quality_ok"])
    is_quality_ok_false_count = sum(1 for val in metrics["is_quality_ok"] if val is False)
    recommend_retake_true_count = sum(1 for val in metrics["recommend_retake"] if val is True)

    return {
        "total_count": total_count,
        "is_quality_ok_false_count": is_quality_ok_false_count,
        "is_quality_ok_false_ratio": is_quality_ok_false_count / total_count if total_count > 0 else 0.0,
        "recommend_retake_true_count": recommend_retake_true_count,
        "recommend_retake_true_ratio": recommend_retake_true_count / total_count if total_count > 0 else 0.0
    }


def analyze_low_quality_top3(
    results: List[Dict[str, Any]],
    metrics: Dict[str, List[Any]]
) -> List[Dict[str, Any]]:
    """
    What: 低品質動画Top3を抽出
    Why: 誤検知パターンを特定するため

    Design Decision:
    - quality_score昇順でTop3
    - 各動画の詳細情報を含む

    Args:
        results: 結果JSONデータのリスト
        metrics: 抽出されたメトリクス

    Returns:
        低品質Top3のリスト
    """
    # quality_scoreでソート
    scored_results = []
    for result in results:
        quality_metrics = result.get("quality_metrics", {})
        if "quality_score" in quality_metrics:
            scored_results.append({
                "video_id": result.get("video_path", "unknown"),
                "quality_score": quality_metrics["quality_score"],
                "detection_rate": result.get("health_check", {}).get("detection_rate"),
                "is_quality_ok": result.get("health_check", {}).get("is_quality_ok"),
                "recommend_retake": quality_metrics.get("recommend_retake"),
                "warnings": quality_metrics.get("warnings", []),
                "test_type": result.get("test_type"),
                "landmark_visibility_avg": quality_metrics.get("landmark_visibility_avg"),
                "frame_completeness": quality_metrics.get("frame_completeness"),
                "low_visibility_frames": result.get("health_check", {}).get("low_visibility_frames"),
                "total_frames": result.get("health_check", {}).get("total_frames")
            })

    # quality_score昇順でソート
    scored_results.sort(key=lambda x: x["quality_score"])

    return scored_results[:3]


def classify_recommend_retake_causes(
    metrics: Dict[str, List[Any]]
) -> Dict[str, int]:
    """
    What: recommend_retake=Trueの原因を分類
    Why: 再撮影推奨の主要因を特定するため

    Design Decision:
    - warningsの内容から原因を分類
    - 例: "low_visibility", "detection_failure", etc.

    Args:
        metrics: 抽出されたメトリクス

    Returns:
        原因別の件数
    """
    # warningsの出現頻度をカウント
    warning_counter = Counter(metrics["warnings"])

    return dict(warning_counter.most_common(10))


def generate_markdown_report(
    result: Dict[str, Any],
    output_path: str
):
    """
    What: 分析結果をMarkdown形式でレポート生成
    Why: 人間が読みやすい形式での結果提示

    Args:
        result: 分析結果
        output_path: 出力ファイルパス
    """
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# 品質メトリクス分析結果（S3ベース）\n\n")
        f.write(f"**生成日時**: {result['generated_at']}\n\n")
        f.write(f"**データソース**: S3バケット（thf-motion-scan-results-417081976353）\n\n")
        f.write(f"**データ範囲**: {result['data_range']['cutoff_date']}以降\n\n")
        f.write(f"**総レコード数**: {result['data_range']['total_records']}件\n\n")

        f.write("---\n\n")

        # detection_rate統計
        f.write("## 1. detection_rate統計\n\n")
        dr = result["detection_rate"]
        f.write(f"- **件数**: {dr['count']}\n")
        f.write(f"- **平均**: {dr['mean']:.4f}\n")
        f.write(f"- **最小**: {dr['min']:.4f}\n")
        f.write(f"- **最大**: {dr['max']:.4f}\n")
        f.write(f"- **P50（中央値）**: {dr['p50']:.4f}\n")
        f.write(f"- **P95**: {dr['p95']:.4f}\n\n")

        # quality_score統計
        f.write("## 2. quality_score統計\n\n")
        qs = result["quality_score"]["statistics"]
        f.write(f"- **件数**: {qs['count']}\n")
        f.write(f"- **平均**: {qs['mean']:.2f}\n")
        f.write(f"- **最小**: {qs['min']:.2f}\n")
        f.write(f"- **最大**: {qs['max']:.2f}\n")
        f.write(f"- **P50（中央値）**: {qs['p50']:.2f}\n")
        f.write(f"- **P95**: {qs['p95']:.2f}\n\n")

        # quality_score分布
        f.write("## 3. quality_score分布\n\n")
        f.write("### ヒストグラム（10区間）\n\n")
        dist = result["quality_score"]["distribution"]
        f.write("| 区間 | 件数 |\n")
        f.write("|------|------|\n")
        for bin_label, count in dist["histogram"].items():
            f.write(f"| {bin_label} | {count} |\n")
        f.write("\n")

        f.write("### 百分位数\n\n")
        perc = dist["percentiles"]
        f.write(f"- **P10**: {perc['p10']:.2f}\n")
        f.write(f"- **P25**: {perc['p25']:.2f}\n")
        f.write(f"- **P50**: {perc['p50']:.2f}\n")
        f.write(f"- **P75**: {perc['p75']:.2f}\n")
        f.write(f"- **P90**: {perc['p90']:.2f}\n\n")

        # 品質パターン
        f.write("## 4. 品質パターン分析\n\n")
        qp = result["quality_patterns"]
        f.write(f"- **総件数**: {qp['total_count']}\n")
        f.write(f"- **is_quality_ok=False**: {qp['is_quality_ok_false_count']}件（{qp['is_quality_ok_false_ratio']*100:.1f}%）\n")
        f.write(f"- **recommend_retake=True**: {qp['recommend_retake_true_count']}件（{qp['recommend_retake_true_ratio']*100:.1f}%）\n\n")

        # 低品質Top3
        f.write("## 5. 低品質動画Top3\n\n")
        for i, item in enumerate(result["low_quality_top3"], start=1):
            f.write(f"### #{i}: {item['video_id']}\n\n")
            f.write(f"- **quality_score**: {item['quality_score']:.2f}\n")
            f.write(f"- **detection_rate**: {item['detection_rate']:.4f}\n")
            f.write(f"- **is_quality_ok**: {item['is_quality_ok']}\n")
            f.write(f"- **recommend_retake**: {item['recommend_retake']}\n")
            f.write(f"- **test_type**: {item['test_type']}\n")
            f.write(f"- **landmark_visibility_avg**: {item['landmark_visibility_avg']:.4f}\n")
            f.write(f"- **frame_completeness**: {item['frame_completeness']:.4f}\n")
            f.write(f"- **low_visibility_frames**: {item['low_visibility_frames']}/{item['total_frames']}\n")
            if item["warnings"]:
                f.write(f"- **warnings**: {', '.join(item['warnings'])}\n")
            f.write("\n")

        # recommend_retake原因分類
        f.write("## 6. recommend_retake原因分類\n\n")
        causes = result["recommend_retake_causes"]
        if causes:
            f.write("| 原因 | 件数 |\n")
            f.write("|------|------|\n")
            for cause, count in causes.items():
                f.write(f"| {cause} | {count} |\n")
        else:
            f.write("（警告なし）\n")

        f.write("\n---\n\n")
        f.write("**注**: この分析はS3結果ファイルから直接取得したデータを使用しています。\n")
        f.write("DynamoDBには`quality_metrics`が保存されていないため、S3ベースの分析を実施しました。\n")

    print(f"✅ Markdownレポート生成完了: {output_path}")


def main():
    """
    What: S3ベース品質メトリクス分析の実行
    Why: DynamoDBにquality_metricsが保存されていないため、S3から直接取得

    Design Decision:
    - Stage 1: S3結果ファイルの列挙
    - Stage 2: データ抽出と統合
    - Stage 3: 統計分析実行
    - Stage 4: レポート生成
    """
    print("=" * 60)
    print("品質メトリクス分析（S3ベース）")
    print("=" * 60)

    bucket = "thf-motion-scan-results-417081976353"
    region = "ap-northeast-1"
    cutoff_date = "2025-11-01"

    # Stage 1: S3結果ファイルの列挙
    print("\n[Stage 1] S3結果ファイルの列挙")
    keys = list_s3_result_files(bucket=bucket, region=region, cutoff_date=cutoff_date)

    if len(keys) < 10:
        print(f"\n⚠️  警告: データ件数が少なすぎます（N={len(keys)} < 10）")
        print("   統計的信頼性が低い可能性があります")

    if len(keys) == 0:
        print("\n❌ データが取得できませんでした")
        sys.exit(1)

    # Stage 2: データ抽出と統合
    print("\n[Stage 2] JSONデータ抽出と統合")
    results = []
    for i, key in enumerate(keys, start=1):
        print(f"  {i}/{len(keys)}: {key}")
        data = fetch_s3_json(bucket, key, region)
        if data:
            results.append(data)

    print(f"\n取得成功: {len(results)}/{len(keys)}件")

    # メトリクス抽出
    metrics = extract_metrics_from_results(results)

    # Stage 3: 統計分析実行
    print("\n[Stage 3] 統計分析実行")

    # detection_rate統計
    print("\n--- detection_rate統計 ---")
    detection_stats = calculate_statistics(metrics["detection_rate"])
    print(json.dumps(detection_stats, indent=2))

    # quality_score統計
    print("\n--- quality_score統計 ---")
    quality_stats = calculate_statistics(metrics["quality_score"])
    print(json.dumps(quality_stats, indent=2))

    # quality_score分布
    print("\n--- quality_score分布 ---")
    quality_distribution = calculate_quality_score_distribution(metrics["quality_score"])
    print(json.dumps(quality_distribution, indent=2))

    # 品質パターン分析
    print("\n--- 品質パターン分析 ---")
    quality_patterns = analyze_quality_patterns(metrics)
    print(json.dumps(quality_patterns, indent=2))

    # 低品質Top3
    print("\n--- 低品質Top3 ---")
    low_quality_top3 = analyze_low_quality_top3(results, metrics)
    for i, item in enumerate(low_quality_top3, start=1):
        print(f"{i}. {item['video_id']}: quality_score={item['quality_score']:.2f}")

    # recommend_retake原因分類
    print("\n--- recommend_retake原因分類 ---")
    recommend_retake_causes = classify_recommend_retake_causes(metrics)
    print(json.dumps(recommend_retake_causes, indent=2))

    # Stage 4: レポート生成
    print("\n[Stage 4] レポート生成")

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_range": {
            "cutoff_date": cutoff_date,
            "total_records": len(results)
        },
        "detection_rate": detection_stats,
        "quality_score": {
            "statistics": quality_stats,
            "distribution": quality_distribution
        },
        "quality_patterns": quality_patterns,
        "low_quality_top3": low_quality_top3,
        "recommend_retake_causes": recommend_retake_causes
    }

    # JSON出力
    json_output_path = "docs/monitoring/quality_metrics_analysis.json"
    with open(json_output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON出力完了: {json_output_path}")

    # Markdown出力
    md_output_path = "docs/monitoring/quality_metrics_analysis.md"
    generate_markdown_report(result, md_output_path)

    print("\n" + "=" * 60)
    print("✅ 全ステージ完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
