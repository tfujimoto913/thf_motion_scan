# Rep CLI Changelog

versions差分を扱うための変更ログ

## v0.2.0 (2025-11-02) - Overlay Release

### Added
- 画像オーバーレイ実装（best.png/worst.png/median.png）
- 肩線・骨盤線・体幹軸描画（OpenCV使用）
- Class注記・スコア注記（視覚的フィードバック）
- 可視性ガード（check_visibility関数、閾値=0.5）
- 可視性不足時の flags=["low_visibility"] 付与
- --overlay フラグ機能実装（true/false制御）
- テスト3件追加（draw_overlay, check_visibility）

### Design Decisions
- 肩線（緑）、骨盤線（青）、体幹軸（黄）で色分け
- Class注記："pass (p=0.92)" 形式（左上）
- スコア注記："Score: 75.0" 形式（左上2行目）
- 可視性閾値：0.5（肩・hip・鼻の全てが閾値以上で描画）
- 動画再読込：代表フレームインデックスで直接アクセス

### Deferred
- 回旋矢印（体幹回旋角の符号で左右描き分け）

## v0.1.0 (2025-11-02) - MVP Release

### Added
- CLI骨格実装（argparse、--video/--out-dir/--dump-trace フラグ）
- 入力検証・エラーハンドリング（FileNotFoundError、原因＋次アクション提示）
- PoseExtractor統合（動画→ランドマーク抽出）
- BodyNormalizer統合（base_width計算、body scale normalization）
- SingleLegSquatEvaluatorV2統合（8原則・80点満点評価）
- 代表フレーム抽出（best/worst/median、overall scoreベース）
- JSON出力（result.json：scores, class, versions, representative_frames）
- CSV出力（trace.csv：時系列データ、--dump-trace フラグで制御）
- versions フィールド（rules_version, normalization_version, artifact_sha）
- README、Runbook、CHANGELOG
- テスト12件（argparse、pipeline、frames、export）

### Design Decisions
- MVP: single_leg_squat のみ対応（T01）
- 代表フレーム：overall scoreでランキング（best=max, worst=min, median=middle）
- base_width：最初のフレームから計算（簡易実装）
- 分類閾値：pass>=60/80 (75%), needs_improvement>=40/80 (50%)
- trace.csv：evaluator の frame_data から抽出（MVP段階の制約）

### Deferred
- 画像オーバーレイ（肩線・骨盤線・角度値・class注記）
- 全テストタイプ対応（T02-T07）
- バッチ処理
- CI統合（artifact_sha自動埋め込み）

### Breaking Changes
None (初回リリース)

### Known Issues
- trace.csv: evaluator が frame_data を提供しない場合は空（ヘッダーのみ）
- 画像オーバーレイ未実装（--overlay フラグは将来対応）
- 単一テストタイプ（single_leg_squat）のみ

## Future Versions

### v0.2.0 (予定)
- 全テストタイプ対応（T02-T07）
- 画像オーバーレイ実装（肩線・骨盤線・角度値・class注記）
- base_width計算の改善（median使用）

### v0.3.0 (予定)
- バッチ処理対応
- CI統合（artifact_sha自動埋め込み）
- パフォーマンス最適化
