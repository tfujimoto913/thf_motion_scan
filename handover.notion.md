# Task 1 – Dashboard Guardrails Phase 1

## Context
- Streamlit製ダッシュボードに運用ガードレール（基盤・可視性）を反映する初期対応を実施。
- 対象ブランチ: `feature/phase5-complete` / 実行環境: `prod` セレクタのみ有効。
- 検証: `python -m compileall dashboard` を実行し構文チェックを通過。

## Task
- サイドバーに環境セレクタを追加し、将来の dev/staging 切替に対応できるリソース解決基盤を整備。
- 一覧・詳細ビューの双方で `rules_version` / `scoring_version` を表示し、不整合時に警告を提示。
- Health Check を基にした品質ステータス判定を共通化し、一覧にバッジ表示を追加。

## Notes
### Diff Summary
- `dashboard/config.py`: 環境辞書の生成を抽象化し、`DEFAULT_ENV`/`get_available_environments` を追加。prod/非prodの命名規則に沿ったリソース解決を実装。
- `dashboard/app.py`: 環境セレクタ、バージョン抽出/整形、品質ステータス判定のヘルパーを追加。結果一覧にバージョン・品質列を追加し、詳細ビューでも警告表示を統一。
- `dashboard/app.py`: Health Check の表示ロジックを共通関数化し、警告/エラー判定を `is_valid`・検出率・警告リストに基づいて統一。

### Next Actions
- [ ] dev / staging 用のリソース命名を本番アカウントに合わせて登録し、セレクタを有効化。
- [ ] `rules_version` / `scoring_version` の基準値を playlist/rules から取得し、不整合条件を正式定義。
- [ ] CloudWatch メトリクスやDLQと連動したアラート表示（Phase 3想定）を追加実装。

# Task 2 – Dashboard Guardrails Phase 2

## Context
- Phase 1での基盤をベースに、欠損データのフォールバックとバージョン互換性ガードを追加。
- 既存の比較・詳細UIに影響が出ないことを確認するため `python -m compileall dashboard` にて構文検証。

## Task
- DynamoDB/評価データ欠損時の表示強化（"データ未取得"、ユーザー向けメッセージ、技術者向けスタック情報）。
- `rules_version` の SemVer 解析と互換性判定ヘルパーを追加し、比較・レーダーチャートでのバージョンガードを実装。
- レーダーチャート（v2.1原則スコア）を表示し、互換性が無い場合は警告＋ユーザー承認での続行オプションを提供。

## Notes
### Diff Summary
- `dashboard/app.py`: 欠損値フォールバック、互換性チェック、レーダーチャート描画、比較セクションのユーザー承認フローを実装。新規ヘルパー（SemVer解析・スコア集計）を追加。
- `dashboard/config.py`: 影響なし（Phase 1の内容維持）。

### Next Actions
- [ ] DynamoDBレスポンスをモックしたpytestを整備し、欠損ケースの回帰テストを追加。
- [ ] レーダーチャートの軸定義を正式な7原則スコアリング仕様に合わせて拡張。
- [ ] Streamlit上での互換性警告テキストをi18n化し、文言レビューを実施。

# Task 3 – Dashboard Guardrails Phase 3

## Context
- 可観測性とパフォーマンス向上の要件を中心に、ロギング・キャッシュ・健全性チェックを強化。
- 追加の診断UI（デバッグ/管理者モード）を導入し、運用オペレーションで必要な情報を即時把握できるようにした。
- 検証: `python -m compileall dashboard` を実行し構文チェックを通過。

## Task
- 構造化ロギング: `utils.logging` にJSONフォーマッタとイベントヘルパーを実装し、一覧/詳細/比較/レーダー/アップロードなど主要イベントで `request_id`・`event_type`・`rules_version` を含むログを出力。
- パフォーマンス制限とキャッシュ: `config.PERFORMANCE_LIMITS` に閾値を定義し、サイドバーで件数・期間の調整、キャッシュTTL(5分)と手動クリアボタンを提供。DynamoDB読込は `st.cache_data` + `data_loader.py` で集約化。
- レスポンス計測: `execution_timer` を導入し、ページ描画/詳細表示/比較/レーダーなどの処理時間をロギング。デバッグモード時には画面下部に実行時間を表示し、800ms超過は警告ログを出力。
- 健全性と管理者向けUI: 管理者モードを追加し、S3/DynamoDB接続チェック、バージョン不整合率、最近のエラーログをサイドバーに集約表示。

## Notes
### Diff Summary
- `dashboard/utils/logging.py`, `utils/__init__.py`: JSONロガー、タイマー、エラーログ記録APIを追加し、他モジュールから共通利用可能に。
- `dashboard/data_loader.py`: DynamoDB取得をキャッシュ化し、キャッシュヒット/ミス・エラーを構造化ログ＋エラーログに反映。
- `dashboard/app.py`: パフォーマンス設定UI、デバッグ/管理者モード、ヘルスチェック、エラー記録、一覧/詳細/比較/レーダーへの計測とログ出力を実装。`perform_health_checks` でS3/DynamoDB疎通を確認。
- `dashboard/session_pages.py`: 新しいデータローダとエラーログ記録に対応。

### Next Actions
- [ ] CloudWatch Logs/Metrics 連携を構成し、構造化ログをモニタリング基盤へ転送。
- [ ] キャッシュヒット率・レスポンスタイムを可視化するダッシュボードを別途整備。
- [ ] ヘルスチェックの対象にSQSやLambda実行状況を追加し、運用Runbookと紐付ける。
