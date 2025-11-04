# Rules Version Release Runbook

**Purpose**: Step-by-step procedure for releasing a new rules version (e.g., v2.1 → v2.2) with continuous monitoring and rollback decision support.

**Decision Log**: ADR-040 (UI monitoring 2-tier alert design)

**Last Updated**: 2025-11-04

---

## 📋 Overview

This runbook covers:
- Threshold updates (thresholds.json)
- Deployment to AWS (SAM)
- Continuous monitoring (15min WARN / 5min FAIL debounce)
- Rollback decision criteria
- Emergency response procedures

**CRITICAL**: Do NOT skip monitoring steps. BCR/kappa/override degradation must be detected within 15 minutes.

---

## 🔧 Prerequisites

### Required Tools
- AWS CLI configured with appropriate credentials
- SAM CLI (Serverless Application Model)
- Git access to this repository
- Access to CloudWatch Console
- SNS subscription to `thf-alerts-<env>` topic

### Pre-Release Checklist
- [ ] New thresholds validated in dev environment
- [ ] `thresholds.json` updated with new rules_version
- [ ] JSON schema validation passed (`sam validate`)
- [ ] Unit tests passed (`pytest tests/`)
- [ ] Changelog updated in `docs/adr/`

---

## 🚀 Release Procedure

### Step 1: Update Thresholds

1. Edit `config/thresholds.json`:
   ```json
   {
     "version": "2.2",
     "updated_at": "2025-11-04T12:00:00Z",
     "thresholds": {
       "single_leg_squat": { ... }
     }
   }
   ```

2. Validate schema:
   ```bash
   sam validate
   ```

3. Commit changes:
   ```bash
   git add config/thresholds.json
   git commit -m "feat(thresholds): update to v2.2 - <reason>"
   ```

---

### Step 2: Deploy to Dev Environment

1. Build SAM application:
   ```bash
   sam build
   ```

2. Deploy to dev:
   ```bash
   sam deploy --parameter-overrides Environment=dev
   ```

3. Verify stack update:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name thf-motion-scan-dev \
     --query "Stacks[0].StackStatus"
   ```

   Expected: `UPDATE_COMPLETE`

---

### Step 3: Enable Metrics Monitoring

1. Confirm MetricsMonitorFunction is enabled:
   ```bash
   aws lambda get-function --function-name thf-motion-scan-dev-MetricsMonitor
   ```

2. Check EventBridge rule status:
   ```bash
   aws events describe-rule --name metrics-monitor-1min
   ```

   Expected: `State: ENABLED`

3. Verify DynamoDB table exists:
   ```bash
   aws dynamodb describe-table --table-name metrics-monitoring-state-dev
   ```

---

### Step 4: Monitor for 30 Minutes (Critical)

**CRITICAL**: This is the most important step. Do NOT proceed to production without completing this monitoring phase.

#### 4.1 CloudWatch Dashboard

1. Open CloudWatch Dashboard:
   ```
   https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=MotionScan-Ops-dev
   ```

2. Monitor these metrics:
   - BCR (Balanced Correct Rate)
   - Kappa (Cohen's Kappa)
   - Override Ratio

#### 4.2 Check Monitoring State

Every 5 minutes, check the metrics monitoring state:

```bash
aws dynamodb scan \
  --table-name metrics-monitoring-state-dev \
  --projection-expression "metric_name,current_state,warn_count,fail_count,last_check_ts"
```

Expected output:
```json
{
  "Items": [
    {
      "metric_name": "BCR",
      "current_state": "OK",
      "warn_count": 0,
      "fail_count": 0,
      "last_check_ts": "2025-11-04T12:05:00Z"
    }
  ]
}
```

#### 4.3 Alarm Status

Check CloudWatch Alarms status:

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix "Metrics-" \
  --state-value ALARM
```

Expected: **No alarms in ALARM state**

#### 4.4 SNS Notifications

Monitor your email for SNS notifications from `thf-alerts-dev`.

**If you receive any of these notifications, proceed to Step 5 (Rollback Decision).**

---

### Step 5: Rollback Decision Criteria

**WARN State (15 consecutive minutes)**:
- Action: Investigate degradation root cause
- Criteria: BCR < 0.5, Kappa < 0.3, or Override > 30%
- Decision: Can continue monitoring, but prepare rollback

**FAIL State (5 consecutive minutes)**:
- Action: **IMMEDIATE ROLLBACK REQUIRED**
- Criteria: BCR < 0.3, Kappa < 0.2, or Override > 50%
- Decision: Unacceptable quality degradation

---

### Step 6: Rollback Procedure (If Needed)

#### 6.1 Identify Previous Rules Version

```bash
git log --oneline config/thresholds.json | head -5
```

#### 6.2 Revert Thresholds

```bash
git revert HEAD
git push
```

#### 6.3 Redeploy Previous Version

