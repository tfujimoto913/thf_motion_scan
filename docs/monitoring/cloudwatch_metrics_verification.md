# CloudWatch Metrics実データ確認結果

**確認日時**: 2025-11-06 02:25 JST
**対象期間**: 直近24時間、直近7日間
**対象メトリクス**: BalancedCorrectRate, CohenKappa, OverrideRatio
**ネームスペース**: THF/MotionScan

---

## 📊 確認結果サマリー

### データ存在状況

| メトリクス | 24時間 | 7日間 | CloudWatch存在 | 結論 |
|-----------|--------|-------|---------------|------|
| BalancedCorrectRate | 0件 | 0件 | ❌ なし | メトリクス未送信 |
| CohenKappa | 0件 | 0件 | ❌ なし | メトリクス未送信 |
| OverrideRatio | 0件 | 0件 | ❌ なし | メトリクス未送信 |

**重要な発見**: **THF/MotionScan ネームスペースにメトリクスが1件も存在しない**

---

## 1. BCR (BalancedCorrectRate)

### 直近24時間（2025-11-04 17:21 〜 2025-11-05 17:21 UTC）
- **データポイント数**: 0件
- **P95計算**: ❌ 不可能（データなし）

### 直近7日間（2025-10-29 17:24 〜 2025-11-05 17:24 UTC）
- **データポイント数**: 0件
- **P95計算**: ❌ 不可能（データなし）

---

## 2. Kappa (CohenKappa)

### 直近24時間
- **データポイント数**: 0件
- **P95計算**: ❌ 不可能（データなし）

### 直近7日間
- **データポイント数**: 0件
- **P95計算**: ❌ 不可能（データなし）

---

## 3. Override Rate (OverrideRatio)

### 直近24時間
- **データポイント数**: 0件
- **P95計算**: ❌ 不可能（データなし）

### 直近7日間
- **データポイント数**: 0件
- **P95計算**: ❌ 不可能（データなし）

---

## 4. 原因分析

### なぜメトリクスが送信されていないのか？

#### 調査結果

1. **CloudWatch Metrics一覧確認**
   ```bash
   aws cloudwatch list-metrics --namespace THF/MotionScan --region ap-northeast-1
   ```
   **結果**: メトリクス総数 = 0件

2. **Lambda処理ログ確認**
   - `/aws/lambda/thf-motion-scan-ProcessingFunction` のログを7日分検索
   - "metric" キーワード検索結果: 該当なし

3. **コード確認**
   - `src/handler.py` での `emit_metric()` 呼び出し:
     - `LandmarkDetectionRate` (検出率)
     - `AnalysesCompleted` (処理完了カウント)
   - **BCR/Kappa/OverrideRatio の送信コードは存在しない**

#### 根本原因の推定

**BCR/Kappa/OverrideRatio は「評価精度メトリクス」**であり、以下の理由で送信されていない：

