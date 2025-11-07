# DynamoDB保存修正結果

**修正日時**: 2025-11-06
**対象環境**: dev
**対象テーブル**: `motion-scan-results`

---

## 問題の原因

### 根本原因

**タイミング問題**: 2025-11-01の動画処理時点では、DynamoDB権限が未追加だった

- **動画処理日時**: 2025-11-01 08:38-08:43 UTC
- **CloudFormation更新**: 2025-11-05 16:43 UTC
- **DynamoDB権限追加**: 2025-11-05 16:43 UTC（CloudFormation更新時）

### 詳細分析

#### ✅ コード側の実装
- `src/handler.py:286` で `save_to_dynamodb()` が正しく呼び出されている
- 関数実装も問題なし

#### ✅ template.yaml定義
```yaml
ProcessingFunction:
  Policies:
    - S3ReadPolicy:
        BucketName: !Sub 'thf-motion-scan-videos-${AWS::AccountId}'
    - S3CrudPolicy:
        BucketName: !Sub 'thf-motion-scan-results-${AWS::AccountId}'
    - DynamoDBCrudPolicy:
        TableName: !Ref ResultsTable  # ← 現在は存在
    - DynamoDBCrudPolicy:
        TableName: !Ref RepsTable
```

#### ✅ IAM権限の確認結果
```json
{
  "Statement": [
    {
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:DeleteItem",
        "dynamodb:PutItem",        # ← 必要な権限あり
        "dynamodb:Scan",
        "dynamodb:Query",
        "dynamodb:UpdateItem",
        "dynamodb:BatchWriteItem",
        "dynamodb:BatchGetItem",
        "dynamodb:DescribeTable",
        "dynamodb:ConditionCheckItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:ap-northeast-1:417081976353:table/motion-scan-results",
        "arn:aws:dynamodb:ap-northeast-1:417081976353:table/motion-scan-results/index/*"
      ],
      "Effect": "Allow"
    }
  ]
}
```

### 結論

❌ **問題**: 2025-11-01時点では、template.yamlに `DynamoDBCrudPolicy` が未追加だった
✅ **現状**: 2025-11-05のデプロイ以降、DynamoDB権限が追加され、正常に保存されるようになった

---

## 実施した修正

### 修正内容

**修正なし** - template.yamlには既にDynamoDB権限が存在

### デプロイ

**デプロイ不要** - 2025-11-05のCloudFormation更新で既に反映済み

---

## 動作確認結果

### テスト実行

**テスト動画**: `test_dynamodb_verification_20251106_020755.mp4`
**アップロード日時**: 2025-11-06 02:07:55 JST
**処理完了**: 2025-11-05 17:11:26 UTC（約3分）

### DynamoDB保存結果

**✅ 成功**: レコード数 = 1

#### 保存されたレコード

```json
{
  "video_id": "thf-motion-scan-videos-417081976353/videos/single_leg_squat/test_dynamodb_verification_20251106_020755.mp4",
  "processed_at": "2025-11-05T17:11:26.465792",
  "test_type": "single_leg_squat",
  "score": 55.2,
  "max_score": 80,
  "scoring_version": "v2.1",
  "result_s3_key": "results/2025/11/05/test_dynamodb_verification_20251106_020755_20251105_171126.json",
  "ttl": 1770138686,
  "video_info": {
    "fps": 57.86856913512495,
    "duration": 16.278266666666667,
    "detected_frames": 942,
    "frame_count": 942
  },
  "health_check": {
    "detected_frames": 942,
    "detection_rate": 1.0,
    "is_quality_ok": false,
    "low_visibility_frames": 289,
    "total_frames": 942,
    "low_visibility_landmarks_count": 7269
  },
  "evaluation": {
    "version": "v2.1",
    "A_execution_score": 20.0,
    "B_total": 35.2,
    "total_score": 55.2,
    "total_percentage": 69,
    "max_possible": 80,
    "A_breakdown": {
      "knee_flexion_angle": 10.0,
      "completion_reps": 10.0
    },
    "B_principles": {
      "eccentric": {
        "B1_core_stability": ...,
        "B2_support_foundation": 5.0,
        "B3_3joint_coordination": ...,
        "B4_pelvis_horizontal": ...
      },
      "concentric": {
        ...
      }
    }
  }
}
```

#### 刻印されたメタデータ

| フィールド | 値 | 説明 |
|-----------|-----|------|
| `scoring_version` | `v2.1` | スコアリングバージョン |
| `ttl` | `1770138686` | TTL（90日後に自動削除） |
| `evaluation.version` | `v2.1` | 評価システムバージョン |
| `test_type` | `single_leg_squat` | テストタイプ |
| `result_s3_key` | `results/2025/11/05/...` | S3結果ファイルへの参照 |

**注**: `rules_version`, `thresholds_version`, `artifact_sha` は evaluation 内に含まれていない（将来的に追加が望ましい）

---

## 検証完了確認

### ✅ 動作確認項目

- [x] DynamoDBにレコードが保存される
- [x] 主キー（video_id, processed_at）が正しく設定される
- [x] TTLが設定される（90日後に自動削除）
- [x] スコアリングバージョン（v2.1）が記録される
- [x] 評価詳細（evaluation）が保存される
- [x] 健康チェック結果（health_check）が保存される
- [x] S3結果ファイルへの参照（result_s3_key）が記録される

### ⚠️ 将来の改善点

1. **バージョンメタデータの追加**
   - `rules_version`: 評価ルールバージョン
   - `thresholds_version`: 閾値バージョン
   - `artifact_sha`: デプロイされたコードのSHA

   **推奨**: トップレベルフィールドとして追加（evaluation内ではなく）

2. **GSI（Global Secondary Index）の活用**
   - 現在: PK=video_id, SK=processed_at のみ
   - 提案: `athlete_id`, `session_id`, `test_type` でのクエリ用GSI追加

3. **Rep単位データの保存**
   - `REPS_TABLE_NAME` (`motion-scan-reps`) へのRep単位保存
   - 現在は未実装（コードは存在するが、実行されていない）

---

## まとめ

### 問題の本質

**タイミング問題**: 2025-11-01の動画処理時には、DynamoDB権限が未追加だった

### 解決状況

**✅ 解決済み**: 2025-11-05のCloudFormation更新でDynamoDB権限が追加され、以降の処理では正常にDynamoDBに保存されている

### 影響範囲

- **過去データ**: 2025-11-01〜2025-11-05の間に処理された動画は、DynamoDBに保存されていない（S3には保存済み）
- **現在**: 2025-11-05以降の処理では正常にDynamoDBに保存される
- **データロスト**: なし（S3に結果ファイルが保存されている）

### 次のアクション

**Option 2: CloudWatch Metricsの実データ確認** → 進行中

---

**確認完了日時**: 2025-11-06 02:11 JST
**所要時間**: 約15分
**次のステップ**: Option 2（CloudWatch Metricsの実データ確認）へ進む
