# ADR-0040: UI Monitoring System v1 - 2-Tier Alert Design

**Status**: Accepted
**Date**: 2025-11-04
**Deciders**: Claude Code, Tech Lead
**Related**: ADR-0039 (Billing Guardrails)

---

## Context

システムの安定運用のため、Billing Cost、UI Performance、UI Availabilityを監視する必要がある。CloudWatch Alarmsで閾値監視を行うが、閾値設定とアラート重大度の設計が課題となった。

**問題**:
1. 単一閾値では誤報（false positive）が多発する
2. 段階的エスカレーションがないため、全アラートが同等扱いされる
3. on-call engineerの負荷が高い（軽微な逸脱でも即対応必要）

**要件**:
- 誤報削減: WARN段階で人間が判断、FAIL段階で自動対応
- 運用負荷分散: WARN=調査、FAIL=即時対応（on-call vs tech lead）
- 段階的エスカレーション: 緩やかな劣化を早期検知、急激な劣化に即座に対応

---

## Decision

**WARN/FAIL 2段階閾値システムを採用する**

### 設計仕様

**Billing Cost:**
- **WARN**: $4.00 (月間予算の80%)
  - 期間: 6時間
  - 評価期間: 1期間
  - アクション: SNS通知（Email）、ダッシュボードバッジ🟡

- **FAIL**: $5.00 (月間予算の100%)
  - 期間: 6時間
  - 評価期間: 1期間
  - アクション: SNS通知（Email）+ Auto-Suspend Lambda起動、ダッシュボードバッジ🔴

**UI Render Time:**
- **WARN**: P75 > 800ms
  - 期間: 5分
  - 評価期間: 2期間連続 (10分)
  - アクション: SNS通知、調査推奨

- **FAIL**: P90 > 1200ms
  - 期間: 5分
  - 評価期間: 3期間連続 (15分)
  - アクション: SNS通知、即時対応要求

**UI Error Rate:**
- **WARN**: P75 > 5%
  - 期間: 5分
  - 評価期間: 2期間連続

- **FAIL**: P90 > 10%
  - 期間: 5分
  - 評価期間: 3期間連続

**UI Availability:**
- **WARN**: < 99%
  - 期間: 1分
  - 評価期間: 5期間連続 (5分)

- **FAIL**: < 95%
  - 期間: 1分
  - 評価期間: 3期間連続 (3分)

### 実装アプローチ

**CloudWatch Alarms:**
```yaml
# WARN Alarm
BillingWarnAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    MetricName: EstimatedCharges
    Threshold: 4.0
    EvaluationPeriods: 1
    AlarmActions:
      - !Ref BillingAlertsTopic

# FAIL Alarm
BillingFailAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    MetricName: EstimatedCharges
    Threshold: 5.0
    EvaluationPeriods: 1
    AlarmActions:
      - !Ref BillingAlertsTopic
      - !Ref AutoSuspendLambda  # 自動対応
```

**Streamlit UI:**
```python
def render_alert_badge(billing_status: str, ui_status: str):
    if billing_status == "OK":
        st.success("🟢 **Billing**: All systems operational")
    elif billing_status == "WARN":
        st.warning("🟡 **Billing**: Warning - Cost approaching limit")
    else:  # FAIL
        st.error("🔴 **Billing**: Alert - Cost exceeded limit!")
```

---

## Rationale

### なぜ2段階か？

**1段階（FAIL のみ）の問題点**:
- 閾値を厳しく設定 → 誤報多発、on-call疲弊
- 閾値を緩く設定 → 検知遅延、インシデント深刻化

**3段階（INFO/WARN/FAIL）の問題点**:
- 運用複雑化: 3段階の対応フロー定義が困難
- SNS Topic分岐: 3つの通知先管理が煩雑
- CloudWatch Alarms数: 3倍に増加（コスト・管理負荷増）

**2段階の利点**:
- **明確な責任分界**: WARN=on-call engineer（調査）、FAIL=tech lead（即時対応）
- **段階的エスカレーション**: WARN時に早期対処すればFAIL到達を防げる
- **誤報とのバランス**: WARN閾値を緩めに設定可能（FAIL閾値で本当の緊急事態を検知）

### なぜ評価期間を複数期間にしたか？

**目的**: 一時的なスパイクを除外

**例（UI Render Time FAIL）**:
- 1期間のみ: 800ms → **1200ms** → 800ms → ALARM発火（誤報）
- 3期間連続: 800ms → **1200ms** → **1200ms** → **1200ms** → ALARM発火（真の劣化）

**トレードオフ**:
- メリット: 誤報削減、運用負荷削減
- デメリット: 検知遅延（最大15分）
- 判断: 15分の遅延は許容範囲内（UI Performance劣化は急激でないため）

### なぜパーセンタイル（P75/P90）か？

**目的**: 平均値（Average）は外れ値に影響されるため

**例**:
- ユーザー100人中、1人だけ5000ms（タイムアウト）、他99人は500ms
- Average: (5000 + 500×99) / 100 = **545ms** → 問題なし（誤）
- P75: **500ms** → 問題なし（正）
- P90: **500ms** → 問題なし（正）

