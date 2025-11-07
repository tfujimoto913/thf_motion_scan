# Ground Truth Data Management Guide

## 目的
- 運用系 CloudWatch メトリクスと同様に、Ground Truth (GT) メトリクスを定量化・送信するための生データ保管ポリシーを定義する  
- BCR / κ / Override 指標を算出するためのレビュー結果を一元管理し、後続の自動化 (Stage 5) に備える  
- 匿名化・保存期間・取り扱い手順を明文化し、レビュープロセスの属人化を防ぐ

## S3 構造
```
s3://thf-motion-scan-gt/{env}/evaluations/{YYYY-MM-DD}/{session_id}.json
```
- `{env}`: `dev` / `stg` / `prod`
- ファイル単位で 1 セッションのレビュー結果を保存
- サンプル: `docs/monitoring/gt_sample.json`

## スキーマ概要
| フィールド        | 型      | 必須 | 説明                                           |
|------------------|---------|------|------------------------------------------------|
| `athlete_id`     | string  | ✅ | 匿名化済みの選手 ID (例: `ath-0001`)           |
| `session_id`     | string  | ✅ | セッション ID (例: `20240301-0800-A`)          |
| `test_code`      | string  | ✅ | Tコード (例: `T01_single_leg_squat`)           |
| `ai_score`       | number  | ✅ | AI 自動判定スコア                              |
| `human_score`    | number  | ✅ | コーチ／審査員による最終スコア                 |
| `override_flag`  | boolean | ✅ | 人手で上書きが発生したか                       |
| `reviewer`       | string  | ✅ | レビュー担当者の識別子 (社内 ID)               |
| `rules_version`  | string  | ✅ | 対象ルールバージョン (例: `v2.1.0`)           |
| `artifact_sha`   | string  | ✅ | 評価コードのコミット SHA                        |
| `created_at`     | string  | ✅ | ISO8601 タイムスタンプ (UTC)                   |
| `notes`          | array   | 任意 | レビュー時の補足メモ (例: `["膝角度計測に再確認必要"]`) |

## 週次レビュー フロー (10件目標)
1. **月曜 10:00 JST**: DynamoDB `motion-scan-results` から直近 7 日間の候補を抽出 (詳細は「週次抽出 CLI」参照)  
2. 抽出リストを QA / コーチチームに共有し、同日夕方までに最終 10 件を確定  
3. レビュー担当が `dev` バケットへ JSON をアップロード (1 ファイル = 1 セッション)  
4. 完了後、Slack `#thf-monitoring` へ完了報告 (件数 / reviewer / 未処理セッション)  
5. レビュー内容を `notes` に記録し、翌週レビュー対象が重複しないよう `review_list.csv` を更新

## 保存期間と匿名化
- 保存期間: **90日** (S3 Lifecycle で自動削除予定)  
- 個人特定情報は格納しない (athlete_id / reviewer は匿名 ID を使用)  
- 生データは dev → stg → prod の順にサンプリングし、本番導入前に QA が目視確認

## 取り扱い注意事項
- IAM 権限は Stage 5 で Lambda に付与予定 (現状は手動アップロードのみ)  
- JSON の整合性は `scripts/monitoring/validate_gt_schema.py` で lint 可能  
- 誤って個人情報をアップロードした場合は直ちに削除 & セキュリティ担当へ報告

## 週次抽出 CLI (次タスク準備)
- スクリプト: `scripts/monitoring/extract_gt_sessions.py`（次ステップで実装予定）  
- 要件:
  1. DynamoDB `motion-scan-results` から直近 7 日のセッションを取得 (PK: `video_id`, SK: `processed_at`)  
  2. ランダム or スコア差異優先で 10 件をサンプリング  
  3. 元動画の S3 署名付き URL を発行 (有効期限 24h)  
  4. `docs/monitoring/review_list.csv` 形式で出力 (session_id, test_code, score, signed_url, candidate_notes)
- 初回実行: **2025-11-11 (月) dev 環境** でスクリプトを試行し、フローを検証する
