# データソース実在確認結果（dev環境）

**確認日時**: 2025-11-06
**対象環境**: dev
**AWS Account**: 417081976353
**AWS Region**: ap-northeast-1

---

## 1. CloudWatch Logs

### 実在確認
✅ **確認済み** - 構造化ログシステムが稼働中

### Log Groups

| Log Group | 用途 | ログ形式 | 実在確認 |
|-----------|------|---------|---------|
| `/thf/motion-scan/dev/logs/info` | 情報ログ | 構造化JSON | ✅ 存在（現時点では空） |
| `/thf/motion-scan/dev/logs/warn` | 警告ログ | 構造化JSON | ✅ 存在（現時点では空） |
| `/thf/motion-scan/dev/logs/error` | エラーログ | 構造化JSON | ✅ 存在（現時点では空） |
| `/thf/motion-scan/dev/logs/metrics` | メトリクスログ | 構造化JSON | ✅ 存在（現時点では空） |
| `/aws/lambda/thf-motion-scan-ProcessingFunction` | Lambda標準ログ | 非構造化 | ✅ 存在（データあり） |

### 構造化ログフォーマット

**ログキー一覧**:
```json
{
  "timestamp": "ISO8601 UTC",
  "level": "INFO|WARNING|ERROR",
  "message": "string",
  "requestId": "string|null",
  "environment": "dev|stg|prod",
  "testCode": "string|null",
  "athleteId": "string|null",
  "sessionId": "string|null",
  "functionName": "string",
  "rulesVersion": "string|null",
  "artifactSha": "string|null",
  "payload": "object|null",
  "error": {
    "type": "string",
    "message": "string"
  }
}
```

### 実装ファイル
- **Logger**: `lambda/common/structured_logging.py`
- **Adapter**: `processing/logger.py`

### 注意事項
⚠️ 当初想定していた `/aws/lambda/thf-motion-evaluator-*` というLog Groupは存在しない
→ 代わりに `/thf/motion-scan/dev/logs/*` を使用する構造化ログシステムが実装されている

---

## 2. DynamoDB

### 実在確認
✅ **確認済み** - テーブルは存在（現時点では空）

### テーブル情報

**テーブル名**: `motion-scan-results`
**項目数**: 0（未使用）
**リージョン**: ap-northeast-1

### 主キー構造

| キー種別 | 属性名 | 型 | 説明 |
|---------|--------|-----|------|
| HASH | `video_id` | String | `{bucket}/{video_key}` 形式 |
| RANGE | `processed_at` | String | ISO8601形式タイムスタンプ |

### GSI（Global Secondary Index）

| GSI名 | PK | SK |
|-------|----|----|
| GSI2 | `GSI2PK` (String) | `GSI2SK` (String) |

### カラム構造

**基本カラム**:
- `video_id` (String) - 主キー
- `processed_at` (String) - ソートキー
- `test_type` (String) - テストタイプ（single_leg_squat等）
- `score` (Number/Decimal) - スコア
- `max_score` (Number/Decimal) - 最大スコア（v1: 12, v2.1: 80）
- `scoring_version` (String) - スコアリングバージョン（v1, v2.1）
- `result_s3_key` (String) - S3結果キー
- `ttl` (Number) - TTL（90日後に自動削除）

**オプションカラム**:
- `athlete_id` (String) - アスリートID
- `session_id` (String) - セッションID
- `team_id` (String) - チームID

**ネストされた構造**:

**`video_info` (Map)**:
- 動画メタデータ（フレーム数、FPS等）

**`health_check` (Map)**:
- `detection_rate` (Number) - ランドマーク検出率
- `frame_count` (Number) - フレーム数
- その他品質指標

**`evaluation` (Map)**:
- `version` (String) - 評価バージョン（v1, v2, v2.1）
- `total_score` (Number) - 総合スコア
- `section_a` (Map) - セクションA評価（21点）
- `section_b` (Map) - セクションB評価（216点、8原則）

