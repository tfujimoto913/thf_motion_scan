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

# Task 4 – Ops Guardrails Phase 5 Completion

## Context
- Phase 5 Opsカード（Notion: 1701b3b9c24e4e9eaa225c5a7ee8a0fc）に基づき、CloudWatchダッシュボード/アラーム、SNSトピック、DLQ Runbook、構造化ログ＆カスタムメトリクスをIaC＋コード双方へ実装。
- `sam validate` を通過（~/.aws-sam/metadata.json 書き込み権限警告ありだがテンプレートは有効）。
- `python3 -m compileall` で `src`, `processing`, `lambda/*`, `scripts/redrive.py` を構文チェック済み。

## Task
- `template.yaml` にSNSトピック、INFO/WARN/ERROR/METRICS各LogGroup、4種アラーム、`MotionScan-Ops-<env>`ダッシュボードを追加し、環境/閾値/Retentionをパラメータ化。
- StructuredLoggerを共通化（`lambda/common/structured_logging.py`）し、Processing/UploadUrl Lambdaから必須フィールドを含むJSONログとカスタムメトリクス（VideoAnalysisDuration, LandmarkDetectionRate, PresignedUrlGenerationDuration 等）を送出。X-Rayサブセグメント（video_processing, score_calculation）を追加。
- DLQ再投入スクリプト（`scripts/redrive.py`）とRunbook（`docs/runbooks/dlq_redrive.md`）を作成し、停止条件（同一原因5連続・UserErrorsスパイク・MaxBatch等）とメトリクス発行（RedriveSuccessCount/FailureCount）を自動化。

## Notes
### Diff Summary
- `template.yaml`: Parameters/Conditions/Resources 更新、CloudWatch Dashboard JSON刷新、Outputs調整。
- `src/handler.py`, `processing/worker.py`: StructuredLogger適用、X-Ray subsegment挿入、Landmark検出率メトリクス/失敗カウンタ実装。
- `lambda/upload_url/handler.py`: 構造化ログとレスポンス計測、Authorization/Validationログ出力を強化。
- `lambda/common/structured_logging.py`: JSONログ+CloudWatch Logs/metrics送信、およびシーケンストークン管理を実装。
- `scripts/redrive.py`: バッチ制御・停止条件・CloudWatchメトリクス送信を備えた運用スクリプトを追加。
- `docs/runbooks/dlq_redrive.md`: 前提条件、コマンドテンプレート、停止条件、観測ポイント、事後対応を整理。
- `requirements*.txt`, `Dockerfile`: `aws-xray-sdk` 追加、共通モジュールをLambdaコンテナにコピー。

### Next Actions
- [ ] 疑似ERROR（Lambda Errors, LandmarkDetectionFailures, DynamoDB UserErrors）を発火させ、SNS通知・ダッシュボード反映・X-Rayトレースを検証。
- [ ] Slack通知フロー準備後、`thf-alerts-<env>` トピックをChatOpsに接続。
- [ ] `scripts/redrive.py` をステージングDLQでドライランし、Runbook手順と停止条件ログを確認。
- [ ] pytest環境（`pip install -r requirements.txt`）整備後に `python -m pytest` を実行し、構造化ロギング変更の回帰テストを追加検討。

# Task 5 – Session Detail Polish (Phase 5 Stage 3 Micro-Adjustments)

## Context
- Notion Stage 3 タスク（欠測表示・バージョン情報拡充・ラベリング統一・UIメトリクス）を実装。
- `python3 -m compileall dashboard` にて構文チェック済み。

## Task
- 欠測を含むレーダーチャートで 0% 塗り潰しを回避し、グレー点線＋“N/A” ラベルの別トレースで可視化。
- セッション詳細ヘッダーに `rules_version / normalization_version / artifact_sha` を並記し、鮮度表示を「今日 / 1日前 / X日前」に統一。
- test_code → 日本語名称のマッピングを `config.py` の単一ソースに集約し、ヘルプやツールチップでも一貫した表示に変更。
- 環境切替・キャッシュクリア・比較実行などの UI 操作で `UIEvent` カスタムメトリクスを CloudWatch へ送出。

## Notes
### Diff Summary
- `dashboard/utils/logging.py`: `emit_ui_metric` を追加し、Namespace `THF/MotionScan` の `UIEvent` を Environment/TestCode/SessionId 付きで送信。短時間の連続発火を抑制。
- `dashboard/app.py`: 環境セレクタとキャッシュクリアに UIEvent を埋め込み。短縮マップを `config` 依存に揃えるため呼び出しを微修正。
- `dashboard/session_pages.py`: ヘッダー métrics を再構成し、欠測判定とレーダー表示の拡張、比較実行時に UIEvent 送信を実装。差分テーブルも N/A 表示に対応。

### Next Actions
- [ ] CloudWatch 上で `UIEvent` メトリクスが期待通り Dimension（Environment/TestCode/SessionId）付きで記録されるか確認し、運用ダッシュボードを検討。
- [ ] normalization_version / artifact_sha を Lambda 生成物で必ず埋め込むようワークフローを整備（未設定時は UI 上 “mixed/‐” 表示）。
- [ ] 欠測が多発するセッションの割合を算出し、さらに視覚化（例: 欠測ヒートマップ）するアイデアを検討。
