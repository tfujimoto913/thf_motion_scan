# 監視ルール更新記録

**更新日**: 2025-11-06
**担当**: Claude Code
**タスク**: 品質・処理監視ルール見直し（代替メトリクス）v1

---

## 更新内容サマリー

### 実施内容
1. S3ベース品質メトリクス分析（N=26、2025-11-01以降）
2. 監視閾値設計（quality_thresholds.yaml作成）
3. metrics_monitor.py更新（LandmarkDetectionRate監視追加）
4. 技術的負債記録（DynamoDB、CloudWatch送信未実装）

### 成果物
- **分析レポート**: `docs/monitoring/quality_metrics_analysis.md`
- **閾値設計**: `config/monitoring/quality_thresholds.yaml`
- **監視ロジック**: `lambda/monitoring/metrics_monitor.py`（更新）
- **技術的負債**: `docs/technical_debt/dynamodb_quality_metrics.md`
- **技術的負債**: `docs/technical_debt/quality_metrics_cloudwatch.md`

---

## 1. S3ベース品質メトリクス分析

### データソース
- **S3バケット**: thf-motion-scan-results-417081976353
- **データ範囲**: 2025-11-01以降の処理済みJSONファイル
- **データ件数**: 26件（統計的信頼性OK）

### 分析結果

#### detection_rate（ランドマーク検出率）
- **件数**: 26
- **平均**: 1.0000（100%検出）
- **範囲**: 1.0000 - 1.0000
- **P50**: 1.0000
- **P95**: 1.0000

**結論**: 現状の検出品質は完璧

#### quality_score（総合品質スコア）
- **件数**: 26
- **平均**: 87.31
- **範囲**: 81 - 95
- **P50**: 86
- **P95**: 93
- **P10**: 85
- **P25**: 85

**結論**: 高品質（80点台が76.9%、90点台が23.1%）

#### 品質パターン
- **is_quality_ok=False**: 15/26件（57.7%）
- **recommend_retake=True**: 0件（0.0%）
- **主要警告**: "High frame loss rate"（16/26件、61.5%）

**重要な発見**: quality_score高い（81-95）⇔ is_quality_ok=False（57.7%）の矛盾
→ 別タスク「品質判定ロジック改善」で対応予定

---

## 2. 監視閾値設計

### 実装済みメトリクス

#### LandmarkDetectionRate
- **status**: 実装済み（CloudWatchメトリクス送信中）
- **warn_threshold**: 95.0%（5%低下で警告）
- **fail_threshold**: 90.0%（10%低下で異常）
- **comparison**: less_than（低いほど悪い）
- **debounce**: WARN=15分、FAIL=5分

**設計根拠**: 現状100%だが、5%低下で警告、10%低下で異常とする保守的設計

### 設計のみメトリクス（CloudWatch送信未実装）

#### quality_score
- **warn_threshold**: 85.0点（P25=85、下位25%を警告）
- **fail_threshold**: 81.0点（最小値=81、これ以下は異常）
- **実装状況**: 未実装（別タスクで対応予定）

#### detection_rate
- **warn_threshold**: 0.95（5%低下で警告）
- **fail_threshold**: 0.90（10%低下で異常）
- **実装状況**: 未実装（LandmarkDetectionRateと重複の可能性）

---

## 3. metrics_monitor.py更新

### 変更内容

#### 追加: LandmarkDetectionRate監視
```python
{
    "metric_name": "LandmarkDetectionRate",
    "cloudwatch_metric": "LandmarkDetectionRate",
    "warn_threshold": 95.0,
    "fail_threshold": 90.0,
    "comparison": "less_than",
    "enabled": True,  # 実装済み
}
```

#### 変更: BCR/Kappa/OverrideRatio無効化
```python
{
    "metric_name": "BCR",
    "cloudwatch_metric": "BalancedCorrectRate",
    "warn_threshold": 0.5,
    "fail_threshold": 0.3,
    "comparison": "less_than",
    "enabled": False,  # データなし（Ground Truth必須）
}
```

#### 追加: enabled判定ロジック
```python
# Skip disabled metrics (no CloudWatch data available)
if not metric_config.get("enabled", True):
    print(f"Skipping {metric_name} (disabled - no CloudWatch data)")
    continue
```