**`quality_metrics` (Map)**:
- `landmark_visibility_avg` (Number) - ランドマーク可視性平均（0-1）
- `frame_completeness` (Number) - フレーム完全性（0-1）
- `quality_score` (Number) - 品質スコア（0-100）
- `warnings` (List) - 警告リスト
- `recommend_retake` (Boolean) - 再撮影推奨フラグ

### Reps テーブル

**テーブル名**: `motion-scan-reps`（環境変数 `REPS_TABLE_NAME` で指定）
**実在確認**: ❌ **未作成** - コードには実装されているが、まだデプロイされていない

### 実装ファイル
- **保存処理**: `src/handler.py` - `save_to_dynamodb()`
- **Rep保存**: `src/handler.py` - `save_reps_to_dynamodb()` (未使用)

---

## 3. 閾値定義ファイル

### 実在確認
✅ **確認済み** - 複数の閾値定義ファイルが存在

### ファイル一覧

#### 評価閾値（テストスコア）

**ファイルパス**: `config/thresholds_v2.json`
**バージョン**: 1.0.0
**ルールバージョン**: 2.1.0

**構造**:
```json
{
  "versions": {
    "rules_version": "2.1.0",
    "thresholds_version": "1.0.0",
    "normalization_version": "1.0.0"
  },
  "tests": [
    {
      "code": "overall_score",
      "metric": "overall_score",
      "unit": "score",
      "direction": "higher",
      "primary": {
        "bands": [
          {"name": "pass", "op": "gte", "value": 60},
          {"name": "border", "op": "range_inc", "value": [40, 60]},
          {"name": "fail", "op": "lt", "value": 40}
        ]
      }
    }
  ]
}
```

**現行閾値**:
- **pass**: ≥60点
- **border**: 40-60点
- **fail**: <40点

#### 監視閾値（UI/Billing）

**ファイルパス**: `config/monitoring/base.yaml`
**バージョン**: 1.0.0
**環境別オーバーライド**: `config/monitoring/dev.yaml`, `stg.yaml`, `prod.yaml`

**Billing監視閾値**:
| メトリクス | WARN閾値 | FAIL閾値 | 単位 |
|-----------|---------|---------|------|
| 月次コスト | 4.0 | 5.0 | USD |

**UI監視閾値（base）**:
| メトリクス | WARN閾値（P75） | FAIL閾値（P90） | 単位 |
|-----------|---------------|---------------|------|
| Render Time | 800 | 1200 | ms |
| Error Rate | null（未設定） | null（未設定） | % |
| Availability | 99.0 | 95.0 | % |

**UI監視閾値（dev環境オーバーライド）**:
| メトリクス | WARN閾値（P75） | FAIL閾値（P90） | 単位 |
|-----------|---------------|---------------|------|
| Render Time | 1000 | 1500 | ms |
| Error Rate | 0.10（10%） | 0.20（20%） | % |
| Availability | 95.0 | 90.0 | % |

**Rollback条件**:
- False positive rate増加: +30%
- Critical event miss: 1件以上
- Cost overrun: $5.00超過
- UI degradation: P90>1200ms（3回連続）

**Mini-review triggers**:
- False positive rate: +20%
- Alarm storm: 1時間以内に5件
- Repeated rollback: 7日以内に2回

### 注意事項
⚠️ ユーザーが求めている「BCR」「κ」「override_rate」といったメトリクスの閾値は、これらのファイルには含まれていない
→ これらは別システム（metrics_monitor等）で管理されている可能性がある

---

## 4. SNS Topic/Subscription

### 実在確認
✅ **確認済み** - dev環境用SNS Topicが存在

### Topic情報

**Topic ARN**: `arn:aws:sns:ap-northeast-1:417081976353:thf-alerts-dev`
**環境**: dev
**リージョン**: ap-northeast-1