##### 1. Ground Truth が必要
- **BCR (Balanced Correct Rate)**: 正解データとの比較が必要
- **Kappa (Cohen's Kappa)**: 評価者間一致度 = 2人以上の評価結果が必要
- **Override Ratio**: 人間による上書き率 = 手動修正データが必要

##### 2. 実装の意図
- これらのメトリクスは `lambda/monitoring/metrics_monitor.py` で**監視対象**として定義されている
- しかし、**送信元**は別のシステム（Dashboard、検証ツール等）の想定

##### 3. 実運用フローでは生成されない
- 通常の動画処理（S3 → Lambda → DynamoDB）では、Ground Truthが存在しない
- したがって、BCR/Kappa/OverrideRatioは計算・送信されない

---

## 5. 代替データソースの調査

### 実際に送信されているメトリクス

`src/handler.py` で実際に送信されているメトリクス:

```python
# 検出率（Landmark Detection Rate）
emit_metric(
    "LandmarkDetectionRate",
    detection_rate * 100,
    unit="Percent"
)

# 処理完了カウント
emit_metric("AnalysesCompleted", 1)
```

### 利用可能なメトリクス候補

| メトリクス | 送信元 | 用途 | データ存在 |
|-----------|--------|------|-----------|
| `LandmarkDetectionRate` | handler.py | ランドマーク検出率 | 要確認 |
| `AnalysesCompleted` | handler.py | 処理完了数 | 要確認 |
| `LandmarkDetectionFailures` | handler.py | 検出失敗数 | 要確認 |

---

## 6. 誤検知分析への影響

### 当初の計画

**誤検知Top3抽出**: BCR/Kappa の閾値乖離から誤検知パターンを特定

### 実際の状況

❌ **計画変更が必要**: BCR/Kappa/OverrideRatioメトリクスが存在しない

### 代替アプローチ

#### Option A: CloudWatch Logsベースの誤検知分析

**データソース**: `/aws/lambda/thf-motion-scan-ProcessingFunction`

**分析可能な指標**:
1. **Health Check失敗**
   - `is_quality_ok: false` のケース
   - `low_visibility_frames` が高いケース
   - `detection_rate` が低いケース

2. **品質メトリクス**
   - `quality_score` が低いケース（<70）
   - `recommend_retake: true` のケース
   - `landmark_visibility_avg` が低いケース（<0.8）

3. **評価結果の偏り**
   - `total_score` の分布
   - `total_percentage` の分布
   - 特定の`B_principles`が consistently 低いケース

#### Option B: S3結果ファイルベースの集計

**データソース**: `s3://thf-motion-scan-results-417081976353/results/`

**分析可能な内容**:
- 全処理結果JSONを集計
- `quality_metrics` の統計分析
- `health_check` の失敗パターン分析
- `evaluation.B_principles` の傾向分析

#### Option C: DynamoDBベースの集計

**データソース**: `motion-scan-results` テーブル

**分析可能な内容**:
- `health_check.is_quality_ok=false` のクエリ
- `scoring_version` 別の統計
- `test_type` 別の品質傾向

---

## 7. 総合評価と推奨アクション

### P95計算の実行可能性

| メトリクス | 24hデータ | 7dデータ | P95計算可否 | 理由 |
|-----------|----------|----------|-----------|------|
| BCR | 0件 | 0件 | ❌ 不可能 | メトリクス未送信 |
| Kappa | 0件 | 0件 | ❌ 不可能 | メトリクス未送信 |
| Override | 0件 | 0件 | ❌ 不可能 | メトリクス未送信 |

### Option 3（集計スクリプト実装）への準備状況

**❌ 当初計画では進行不可**: BCR/Kappa/OverrideRatioメトリクスが存在しない

**✅ 代替計画で進行可能**: CloudWatch Logs/S3/DynamoDBベースの分析

---

## 8. 推奨される次のアクション

### 優先度1: ユーザーへの報告とスコープ再定義

**報告内容**:
1. BCR/Kappa/OverrideRatioメトリクスは実運用では生成されない
2. これらは検証環境でGround Truthと比較する際のメトリクス
3. 誤検知分析の方針を変更する必要がある

**スコープ再定義の提案**:
- ❌ BCR/Kappa P95乖離テーブル → 実装不可
- ✅ 品質メトリクス（quality_score, detection_rate）の統計分析
- ✅ Health Check失敗パターンのTop3抽出
- ✅ 低品質動画の特徴分析（landmark_visibility, frame_completeness）

### 優先度2: 利用可能なメトリクスの確認

```bash
# LandmarkDetectionRate の実データ確認
aws cloudwatch get-metric-statistics \
  --namespace THF/MotionScan \
  --metric-name LandmarkDetectionRate \
  --start-time $(date -u -v-7d +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average Maximum Minimum SampleCount \
  --region ap-northeast-1
```

### 優先度3: 代替分析方針の決定

**3つの選択肢**:

1. **CloudWatch Logsベース**
   - 構造化ログから `health_check` と `quality_metrics` を抽出
   - `is_quality_ok=false` のパターン分析
   - 実装難易度: 中

2. **S3結果ファイルベース**
   - 全処理結果JSONをダウンロード・集計
   - より詳細な分析が可能
   - 実装難易度: 高

3. **DynamoDBベース**
   - テーブルスキャンでクエリ
   - 最も高速だが、データが限定的（2025-11-05以降のみ）
   - 実装難易度: 低

---

## 9. metrics_monitor.py の役割の再確認

### 設計意図

`lambda/monitoring/metrics_monitor.py` は以下を前提としている:

```python
METRICS_CONFIG = [
    {
        "metric_name": "BCR",
        "cloudwatch_metric": "BalancedCorrectRate",
        "warn_threshold": 0.5,
        "fail_threshold": 0.3,
    },
    {
        "metric_name": "Kappa",
        "cloudwatch_metric": "CohenKappa",
        "warn_threshold": 0.3,
        "fail_threshold": 0.2,
    },
    {
        "metric_name": "OverrideRatio",
        "cloudwatch_metric": "OverrideRatio",
        "warn_threshold": 30.0,
        "fail_threshold": 50.0,
    },
]
```

**実行頻度**: EventBridge経由で1分ごと
**処理内容**: CloudWatch GetMetricStatistics API でメトリクスを取得 → 閾値評価 → SNS通知

### 現状の問題

**❌ メトリクスが存在しないため、監視が機能していない**

### 解決策

#### Option A: メトリクス送信を実装
- Dashboard/検証ツールから BCR/Kappa/OverrideRatio を送信
- Ground Truthデータセットが必要

#### Option B: 監視対象を変更
- `LandmarkDetectionRate`, `quality_score`, `is_quality_ok` 等の実在メトリクスに変更
- `metrics_monitor.py` の `METRICS_CONFIG` を更新

#### Option C: 監視を一時停止
- EventBridge Ruleを無効化
- Ground Truthデータセットが整備されるまで待機

---

## 10. まとめ

### 確認結果

❌ **BCR/Kappa/OverrideRatio メトリクスは存在しない**
- CloudWatch Metricsに1件もデータなし
- 送信コードも実装されていない
- Ground Truth必須のため、実運用では生成されない

### 次のステップ

**ユーザーとの協議が必要**:
1. 誤検知分析のスコープ再定義
2. 代替メトリクス（quality_score, detection_rate等）での分析に切り替え
3. または、Ground Truthデータセットの整備

---

**確認完了日時**: 2025-11-06 02:27 JST
**所要時間**: 約12分
**次のアクション**: ユーザーへ報告 → スコープ再定義 → Option 3（修正版）の実装