### 動作変更
- **以前**: BCR/Kappa/OverrideRatioを監視（データなしでOK判定）
- **現在**: LandmarkDetectionRateのみ監視（BCR/Kappa/OverrideRatioはスキップ）

---

## 4. 技術的負債記録

### 負債1: DynamoDBにquality_metricsが保存されていない
- **ドキュメント**: `docs/technical_debt/dynamodb_quality_metrics.md`
- **優先度**: 中
- **影響**: DynamoDBベースの品質分析が不完全（S3回避策で対応中）
- **対応方針**: src/handler.py:721にquality_metrics保存処理を追加

### 負債2: quality_score/detection_rateのCloudWatch送信未実装
- **ドキュメント**: `docs/technical_debt/quality_metrics_cloudwatch.md`
- **優先度**: 中
- **影響**: これらのメトリクスをCloudWatchで監視できない
- **対応方針**: processing/worker.pyにメトリクス送信処理を追加

### 負債3: BCR/Kappa/OverrideRatioメトリクスが存在しない
- **ドキュメント**: `docs/monitoring/cloudwatch_metrics_verification.md`
- **優先度**: 低
- **影響**: Ground Truth必須のため、実運用では生成されない
- **対応方針**: Ground Truth基盤整備後に対応

---

## 5. 別タスク提案

### タスク1: 品質判定ロジック改善（is_quality_ok矛盾解消）
- **優先度**: 中
- **理由**: 57.7%がFalse判定は過検知の可能性
- **内容**: low_visibility_frames閾値の見直し

### タスク2: 品質メトリクスのCloudWatch送信実装
- **優先度**: 中
- **内容**: quality_score, detection_rateをworker.pyで送信
- **完了後**: metrics_monitor.pyで監視開始

### タスク3: DynamoDB quality_metrics保存実装
- **優先度**: 中
- **内容**: src/handler.py:721にquality_metrics保存処理を追加
- **完了後**: DynamoDBベースの品質分析が可能

---

## 6. 今回の制約と判断

### スコープ変更
- **当初計画**: BCR/Kappa/OverrideRatio P95分析
- **実際**: quality_score/detection_rate P95分析（代替メトリクス）
- **理由**: BCR/Kappa/OverrideRatioメトリクスが存在しない（Ground Truth必須）

### 実装範囲
- **実装**: LandmarkDetectionRate監視（実在メトリクス）
- **設計のみ**: quality_score/detection_rate（CloudWatch送信未実装）
- **判断**: 「完璧を待たず即価値を出す」方針

### データソース
- **DynamoDB**: データ1件のみ、quality_metricsなし
- **S3**: データ26件、完全な品質メトリクスあり
- **選択**: S3ベース分析を実施（統計的信頼性確保）

---

## 7. 次のアクション

### 即実行可能
- [x] LandmarkDetectionRate監視の有効化（metrics_monitor.py更新）
- [x] 閾値設計のYAML記録（quality_thresholds.yaml）
- [x] 技術的負債の記録

### 後続タスク
- [ ] 品質メトリクスのCloudWatch送信実装（別タスク）
- [ ] DynamoDB quality_metrics保存実装（別タスク）
- [ ] is_quality_ok閾値の見直し（別タスク）

---

## 8. 成果の評価

### 目標達成度
- ✅ データソース確認完了（Logs/DDB/S3/Metrics）
- ✅ 統計分析完了（N=26、P95算出）
- ✅ 監視閾値設計完了（YAML記録）
- ✅ 監視ロジック実装完了（LandmarkDetectionRate）
- ✅ 技術的負債記録完了

### 即座の価値
- **LandmarkDetectionRate監視**: 検出率低下を15分以内に検知
- **閾値設計**: 統計的根拠のある閾値設定（P95, P25ベース）
- **技術的負債可視化**: 将来対応の優先順位が明確

### 将来の価値
- **quality_score監視**: 実装後、品質劣化を即検知（P25=85点閾値）
- **detection_rate監視**: 実装後、検出率トレンド追跡
- **データ基盤整備**: Ground Truth整備後、BCR/Kappa監視が可能

---

**更新完了日時**: 2025-11-06
**次回レビュー**: 次回デプロイ時（監視動作確認）
