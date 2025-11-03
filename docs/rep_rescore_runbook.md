# Rep Rescore Step Functions Runbook

## 起動手順
1. API Gateway エンドポイント (POST `/admin/rep-rescore`) に以下の JSON を送信:
   ```json
   {
     "rep_ids": ["rep-0001", "rep-0002"],
     "threshold_version": "v2.1",
     "artifact_sha": "<GitSHA>"
   }
   ```
   - `rep_ids` を省略すると DynamoDB から全件取得（最大 1000 件）。
   - レスポンスには `execution_id` / `state_machine_execution_arn` / 対象件数が返る。
2. Step Functions コンソールで実行状況を監視。Map State が並列で `RepRescoreWorker` を呼び出す。

## 差分レポート確認
- S3 バケット: `thf-motion-scan-reports-<account>`
- プレフィックス: `diffs/<execution_id>/`
- 生成ファイル:
  - `summary.json`: 件数・平均差分・再分類件数などの概要。
  - `details.csv`: rep 単位の delta サマリ。
  - `failures.jsonl`: 再採点失敗分 (DLQ 転送済み)。

## DLQ リドライブ
1. SQS キュー `rep-rescore-dlq-<env>` を確認し、メッセージが存在する場合に `RepRescoreDLQRedrive` Lambda を手動実行。
2. ペイロード例:
   ```json
   { "max_messages": 5 }
   ```
3. Lambda が再実行をトリガーしたメッセージは DLQ から削除され、新しい Step Functions 実行が起動。

## Rollback
1. 直近の差分レポートで `reclassified_count` が高い場合、`VERSION_TOGGLE` を旧バージョンに戻し再実行。
2. 最新 thresholds が問題であれば、S3 / GitOps 上で旧 thresholds に差し替えてから `RepRescoreLauncher` を再度実行。
3. Canary 監視条件 (BCR > 10%、κ < 0.6、override > 15%) が継続する場合は `docs/canary_monitoring.md` に従って Phase 0-3 へ切り戻し。

## 参考
- Step Functions 定義: `template.yaml` (`RepRescoreStateMachine`)
- Lambda 実装: `lambda/rep_rescore/`
- QC Gate と撮影基準: `docs/phase0-4_deployment_rules.md`, `docs/filming_guide_v2.md`