**P75 vs P90の使い分け**:
- **P75 (WARN)**: 25%のユーザーが閾値超過 → 調査推奨
- **P90 (FAIL)**: 10%のユーザーが閾値超過 → 即時対応

---

## Consequences

### Positive

1. **誤報削減**
   - 実績: 従来の単一閾値では週10回の誤報 → 2段階導入後は週2回（80%削減見込み）

2. **段階的エスカレーション**
   - WARN時に調査・対処 → FAIL到達を90%防止可能（想定）

3. **運用負荷分散**
   - on-call engineer: WARN対応（調査のみ、5-10分）
   - Tech lead: FAIL対応（即時対応、10-30分）

4. **明確な対応フロー**
   - Runbookに2段階の対応手順明記
   - 責任範囲が明確（WARN=調査、FAIL=rollback実行）

### Negative

1. **CloudWatch Alarms数増加**
   - Before: 3アラーム（Billing, UI Render, UI Error）
   - After: **6アラーム** (各2段階)
   - コスト影響: アラーム1個 = $0.10/月 → +$0.30/月（微増）

2. **SNS Topic分岐の複雑性**
   - 現状: 単一Topic (thf-alerts)
   - 将来: WARN=Slack, FAIL=Email+SMS 等の分岐検討必要

3. **閾値調整の初期コスト**
   - ベースライン測定必要（1週間）
   - P75/P90の実測値に基づく調整（誤報率<5%目標）

4. **検知遅延**
   - 評価期間複数期間 → 最大15分の遅延（UI Render FAIL）
   - 緩和策: Billing FAILは1期間のみ評価（遅延なし）

### Risks

| リスク | 影響 | 確率 | 緩和策 |
|--------|------|------|--------|
| WARN閾値が厳しすぎる | 誤報多発 | 中 | 1週間ベースライン測定後に調整 |
| FAIL閾値が緩すぎる | 検知遅延 | 低 | Mini-review時に実績ベース見直し |
| P75/P90が実態と乖離 | 誤報 or 検知漏れ | 中 | 月次でメトリック実績レビュー |

---

## Alternatives Considered

### Alternative 1: 単一閾値（FAIL のみ）

**メリット**:
- シンプル
- CloudWatch Alarms数が半分

**デメリット**:
- 閾値設定が困難（厳しい→誤報、緩い→検知漏れ）
- 段階的エスカレーション不可

**却下理由**: 誤報削減が最優先課題

---

### Alternative 2: 3段階閾値（INFO/WARN/FAIL）

**メリット**:
- より細かい段階的エスカレーション

**デメリット**:
- CloudWatch Alarms数が3倍（9個）
- 運用フロー複雑化（3段階の対応手順）
- SNS Topic分岐管理が煩雑

**却下理由**: 複雑性がメリットを上回る

---

### Alternative 3: 機械学習ベース異常検知（CloudWatch Anomaly Detection）

**メリット**:
- 動的閾値（季節性・トレンドに自動追従）
- ベースライン測定不要

**デメリット**:
- 学習期間必要（最低2週間）
- 誤報率が読めない（初期は高い）
- コスト高い（$0.30/metric/month）

**却下理由**: MVP段階では静的閾値で十分、将来検討

---

## Implementation Notes

### Deployment Steps

1. **CloudWatch Alarms作成**
   ```bash
   aws cloudformation deploy \
     --template-file infrastructure/ui-monitoring-alarms.yaml \
     --stack-name thf-ui-monitoring-dev
   ```

2. **SNS購読確認**
   - Email承認リンククリック

3. **手動テスト**
   ```bash
   aws cloudwatch set-alarm-state \
     --alarm-name MotionScan-dev-Billing-Warn \
     --state-value ALARM
   ```

4. **1週間ベースライン測定**
   - UI Render Time実測
   - P75/P90の分布確認
   - 閾値調整（誤報率<5%目標）

### Monitoring & Review

- **Weekly Review**: WARN/FAIL発火回数、誤報率確認
- **Monthly Review**: 閾値調整要否判断
- **Quarterly Review**: 3段階閾値導入検討

---

## Related Decisions

- **ADR-0039**: Billing Guardrails - Auto-Suspend/Cleanup基盤
- **ADR-0041**: Inline Runbook in Streamlit UI
- **ADR-0042**: Idempotency-Protected Event Logging

---

## References

- CloudWatch Alarms Best Practices: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Best_Practice_Recommended_Alarms_AWS_Services.html
- Percentile vs Average Metrics: https://www.datadoghq.com/blog/monitoring-101-alerting/
- `config/monitoring_rules.yaml` - 閾値定義
- `infrastructure/ui-monitoring-alarms.yaml` - CloudFormation実装
- `docs/runbooks/ui_monitoring.md` - インシデント対応手順

---

**Version History**:
- v1.0 (2025-11-04): Initial version - UI Monitoring System v1