### Subscription一覧

| Protocol | Endpoint | Status | FilterPolicy |
|----------|----------|--------|--------------|
| email | tfujimoto913@gmail.com | PendingConfirmation（未確認） | なし |
| lambda | arn:aws:lambda:ap-northeast-1:417081976353:function:thf-motion-scan-BillingGuard | Active | なし |

### FilterPolicy詳細

**BillingGuard Lambda Subscription**:
- **FilterPolicy**: null（未設定）
- **FilterPolicyScope**: null（未設定）

→ すべての通知が両方のエンドポイントに配信される

### 期待される通知タイプ（config/monitoring/base.yaml より）

| 通知タイプ | Subject | 用途 |
|-----------|---------|------|
| billing_warn | [WARN] THF Motion Scan - Billing Alert | コスト警告 |
| billing_fail | [FAIL] THF Motion Scan - Billing CRITICAL | コスト超過 |
| ui_performance_warn | [WARN] THF Motion Scan - UI Performance Degradation | UI性能劣化 |

---

## 5. 次工程への引き継ぎ事項

### 確定したデータソースパラメータ

**CloudWatch Logs Insights クエリ用**:
```python
LOG_GROUPS = {
    "warn": "/thf/motion-scan/dev/logs/warn",
    "error": "/thf/motion-scan/dev/logs/error",
    "metrics": "/thf/motion-scan/dev/logs/metrics",
}

LOG_FIELDS = [
    "timestamp", "level", "message", "requestId", "environment",
    "testCode", "athleteId", "sessionId", "functionName",
    "rulesVersion", "artifactSha", "payload", "error"
]
```

**DynamoDB スキャン用**:
```python
TABLE_NAME = "motion-scan-results"
PRIMARY_KEY = {
    "HASH": "video_id",  # format: "{bucket}/{video_key}"
    "RANGE": "processed_at"  # ISO8601 timestamp
}

QUALITY_METRICS_PATH = "quality_metrics"
EVALUATION_PATH = "evaluation"
```

**閾値参照用**:
```python
THRESHOLD_FILES = {
    "evaluation": "config/thresholds_v2.json",
    "monitoring_base": "config/monitoring/base.yaml",
    "monitoring_dev": "config/monitoring/dev.yaml",
}
```

**SNS通知用**:
```python
SNS_TOPIC_ARN = "arn:aws:sns:ap-northeast-1:417081976353:thf-alerts-dev"
SUBSCRIPTIONS = [
    {"protocol": "email", "endpoint": "tfujimoto913@gmail.com"},
    {"protocol": "lambda", "endpoint": "arn:aws:lambda:...BillingGuard"},
]
```

### 未解決事項

1. **BCR/κ/override_rate メトリクスの所在**
   → これらのメトリクスが実際にどこに記録されているかが不明
   → `quality_metrics` や `health_check` には含まれていない
   → 別システム（dashboard/metrics_monitor）のメトリクスの可能性

2. **構造化ログの実データ不足**
   → dev環境のログが現時点で空のため、実際のログ構造を確認できていない
   → 本番データで再確認が必要

3. **Reps テーブル未作成**
   → Rep単位の詳細データを保存するテーブルが未デプロイ
   → 今後のデプロイで作成予定

### 推奨される次ステップ

1. **BCR/κ/override_rate の所在確認**
   - `metrics_monitor.py` や dashboard関連コードを調査
   - CloudWatch Custom Metricsに直接送信されている可能性を確認

2. **実データでの検証**
   - テスト動画を1本処理して実際のログ/DynamoDBエントリを確認
   - P95計算に必要なメトリクスが実際に記録されているか確認

3. **誤検知パターン分析の設計**
   - 警告ログ（`/thf/motion-scan/dev/logs/warn`）のクエリ設計
   - 誤検知の定義を明確化（どのログメッセージが誤検知に該当するか）

---

## 付録: 確認コマンド履歴