```bash
sam build && sam deploy --parameter-overrides Environment=dev
```

#### 6.4 Verify Rollback

Wait 15 minutes and confirm metrics return to OK state.

---

### Step 7: Production Deployment (If Dev OK)

**Only proceed if all of the following are true:**
- [ ] Dev monitoring passed for 30 minutes
- [ ] No WARN/FAIL alarms triggered
- [ ] BCR/Kappa/Override remain stable

1. Deploy to staging:
   ```bash
   sam deploy --parameter-overrides Environment=staging
   ```

2. Monitor staging for 30 minutes (repeat Step 4)

3. Deploy to production:
   ```bash
   sam deploy --parameter-overrides Environment=prod
   ```

4. Monitor production for 1 hour (repeat Step 4)

---

## 🚨 Emergency Response

### Scenario 1: FAIL Alarm Triggered in Production

**Immediate Actions:**
1. Notify team via Slack/PagerDuty
2. Execute rollback (Step 6)
3. Investigate root cause offline

### Scenario 2: Lambda Monitoring Function Failure

**Symptoms:**
- No recent updates in DynamoDB state table
- CloudWatch Alarms not triggering despite visible metric degradation

**Actions:**
1. Check Lambda function logs:
   ```bash
   aws logs tail /aws/lambda/thf-motion-scan-prod-MetricsMonitor --follow
   ```

2. Manually check CloudWatch metrics:
   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace THF/MotionScan \
     --metric-name BalancedCorrectRate \
     --dimensions Name=Environment,Value=prod Name=RulesVersion,Value=v2.2 \
     --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S) \
     --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
     --period 60 \
     --statistics Average
   ```

3. If metrics show degradation but Lambda is not functioning:
   - Execute manual rollback immediately
   - File incident report

### Scenario 3: SNS Notifications Not Received

**Symptoms:**
- Alarms in ALARM state, but no email received

**Actions:**
1. Verify SNS subscription:
   ```bash
   aws sns list-subscriptions-by-topic --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:thf-alerts-prod
   ```

2. Re-subscribe if needed:
   ```bash
   aws sns subscribe \
     --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:thf-alerts-prod \
     --protocol email \
     --notification-endpoint your-email@example.com
   ```

3. Confirm subscription via email

---

## 📊 Monitoring Dashboard

### CloudWatch Metrics to Monitor

| Metric Name | Namespace | Dimensions | WARN Threshold | FAIL Threshold |
|-------------|-----------|------------|----------------|----------------|
| BalancedCorrectRate | THF/MotionScan | Environment, RulesVersion | < 0.5 | < 0.3 |
| CohenKappa | THF/MotionScan | Environment, RulesVersion | < 0.3 | < 0.2 |
| OverrideRatio | THF/MotionScan | Environment, RulesVersion | > 30% | > 50% |

### Monitoring State (DynamoDB)

| Attribute | Description |
|-----------|-------------|
| `metric_name` | BCR / Kappa / OverrideRatio |
| `current_state` | OK / WARN / FAIL |
| `warn_count` | Minutes in WARN state (0-15) |
| `fail_count` | Minutes in FAIL state (0-5) |
| `last_check_ts` | Last check timestamp (ISO 8601) |

---

## 🔍 Troubleshooting

### Q: Metrics are missing in CloudWatch

**A**: Check that EMF metrics are being emitted correctly:

```bash
aws logs filter-log-events \
  --log-group-name /thf/motion-scan/dev/logs/metrics \
  --filter-pattern "{ $.metric_name = \"BalancedCorrectRate\" }" \
  --max-items 5
```

### Q: DynamoDB state table is empty

**A**: Verify MetricsMonitorFunction has DynamoDB write permissions:

```bash
aws iam get-role-policy \
  --role-name thf-motion-scan-dev-MetricsMonitorFunctionRole \
  --policy-name MetricsMonitorFunctionRolePolicy
```

### Q: How do I manually trigger the monitoring Lambda?

**A**: Invoke the function directly:

```bash
aws lambda invoke \
  --function-name thf-motion-scan-dev-MetricsMonitor \
  --payload '{}' \
  /tmp/response.json

cat /tmp/response.json | jq .
```

---

## 📚 Related Documentation

- ADR-040: UI Monitoring 2-Tier Alert Design
- [Billing Fail Safe Runbook](./billing_fail_safe.md)
- [DLQ Redrive Verification Report](../../docs/adr/0026-phase-5-ops-guardrails-cloudwatch-dashboards-dlq-runbook-structured-logging.md)

---

## ✅ Post-Release Checklist

After successful production deployment:

- [ ] Update CHANGELOG.md with release notes
- [ ] Update ADR with any decisions made during release
- [ ] Document any incidents or rollbacks
- [ ] Schedule retrospective if issues occurred
- [ ] Update Notion with release summary
