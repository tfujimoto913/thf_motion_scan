# 技術的負債：quality_score/detection_rateのCloudWatch送信未実装 ✅ 解消済み

**発見日**: 2025-11-06
**発見者**: Claude Code
**解消日**: 2025-11-06
**優先度**: 中 → ✅ 解消済み
**カテゴリ**: 監視システム、メトリクス送信

---

## 問題

### 概要
`quality_score`および`detection_rate`（health_check内）がCloudWatchメトリクスとして送信されていない。

### 詳細
- **場所**: `processing/worker.py`
- **現状**: `LandmarkDetectionRate`のみ送信（line 223）
- **欠損**: `quality_score`, `detection_rate`の送信処理なし
- **影響**: これらのメトリクスをCloudWatchで監視できない（S3結果ファイルからの取得のみ）

### 欠損データ
1. **quality_score**: 総合品質スコア（0〜100点）
   - 照明、距離、姿勢等の総合評価
   - 現状: S3結果JSON内の`quality_metrics.quality_score`に存在
   - 分析結果: 平均87.3、範囲81-95（N=26）

2. **detection_rate**: フレーム検出率（0.0〜1.0）
   - health_check内のdetection_rate
   - 現状: S3結果JSON内の`health_check.detection_rate`に存在
   - 分析結果: 全件1.0（100%検出、N=26）

---

## 影響範囲

### 現在の影響
- **CloudWatch監視**: quality_score/detection_rateの監視不可
- **アラート**: これらのメトリクスでの閾値アラート設定不可
- **ダッシュボード**: リアルタイム品質トレンド表示不可

### 現在の回避策
- S3結果JSONからバッチ分析（`scripts/monitoring/analyze_quality_from_s3.py`）
- DynamoDBにquality_metricsが保存されていないため、S3スキャンが必要

### 将来的な影響
- リアルタイム品質監視ダッシュボード構築時に制約
- P95品質スコアトラッキングが困難
- 品質劣化の早期検知ができない

---

## 根本原因

### コード分析

**processing/worker.py:223**（現状）
```python
# LandmarkDetectionRateのみ送信
emit_metric("LandmarkDetectionRate", detection_rate * 100, unit="Percent")
if not (is_quality_ok and not quality_metrics['recommend_retake']):
    emit_metric("LandmarkDetectionFailures", 1)
```

**欠損している送信処理**:
```python
# quality_scoreの送信（未実装）
emit_metric("QualityScore", quality_metrics['quality_score'], unit="None")

# detection_rateの送信（未実装、LandmarkDetectionRateと重複の可能性）
# emit_metric("DetectionRate", detection_rate * 100, unit="Percent")
```

### 設計判断の推測
- **当初の設計**: S3を詳細データの保存先、CloudWatchを主要指標のみ送信
- **想定**: `quality_score`は詳細データとしてS3のみに保存
- **結果**: リアルタイム監視が困難になった

---

## 対応方針

### 短期対応（現在実施済み）
**回避策**: S3結果JSONからバッチ分析
- **実装**: `scripts/monitoring/analyze_quality_from_s3.py`
- **閾値設計**: `config/monitoring/quality_thresholds.yaml`（design_only_metricsセクション）
- **メリット**: 統計分析が可能（N=26）
- **デメリット**: リアルタイム監視不可

### 中期対応（推奨）
**修正**: `processing/worker.py`にメトリクス送信を追加

#### 実装案1: quality_scoreの送信
```python
# processing/worker.py:223付近に追加
quality_score = quality_metrics.get('quality_score')
if quality_score is not None:
    emit_metric(
        "QualityScore",
        quality_score,
        unit="None",
        dimensions={"TestType": test_type}
    )
```

#### 実装案2: detection_rateの送信
```python
# LandmarkDetectionRateと重複しないか確認後に追加
# 注: LandmarkDetectionRateとdetection_rateの差異を調査
if detection_rate is not None:
    emit_metric(
        "HealthCheckDetectionRate",
        detection_rate * 100,
        unit="Percent",
        dimensions={"TestType": test_type}
    )
```

#### 影響範囲
- 変更ファイル: `processing/worker.py` (2箇所追加)
- CloudWatch Metrics: 新規メトリクス追加（課金増加は軽微）
- テスト: 動画処理の統合テスト
- デプロイ: 次回リリース時に含める

#### 注意点
1. **LandmarkDetectionRateとの重複**
   - `detection_rate`（health_check内）と`LandmarkDetectionRate`（既存メトリクス）の差異を確認
   - 同一であれば、detection_rateの送信は不要

