# 技術的負債：quality_metricsのDynamoDB保存欠損 ✅ 解消済み

**発見日**: 2025-11-06
**発見者**: Claude Code
**解消日**: 2025-11-06
**優先度**: 中 → ✅ 解消済み
**カテゴリ**: データ保存、監視システム

---

## 問題

### 概要
`quality_metrics`フィールドがDynamoDBテーブル（motion-scan-results）に保存されていない。

### 詳細
- **場所**: `src/handler.py:683` の`save_to_dynamodb()`関数
- **現状**: `health_check`, `evaluation`, `video_info`は保存されるが、`quality_metrics`の保存処理がない
- **影響**: DynamoDBベースの品質分析が不完全（現状はS3結果ファイルからの取得で回避）

### 欠損データ
`quality_metrics`には以下の重要な品質指標が含まれる：
- `quality_score`: 品質スコア（0〜100）
- `landmark_visibility_avg`: ランドマーク可視性平均（0.0〜1.0）
- `frame_completeness`: フレーム完全性（0.0〜1.0）
- `warnings`: 警告リスト
- `recommend_retake`: 再撮影推奨フラグ

---

## 影響範囲

### 現在の影響
- **監視システム**: 影響なし（CloudWatch Metricsは別途送信）
- **Dashboard**: 影響なし（S3結果ファイルを参照）
- **品質分析**: 影響あり（DynamoDBクエリでは取得不可）

### 将来的な影響
- DynamoDBをプライマリデータソースとした品質監視ダッシュボード構築時に制約
- 高速なクエリベースの品質分析が不可能（S3スキャンが必要）
- セッション単位での品質トレンド分析に手間がかかる

---

## 根本原因

### コード分析
`src/handler.py:712-723`
```python
item = {
    'video_id': f"{bucket}/{video_key}",
    'processed_at': result['processed_at'],
    'test_type': result['test_type'],
    'score': result['score'],
    'max_score': result.get('max_score', 12),
    'scoring_version': result.get('evaluation', {}).get('version', 'v1'),
    'result_s3_key': result_key,
    'video_info': result['video_info'],
    'health_check': result['health_check'],  # ← 保存される
    'evaluation': result.get('evaluation', {}),
    'ttl': int(datetime.now().timestamp()) + (90 * 24 * 60 * 60)
}
# quality_metrics の保存処理がない ← 問題箇所
```

### 設計判断の推測
- **当初の設計**: S3を詳細データの保存先、DynamoDBを軽量インデックスとして設計
- **想定**: `quality_metrics`は詳細データとしてS3のみに保存
- **結果**: DynamoDBベースの品質分析が困難になった

---

## 対応方針

### 短期対応（現在実施済み）
**回避策**: S3結果JSONファイルから`quality_metrics`を直接取得
- **実装**: `scripts/monitoring/analyze_quality_from_s3.py`
- **メリット**: 2025-11-01以降の全データが利用可能（N=26）
- **デメリット**: クエリが遅い（S3 GetObject × N回）

### 中期対応（推奨）
**修正**: `save_to_dynamodb()`に`quality_metrics`保存を追加

**実装案**:
```python
item = {
    # 既存フィールド
    'video_id': f"{bucket}/{video_key}",
    'processed_at': result['processed_at'],
    # ... (省略) ...
    'health_check': result['health_check'],
    'quality_metrics': result.get('quality_metrics', {}),  # ← 追加
    'evaluation': result.get('evaluation', {}),
    'ttl': int(datetime.now().timestamp()) + (90 * 24 * 60 * 60)
}
```

**影響範囲**:
- 変更ファイル: `src/handler.py` (1箇所)
- テスト: 動画処理の統合テスト
- デプロイ: 次回リリース時に含める

**注意点**:
- DynamoDB項目サイズ制限（400KB）に注意
- `quality_metrics`のサイズは通常200-300バイト程度（問題なし）

### 長期対応（検討）
**設計見直し**: データ保存戦略の明確化
- DynamoDB: 高速クエリが必要な軽量データ
- S3: 詳細データ・履歴保存
- `quality_metrics`をどちらに保存するか、設計ドキュメントに明記

---

## 検証結果

### 2025-11-06時点の状況
- **DynamoDBレコード数**: 1件（2025-11-05以降）
- **S3結果ファイル数**: 26件（2025-11-01以降）
- **quality_metricsの取得**: S3からのみ可能

### S3ベース分析結果（概要）
- **データ件数**: 26件
- **detection_rate**: 平均1.0（全件で完全検出）
- **quality_score**: 平均87.3、範囲81-95（高品質）
- **is_quality_ok=False**: 15/26件（57.7%）
- **recommend_retake=True**: 0件

**詳細**: `docs/monitoring/quality_metrics_analysis.md`参照

---

## アクションアイテム

- [x] **優先度中**: `save_to_dynamodb()`を修正（`quality_metrics`追加） - ✅ 2025-11-06完了
- [ ] **優先度低**: データ保存戦略を設計ドキュメントに明記
- [ ] **優先度低**: DynamoDB項目サイズ監視の追加（将来的なサイズ超過を検知）

---

## ✅ 解消報告（2025-11-06）

### 実施内容
**Phase 2実装**: src/handler.py:723にquality_metrics保存を追加

**変更内容**:
```python
'quality_metrics': result.get('quality_metrics', {}),  # Phase 2: 品質メトリクス保存
```

### 影響範囲
- **変更ファイル**: src/handler.py (1行追加)
- **デプロイ**: 次回リリース時に有効化
- **検証**: テスト動画処理後にDynamoDBレコード確認

### 期待される効果
- DynamoDBクエリでquality_scoreが取得可能
- リアルタイム品質監視が可能
- S3スキャン不要で高速分析

---

## 関連ドキュメント
- 分析結果: `docs/monitoring/quality_metrics_analysis.md`
- 分析スクリプト: `scripts/monitoring/analyze_quality_from_s3.py`
- ソースコード: `src/handler.py:683` (`save_to_dynamodb()`)
- DynamoDB修正検証: `docs/monitoring/dynamodb_fix_result.md`

---

**記録日時**: 2025-11-06
**最終更新**: 2025-11-06
