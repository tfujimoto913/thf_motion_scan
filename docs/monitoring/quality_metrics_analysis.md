# 品質メトリクス分析結果（S3ベース）

**生成日時**: 2025-11-05T17:51:27.223596+00:00

**データソース**: S3バケット（thf-motion-scan-results-417081976353）

**データ範囲**: 2025-11-01以降

**総レコード数**: 26件

---

## 1. detection_rate統計

- **件数**: 26
- **平均**: 1.0000
- **最小**: 1.0000
- **最大**: 1.0000
- **P50（中央値）**: 1.0000
- **P95**: 1.0000

## 2. quality_score統計

- **件数**: 26
- **平均**: 87.31
- **最小**: 81.00
- **最大**: 95.00
- **P50（中央値）**: 86.00
- **P95**: 93.00

## 3. quality_score分布

### ヒストグラム（10区間）

| 区間 | 件数 |
|------|------|
| 0-10 | 0 |
| 10-20 | 0 |
| 20-30 | 0 |
| 30-40 | 0 |
| 40-50 | 0 |
| 50-60 | 0 |
| 60-70 | 0 |
| 70-80 | 0 |
| 80-90 | 20 |
| 90-100 | 6 |

### 百分位数

- **P10**: 85.00
- **P25**: 85.00
- **P50**: 86.00
- **P75**: 88.75
- **P90**: 92.50

## 4. 品質パターン分析

- **総件数**: 26
- **is_quality_ok=False**: 15件（57.7%）
- **recommend_retake=True**: 0件（0.0%）

## 5. 低品質動画Top3

### #1: /tmp/tmp7oe443l8.mp4

- **quality_score**: 81.00
- **detection_rate**: 1.0000
- **is_quality_ok**: True
- **recommend_retake**: False
- **test_type**: stride_mimic
- **landmark_visibility_avg**: 0.8933
- **frame_completeness**: 0.7613
- **low_visibility_frames**: 96/1343
- **warnings**: High frame loss rate

### #2: /tmp/tmpnkvxb3r1.mp4

- **quality_score**: 84.00
- **detection_rate**: 1.0000
- **is_quality_ok**: False
- **recommend_retake**: False
- **test_type**: stride_mimic
- **landmark_visibility_avg**: 0.7509
- **frame_completeness**: 0.9083
- **low_visibility_frames**: 886/2140

### #3: /tmp/tmpafd1raac.mp4

- **quality_score**: 85.00
- **detection_rate**: 1.0000
- **is_quality_ok**: True
- **recommend_retake**: False
- **test_type**: single_leg_squat
- **landmark_visibility_avg**: 0.8967
- **frame_completeness**: 0.8311
- **low_visibility_frames**: 45/1766
- **warnings**: High frame loss rate

## 6. recommend_retake原因分類

| 原因 | 件数 |
|------|------|
| High frame loss rate | 16 |

---

**注**: この分析はS3結果ファイルから直接取得したデータを使用しています。
DynamoDBには`quality_metrics`が保存されていないため、S3ベースの分析を実施しました。