### CloudWatch Logs
```bash
aws logs describe-log-groups --region ap-northeast-1 \
  --query 'logGroups[?contains(logGroupName, `motion`) || contains(logGroupName, `thf`)].logGroupName'
```

### DynamoDB
```bash
aws dynamodb list-tables --region ap-northeast-1
aws dynamodb describe-table --table-name motion-scan-results --region ap-northeast-1
```

### SNS
```bash
aws sns list-topics --region ap-northeast-1
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:ap-northeast-1:417081976353:thf-alerts-dev \
  --region ap-northeast-1
aws sns get-subscription-attributes \
  --subscription-arn "arn:aws:sns:...:382fb728-edf6-417c-9fd5-4d9f5658b379" \
  --region ap-northeast-1
```

---

**確認者**: Claude Code
**確認完了日時**: 2025-11-06
**次のアクション**: ユーザーへの報告 → 3種の集計スクリプト実装へ進む

---

# 📊 実データ確認結果（2025-11-06追記）

## 実処理データの検証

**テスト動画**: `s3://thf-motion-scan-videos-417081976353/videos/single_leg_squat/1101_01_20251101_173755.mp4`
**処理日時**: 2025-11-01 08:38:08 UTC
**処理完了**: 2025-11-01 08:43:21 UTC（約5分）
**動画サイズ**: 134MB（59.7fps、39.8秒、2381フレーム）

### 実際のデータフロー確認

✅ **S3 → SQS → Lambda → S3 Results**（正常動作）
❌ **Lambda → DynamoDB**（実行されていない）

### 1. 構造化ログサンプル

**Log Group**: `/aws/lambda/thf-motion-scan-ProcessingFunction`（stdoutから出力）

```json
{
  "timestamp": "2025-11-01T08:38:08.205399Z",
  "level": "INFO",
  "message": "Processing target identified",
  "test_type": "single_leg_squat",
  "context": {
    "bucket": "thf-motion-scan-videos-417081976353",
    "key": "videos/single_leg_squat/1101_01_20251101_173755.mp4"
  }
}
```

```json
{
  "timestamp": "2025-11-01T08:43:21.165811Z",
  "level": "INFO",
  "message": "Results saved to S3",
  "test_type": "single_leg_squat",
  "context": {
    "result_key": "results/2025/11/01/1101_01_20251101_173755_20251101_084321.json",
    "bucket": "thf-motion-scan-results-417081976353"
  }
}
```

**重要な発見**:
- 構造化ログは `/thf/motion-scan/dev/logs/*` ではなく、Lambdaのstdout経由で `/aws/lambda/thf-motion-scan-ProcessingFunction` に出力されている
- `level`, `timestamp`, `message`, `test_type`, `context` フィールドが存在

### 2. S3処理結果サンプル

**S3 Key**: `s3://thf-motion-scan-results-417081976353/results/2025/11/01/1101_01_20251101_173755_20251101_084321.json`

