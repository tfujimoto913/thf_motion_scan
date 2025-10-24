# THF Motion Scan - AWS デプロイガイド

## 📋 概要

THF Motion ScanをAWS Serverlessアーキテクチャにデプロイする手順書です。

## 🏗️ アーキテクチャ

```
S3 (Videos) → SQS → Lambda (Container) → S3 (Results) + DynamoDB
```

### コンポーネント
- **S3**: 動画アップロード＆結果保存
- **SQS**: 非同期処理キュー
- **Lambda**: MediaPipeによる動画解析（Container Image）
- **DynamoDB**: 処理結果のメタデータ保存

---

## ✅ 前提条件

- [x] AWSアカウント
- [x] AWS CLI（v2.31.20+）
- [x] AWS SAM CLI（v1.145.2+）
- [x] Docker Desktop（v28.5.1+）
- [x] IAM認証設定完了（`aws configure`）

---

## 🚀 デプロイ手順

### Step 1: ECRリポジトリ作成

```bash
# ECRリポジトリを作成
aws ecr create-repository --repository-name thf-motion-scan --region ap-northeast-1

# ECRログイン
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin \
  417081976353.dkr.ecr.ap-northeast-1.amazonaws.com
```

### Step 2: Dockerイメージをビルド＆プッシュ

```bash
# SAM buildでイメージをビルド
sam build

# イメージをECRにプッシュ
docker tag thf-motion-scan:latest \
  417081976353.dkr.ecr.ap-northeast-1.amazonaws.com/thf-motion-scan:latest

docker push 417081976353.dkr.ecr.ap-northeast-1.amazonaws.com/thf-motion-scan:latest
```

### Step 3: SAMデプロイ

```bash
# 初回デプロイ（ガイド付き）
sam deploy --guided

# 2回目以降
sam deploy
```

### Step 4: 動作確認

```bash
# S3バケット名を取得
aws cloudformation describe-stacks \
  --stack-name thf-motion-scan \
  --query 'Stacks[0].Outputs[?OutputKey==`VideosBucketName`].OutputValue' \
  --output text

# テスト動画をアップロード
aws s3 cp test_video.mp4 s3://thf-motion-scan-videos-417081976353/videos/single_leg_squat/test.mp4

# Lambda実行ログを確認
sam logs -n ProcessingFunction --stack-name thf-motion-scan --tail
```

---

## 🧪 ローカルテスト

### ローカルでDockerイメージを実行

```bash
# イメージをビルド
docker build -t thf-motion-scan:local .

# ローカルで実行（テスト用）
docker run --rm \
  -e RESULTS_BUCKET=test-bucket \
  -e TABLE_NAME=test-table \
  thf-motion-scan:local
```

### SAM Localでテスト

```bash
# Lambda関数をローカル実行
sam local invoke ProcessingFunction \
  -e events/s3-event.json

# APIとして起動
sam local start-api
```

---

## 📊 モニタリング

### CloudWatch Logs

```bash
# Lambda関数のログを確認
sam logs -n ProcessingFunction --stack-name thf-motion-scan --tail

# 特定の時間範囲のログ
sam logs -n ProcessingFunction --start-time '10 minutes ago' --end-time 'now'
```

### CloudWatch Metrics

- Lambda実行時間
- Lambda失敗回数
- SQSキューの深さ
- DynamoDBの書き込み数

---

## 🛠️ トラブルシューティング

### Lambdaがタイムアウトする

```yaml
# template.yamlで調整
Globals:
  Function:
    Timeout: 900  # 最大15分
    MemorySize: 3008  # メモリ増量
```

### Dockerイメージが大きすぎる

```bash
# 不要な依存関係を削除
# requirements.txtを見直す
# --no-cache-dirを使用
```

### DLQにメッセージが溜まる

```bash
# デッドレターキューを確認
aws sqs receive-message \
  --queue-url https://sqs.ap-northeast-1.amazonaws.com/417081976353/thf-motion-scan-dlq

# エラーログを調査
sam logs -n ProcessingFunction --filter ERROR
```

---

## 🗑️ クリーンアップ

```bash
# スタックを削除
sam delete --stack-name thf-motion-scan

# S3バケットを空にして削除
aws s3 rm s3://thf-motion-scan-videos-417081976353 --recursive
aws s3 rb s3://thf-motion-scan-videos-417081976353

aws s3 rm s3://thf-motion-scan-results-417081976353 --recursive
aws s3 rb s3://thf-motion-scan-results-417081976353

# ECRイメージを削除
aws ecr delete-repository \
  --repository-name thf-motion-scan \
  --region ap-northeast-1 \
  --force
```

---

## 📈 コスト試算

### 無料枠（12ヶ月）
- Lambda: 月100万リクエスト、40万GB-秒
- S3: 5GB、20,000 GETリクエスト
- DynamoDB: 25GB、25 WCU、25 RCU

### 想定コスト（100動画/月の場合）
- Lambda: $5-10/月（実行時間による）
- S3: $1-2/月
- DynamoDB: $0-1/月
- 合計: **約$6-13/月**

---

## 🔒 セキュリティ

### IAMポリシーの最小権限化

```yaml
Policies:
  - S3ReadPolicy:
      BucketName: !Sub 'thf-motion-scan-videos-${AWS::AccountId}'
  - S3CrudPolicy:
      BucketName: !Sub 'thf-motion-scan-results-${AWS::AccountId}'
  - DynamoDBCrudPolicy:
      TableName: !Ref ResultsTable
```

### データ暗号化

- S3: SSE-S3（デフォルト）
- DynamoDB: 保存時暗号化（デフォルト）

---

## 📞 サポート

問題が発生した場合:
1. CloudWatch Logsを確認
2. DLQを確認
3. GitHub Issueを作成

---

**バージョン**: 1.0.0  
**最終更新**: 2025-10-24