2. **CloudWatch課金**
   - 新規メトリクス2件追加（QualityScore, HealthCheckDetectionRate）
   - 1動画処理あたり2メトリクス × $0.01/1000メトリクス = 微増

3. **Dimensions設計**
   - TestType別の監視が必要か検討
   - 過度なDimensions追加はコスト増加につながる

### 長期対応（検討）
**設計見直し**: メトリクス送信戦略の明確化
- CloudWatch: リアルタイム監視が必要なメトリクス
- S3: 詳細データ・履歴保存
- DynamoDB: 高速クエリが必要な軽量データ
- どのメトリクスをどこに保存するか、設計ドキュメントに明記

---

## 検証結果

### 2025-11-06時点の状況
- **CloudWatchメトリクス**: LandmarkDetectionRateのみ送信済み
- **S3結果ファイル**: quality_score, detection_rate含む（N=26）
- **DynamoDB**: quality_metricsが保存されていない（別の技術的負債）

### S3ベース分析結果（概要）
- **データ件数**: 26件（2025-11-01以降）
- **quality_score**: 平均87.3、範囲81-95
- **detection_rate**: 平均1.0、範囲1.0-1.0（全件完璧）
- **LandmarkDetectionRate**: 実装済み（監視可能）

**詳細**: `docs/monitoring/quality_metrics_analysis.md`参照

---

## 実装タスク

### 新カード：「品質メトリクスのCloudWatch送信実装」

**スコープ**:
1. LandmarkDetectionRateとdetection_rateの差異調査
2. quality_scoreのCloudWatch送信実装
3. (必要に応じて) detection_rateのCloudWatch送信実装
4. metrics_monitor.pyで監視開始
5. 統合テスト実行

**成功の定義**:
- QualityScoreメトリクスがCloudWatchに送信される
- metrics_monitor.pyで監視ロジックが動作
- 閾値ブリーチ時にSNS通知が送信される

**制約条件**:
- CloudWatch課金増加は月$1未満に抑える
- 既存のLandmarkDetectionRate監視に影響を与えない

**優先度**: 中（本タスク完了後に着手推奨）

---

## アクションアイテム

- [x] **優先度中**: LandmarkDetectionRateとdetection_rateの差異調査 - ✅ 同一と確認
- [x] **優先度中**: quality_scoreのCloudWatch送信実装 - ✅ 2025-11-06完了
- [x] **優先度中**: detection_rateのCloudWatch送信実装 - ✅ 2025-11-06完了
- [ ] **優先度中**: metrics_monitor.pyで監視開始 - 次回デプロイ後
- [ ] **優先度低**: メトリクス送信戦略を設計ドキュメントに明記

---

## ✅ 解消報告（2025-11-06）

### 実施内容
**Phase 1実装**: processing/worker.py:230-236にメトリクス送信を追加

**変更内容**:
```python
# QualityScore: 総合品質スコア（新規追加）
emit_metric("QualityScore", quality_score, unit="None")

# DetectionRate: フレーム検出率（新規追加）
emit_metric("DetectionRate", detection_rate * 100, unit="Percent")
```

### 影響範囲
- **変更ファイル**: processing/worker.py (3行追加)
- **CloudWatch Metrics**: 新規メトリクス2件追加
  - QualityScore (unit=None, range=0-100)
  - DetectionRate (unit=Percent, range=0-100)
- **デプロイ**: 次回リリース時に有効化
- **課金影響**: 軽微（月$1未満見込み）

### 期待される効果
- quality_scoreのリアルタイム監視が可能
- detection_rateトレンド追跡が可能
- metrics_monitor.pyで閾値監視開始（デプロイ後）

### LandmarkDetectionRateとの関係
- **確認結果**: detection_rateとLandmarkDetectionRateは同一
- **決定**: 両方送信（監視用に明示的に分離）

---

## 関連ドキュメント
- 分析結果: `docs/monitoring/quality_metrics_analysis.md`
- 閾値設計: `config/monitoring/quality_thresholds.yaml`
- DynamoDB欠損: `docs/technical_debt/dynamodb_quality_metrics.md`
- 既存実装: `processing/worker.py:223` (LandmarkDetectionRate送信)
- 監視ロジック: `lambda/monitoring/metrics_monitor.py`

---

**記録日時**: 2025-11-06
**最終更新**: 2025-11-06