```json
{
  "video_path": "/tmp/tmp5bixl16n.mp4",
  "test_type": "single_leg_squat",
  "athlete_id": "Unknown-251101",
  "session_id": "20251101-0838-X",
  "score": 54.0,
  "max_score": 80,
  "evaluation": {
    "version": "v2.1",
    "test_id": "T01_single_leg_squat",
    "timestamp": "2025-11-01T08:43:21.055511Z",
    "A_execution_score": 20.0,
    "A_breakdown": {
      "knee_flexion_angle": 10.0,
      "completion_reps": 10.0
    },
    "B_principles": {
      "eccentric": {
        "B1_core_stability": 1.0,
        "B1_details": {
          "reason": "体幹が左右に回旋しています（95.6度） / 肩の高さを揃えましょう（左右差25.9%）",
          "coach_details": {
            "trunk_rotation": 95.6,
            "shoulder_diff": 0.259,
            "deductions": [
              "体幹回旋が大きい（95.6度 > 20度閾値）: -2.5点",
              "肩の高低差が大きい（0.259 > 0.1閾値）: -1.5点"
            ],
            "threshold_rotation": 10.0,
            "threshold_shoulder": 0.05
          },
          "severity": "high"
        },
        "B2_support_foundation": 5.0,
        "B3_3joint_coordination": 5.0,
        "B4_pelvis_horizontal": 6.0
      },
      "concentric": {
        "B1_core_stability": 1.0,
        "B2_support_foundation": 5.0,
        "B3_3joint_coordination": 5.0,
        "B4_pelvis_horizontal": 6.0
      }
    },
    "B_total": 34.0,
    "total_score": 54.0,
    "total_percentage": 67,
    "max_possible": 80
  },
  "video_info": {
    "fps": 59.742645777603684,
    "frame_count": 2381,
    "duration": 39.85427777777778,
    "detected_frames": 2237
  },
  "health_check": {
    "total_frames": 2237,
    "detected_frames": 2237,
    "detection_rate": 1.0,
    "low_visibility_frames": 74,
    "low_visibility_landmarks_count": 9334,
    "is_quality_ok": true
  },
  "quality_metrics": {
    "landmark_visibility_avg": 0.8996580176454121,
    "frame_completeness": 0.9395212095758085,
    "quality_score": 92,
    "warnings": [],
    "recommend_retake": false
  },
  "processed_at": "2025-11-01T08:43:21.055663"
}
```

**重要なメトリクス**:
- `detection_rate`: 1.0（100%）
- `landmark_visibility_avg`: 0.8997（約90%）
- `quality_score`: 92（0-100スケール）
- `frame_completeness`: 0.9395（94%）

### 3. DynamoDB状態

**確認結果**: ❌ **テーブルは空（レコード数: 0）**

**原因推定**:
- 処理は成功しているが、`save_to_dynamodb()` 関数が呼ばれていない可能性
- または、Lambda実行時にDynamoDB書き込み権限が不足している可能性

**影響**:
- S3には結果が保存されているため、データロストは発生していない
- ただし、DynamoDBを経由したクエリ（athlete_id、session_id検索等）ができない

### 4. BCR/κ/override_rate メトリクスの所在確定

**✅ 所在判明**: CloudWatch Metricsに直接送信

#### CloudWatch Metrics定義

| プロジェクトメトリクス名 | CloudWatch Metric名 | ネームスペース | 用途 |
|----------------------|-------------------|-------------|------|
| BCR（Balanced Correct Rate） | `BalancedCorrectRate` | `THF/MotionScan` | 評価精度 |
| κ（Cohen's Kappa） | `CohenKappa` | `THF/MotionScan` | 評価者間一致度 |
| Override Rate | `OverrideRatio` | `THF/MotionScan` | 人間による上書き率 |

#### 監視システム

**監視Lambda**: `lambda/monitoring/metrics_monitor.py`
- **実行頻度**: EventBridge経由で1分ごと
- **データソース**: CloudWatch GetMetricStatistics API
- **閾値評価**: 2-tier（WARN/FAIL）
- **通知**: SNS経由（debounce: WARN 15分、FAIL 5分）

#### 閾値設定

| メトリクス | WARN閾値 | FAIL閾値 | 比較方向 |
|-----------|---------|---------|---------|
| BCR | <0.5 | <0.3 | 低いほど悪い |
| Kappa | <0.3 | <0.2 | 低いほど悪い |
| Override Ratio | >30% | >50% | 高いほど悪い |

#### メトリクス送信元

**送信コード**: `lambda/common/structured_logging.py` - `StructuredLogger.metric()`
```python
def metric(self, name: str, value: float, *, unit: str = "Count", dimensions: Optional[Dict[str, str]] = None) -> None:
    # CloudWatch PutMetricData API経由で送信
    self._metrics().put_metric_data(
        Namespace=self._namespace,  # "THF/MotionScan"
        MetricData=[data]
    )
```

