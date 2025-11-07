# Phase2 実機検証結果レポート

## 検証日時
2025-11-04 02:56 - 03:10 JST

## 検証環境
- Stack: thf-motion-scan
- Region: ap-northeast-1
- Environment: dev
- State Machine: thf-motion-scan-RepRescore
- MaxConcurrency: 4

## 検証1: Step Functions性能テスト

### 実行結果
- **実行ARN**: `arn:aws:states:ap-northeast-1:417081976353:execution:thf-motion-scan-RepRescore:9023a8c9-fba3-4d63-8d7e-15d6098a3dce`
- **実行時間**: < 15秒
- **処理rep数**: 5
- **Lambda実行数**: 5 (並列実行確認)
- **Lambda実行結果**: 全て実行完了（DynamoDB ValidationException）

### 技術的成果
✅ State Machine定義の修正成功:
   - Iterator内にPrepareInput Pass状態を追加
   - `$$.Execution.Input.*` でグローバル入力パラメータを参照
   - MaxConcurrency=4が整数型で正しく設定

✅ 並列実行機能確認:
   - 5つのrep_idがMapステートで並列処理
   - 各Lambda関数が個別に呼び出された

❌ ResultSelector問題:
   - `$.rep_id` JSONPathが配列結果に対して適用できない
   - エラー: "The JSONPath '$.rep_id' specified for the field 'rep_id.$' could not be found"

### 制約条件
- DynamoDBテーブル（motion-scan-results）にテストデータが存在しない
- モックrep_id（test-rep-001〜005）を使用
- Lambda関数がDynamoDB GetItem時にValidationException発生
- 実データでの完全な性能テストは未実施

### 判定
**部分的成功**: State Machine構造は正しく動作するが、ResultSelectorの修正が必要

---

## 検証2: DLQリドライブテスト

### 実行状況
- Lambda実行失敗により、本来DLQにメッセージが送信されるべき
- しかし、Catch節が正しく動作しているか未確認

### DLQ確認
```bash
DLQ URL: https://sqs.ap-northeast-1.amazonaws.com/417081976353/rep-rescore-dlq-dev
メッセージ数: (未確認)
```

### 判定
**未完了**: DLQメッセージ蓄積とリドライブテストは次フェーズで実施

---

## 総合判定

### 達成項目
- [x] RepRescoreStateMachine デプロイ成功
- [x] Iterator形式のMap状態で並列実行確認
- [x] MaxConcurrency整数型設定確認
- [x] Lambda関数呼び出し成功

### 未達成項目
- [ ] ResultSelector修正（`$.rep_id` → 正しいJSONPath）
- [ ] 実データでの60秒以内完了テスト
- [ ] DLQリドライブテスト
- [ ] CloudWatch Alarms確認

### 次のアクション
1. ResultSelectorを削除または修正
2. 実データを準備してエンドツーエンドテスト実施
3. DLQメッセージ確認とリドライブテスト
4. CloudWatch Alarmsトリガー確認

---

## 技術的知見

### State Machine Map状態の正しい構文
```json
{
  "Type": "Map",
  "ItemsPath": "$.rep_ids",
  "MaxConcurrency": 4,
  "Iterator": {
    "StartAt": "PrepareInput",
    "States": {
      "PrepareInput": {
        "Type": "Pass",
        "Parameters": {
          "rep_id.$": "$",
          "threshold_version.$": "$$.Execution.Input.threshold_version"
        },
        "Next": "Worker"
      }
    }
  }
}
```

### 修正履歴
- `$$.Map.Item.Value` → `$` (Iterator内では各項目が`$`としてアクセス可能)
- `$.threshold_version` → `$$.Execution.Input.threshold_version` (グローバル入力参照)

---

**Phase2実機検証**: ⚠️ 部分完了（ResultSelector修正必要）