**Dimensions**:
- `Environment`: dev/stg/prod
- `TestCode`: single_leg_squat等
- `FunctionName`: Lambda関数名

#### 確認コマンド

```bash
# BCRメトリクス取得（直近1時間）
aws cloudwatch get-metric-statistics \
  --namespace THF/MotionScan \
  --metric-name BalancedCorrectRate \
  --dimensions Name=Environment,Value=dev \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Minimum,Maximum \
  --region ap-northeast-1
```

### 5. 更新された次工程パラメータ

#### 確定したデータソース

**CloudWatch Logs**:
```python
LOG_GROUPS = {
    "processing": "/aws/lambda/thf-motion-scan-ProcessingFunction",  # 実際の構造化ログ
    # 以下は設定されているが現時点では未使用
    "warn": "/thf/motion-scan/dev/logs/warn",
    "error": "/thf/motion-scan/dev/logs/error",
    "metrics": "/thf/motion-scan/dev/logs/metrics",
}
```

**S3 Results**:
```python
RESULTS_BUCKET = "thf-motion-scan-results-417081976353"
RESULTS_PREFIX = "results/YYYY/MM/DD/"
# 実データパス例:
# s3://thf-motion-scan-results-417081976353/results/2025/11/01/1101_01_20251101_173755_20251101_084321.json
```

**DynamoDB**:
```python
TABLE_NAME = "motion-scan-results"
# 注意: 現時点では空（DynamoDB保存が実行されていない）
# S3結果ファイルからデータを取得する必要がある
```

**CloudWatch Metrics**:
```python
METRICS_NAMESPACE = "THF/MotionScan"
METRICS_CONFIG = {
    "BCR": "BalancedCorrectRate",
    "Kappa": "CohenKappa",
    "OverrideRatio": "OverrideRatio",
}
DIMENSIONS = ["Environment", "TestCode", "FunctionName"]
```

### 6. 新たに判明した問題

1. **DynamoDB保存の未実行**
   - **症状**: 処理成功しているがDynamoDBが空
   - **影響**: athlete_id/session_id検索ができない
   - **推奨対応**: handler.py の save_to_dynamodb() 呼び出しを確認

2. **構造化ログの実際の出力先**
   - **症状**: `/thf/motion-scan/dev/logs/*` ではなくLambda標準ログに出力
   - **影響**: 当初想定していたLog Groupsが使用されていない
   - **推奨対応**: Lambda handler内でStructuredLoggerの設定を確認

3. **BCR/κ/override_rateの実データ不足**
   - **症状**: CloudWatch Metricsにデータが存在するか未確認
   - **影響**: P95計算に必要なメトリクスデータが取得できない可能性
   - **推奨対応**: CloudWatch GetMetricStatistics APIで実データ確認

### 7. 推奨される優先アクション

#### 優先度1: DynamoDB保存の修正
- [ ] `src/handler.py` の `save_to_dynamodb()` 呼び出し箇所を確認
- [ ] Lambda実行ロールのDynamoDB書き込み権限を確認
- [ ] 修正後、テスト動画で再検証

#### 優先度2: CloudWatch Metricsの実データ確認
- [ ] BCR/Kappa/OverrideRatio メトリクスが実際に送信されているか確認
- [ ] 直近7日のメトリクスデータを取得
- [ ] P95計算に必要なデータポイント数を確認

#### 優先度3: 構造化ログの出力先統一
- [ ] Lambda handler で構造化ログ出力先を `/thf/motion-scan/dev/logs/*` に統一
- [ ] または、集計スクリプトを Lambda標準ログから取得するように修正

---

**更新日時**: 2025-11-06
**検証完了**: 実データ確認完了、BCR/κ/override_rate所在確定
**次のアクション**: 上記3つの優先アクション実施 → 3種の集計スクリプト実装
