# Metrics Monitor Lambda Integration Test

**Purpose**: End-to-end testing of contract-compliant SNS notifications from metrics_monitor Lambda
**Scope**: Lambda invocation, SNS delivery, CloudWatch Logs verification
**Expected Duration**: 15-20 minutes
**Last Updated**: 2025-11-05
**Decision Log**: ADR-040 (UI Monitoring 2-Tier Alert System)
**Contract**: `contracts/sns_notification.yaml` (v1.0.0)

---

## 📋 Prerequisites

1. **AWS Credentials**: Configured for target environment
   ```bash
   aws sts get-caller-identity
   # Expected: Account ID and user/role information
   ```

2. **Lambda Function Deployed**: `MetricsMonitorFunction` exists
   ```bash
   aws lambda list-functions --query 'Functions[?contains(FunctionName, `MetricsMonitor`)].FunctionName'
   ```

3. **SNS Topic Configured**: `thf-alerts-<env>` with active subscription
   ```bash
   aws sns list-topics --query 'Topics[?contains(TopicArn, `thf-alerts`)]'
   aws sns list-subscriptions --query 'Subscriptions[?contains(TopicArn, `thf-alerts-dev`)]'
   ```

4. **DynamoDB Table**: `metrics-monitoring-state-<env>` deployed
   ```bash
   aws dynamodb describe-table --table-name metrics-monitoring-state-dev
   ```

5. **CloudWatch Metrics**: BCR/Kappa/OverrideRatio metrics exist
   ```bash
   aws cloudwatch list-metrics --namespace THF/MotionScan
   ```

---

## 🧪 Test Procedure

### Test 1: Lambda Invocation (Dry Run)

**Purpose**: Verify Lambda executes without errors

```bash
# Option A: Using helper script
./tools/test_metrics_monitor_lambda.sh --env dev

# Option B: Direct invocation
aws lambda invoke \
  --function-name MetricsMonitorFunction-dev \
  --cli-binary-format raw-in-base64-out \
  --log-type Tail \
  /tmp/metrics_monitor_test.json

# View response
cat /tmp/metrics_monitor_test.json | jq '.'
```

**Expected Output**:
```json
{
  "statusCode": 200,
  "body": "{\"timestamp\": \"2025-11-05T12:00:00.000Z\", \"results\": [{...}]}"
}
```

**Verification**:
- [ ] `statusCode: 200`
- [ ] `results` array contains BCR, Kappa, OverrideRatio
- [ ] No errors in CloudWatch Logs

---

### Test 2: Simulate WARN State

**Purpose**: Trigger WARN notification (requires 15 consecutive minutes)

**Step 1: Inject Low Metric Value**

```bash
# Publish low BCR value to CloudWatch (simulates degradation)
aws cloudwatch put-metric-data \
  --namespace THF/MotionScan \
  --metric-name BalancedCorrectRate \
  --value 0.45 \
  --dimensions Environment=dev,RulesVersion=v2.1
```

**Step 2: Invoke Lambda 15 Times (1-minute intervals)**

```bash
# Manual method: invoke 15 times with 60-second delay
for i in {1..15}; do
  echo "Invocation $i/15..."
  aws lambda invoke \
    --function-name MetricsMonitorFunction-dev \
    --cli-binary-format raw-in-base64-out \
    /tmp/test_warn_$i.json

  # Check state
  cat /tmp/test_warn_$i.json | jq '.body | fromjson | .results[] | select(.metric_name=="BCR")'

  # Wait 60 seconds (except last iteration)
  if [ $i -lt 15 ]; then
    sleep 60
  fi
done
```

**Expected Behavior**:
- Invocations 1-14: `warn_count` increments (1, 2, ..., 14)
- Invocation 15: `warn_count: 15`, **SNS notification sent**

**Step 3: Verify SNS Notification**

```bash
# Check email/endpoint for notification
# Subject: "[WARN] BCR Alert - dev"

# Verify CloudWatch Logs for notification event
aws logs tail /aws/lambda/MetricsMonitorFunction-dev \
  --since 5m \
  --filter-pattern "metrics_monitor_notification"

# Expected log:
# {
#   "event": "metrics_monitor_notification",
#   "metric_name": "BCR",
#   "state": "WARN",
#   "severity": "WARN",
#   "message_id": "12345678-1234-1234-1234-123456789012"
# }
```

**Step 4: Verify SNS Message Structure**

Check email payload conforms to contract:
```json
{
  "env": "dev",
  "overall": "WARN",
  "source": "metrics_monitor",
  "reason": "BCR has been in WARN state for 15 consecutive minutes (current: 0.450)",
  "url": "https://console.aws.amazon.com/cloudwatch/",
  "timestamp": "2025-11-05T12:15:00.000Z",
  "severity": "WARN",
  "metadata": {
    "metric_name": "BCR",
    "current_value": 0.45,
    "warn_count": 15,
    "fail_count": 0,
    "warn_debounce_threshold": 15,
    "fail_debounce_threshold": 5,
    "state_entered_ts": "2025-11-05T12:00:00.000Z",
    "rules_version": "v2.1"
  }
}
```

---

### Test 3: Simulate FAIL State

**Purpose**: Trigger FAIL notification (requires 5 consecutive minutes)

**Step 1: Inject Very Low Metric Value**

```bash
# Publish very low BCR value (below FAIL threshold 0.3)
aws cloudwatch put-metric-data \
  --namespace THF/MotionScan \
  --metric-name BalancedCorrectRate \
  --value 0.25 \
  --dimensions Environment=dev,RulesVersion=v2.1
```

**Step 2: Invoke Lambda 5 Times**

```bash
for i in {1..5}; do
  echo "Invocation $i/5..."
  aws lambda invoke \
    --function-name MetricsMonitorFunction-dev \
    --cli-binary-format raw-in-base64-out \
    /tmp/test_fail_$i.json

  cat /tmp/test_fail_$i.json | jq '.body | fromjson | .results[] | select(.metric_name=="BCR")'

  if [ $i -lt 5 ]; then
    sleep 60
  fi
done
```

**Expected Behavior**:
- Invocations 1-4: `fail_count` increments (1, 2, 3, 4)
- Invocation 5: `fail_count: 5`, **SNS notification sent with CRITICAL severity**

**Verify**:
- [ ] Email subject: `[FAIL] BCR Alert - dev`
- [ ] `overall: "FAIL"`
- [ ] `severity: "CRITICAL"`
- [ ] CloudWatch Logs event: `"state": "FAIL"`

---

### Test 4: Recovery (OK State)

**Purpose**: Verify recovery notification

**Step 1: Inject Normal Metric Value**

```bash
# Publish normal BCR value (above WARN threshold 0.5)
aws cloudwatch put-metric-data \
  --namespace THF/MotionScan \
  --metric-name BalancedCorrectRate \
  --value 0.65 \
  --dimensions Environment=dev,RulesVersion=v2.1
```

**Step 2: Invoke Lambda Once**

```bash
aws lambda invoke \
  --function-name MetricsMonitorFunction-dev \
  --cli-binary-format raw-in-base64-out \
  /tmp/test_recovery.json

cat /tmp/test_recovery.json | jq '.body | fromjson | .results[] | select(.metric_name=="BCR")'
```

**Expected Behavior**:
- `current_state: "OK"`
- `warn_count: 0`, `fail_count: 0` (reset)
- **SNS notification sent** (if previous state was WARN/FAIL)

**Verify**:
- [ ] Email subject: `[OK] BCR Alert - dev`
- [ ] `overall: "OK"`
- [ ] `severity: "INFO"`
- [ ] `reason: "BCR recovered to normal (current: 0.650)"`

---

## ✅ Verification Checklist

After completing all tests, verify:

- [ ] **Lambda Execution**: No errors in CloudWatch Logs
- [ ] **SNS Delivery**: All 3 notifications received (WARN, FAIL, OK)
- [ ] **Contract Compliance**: All payloads contain required keys (env, overall, source, reason, url)
- [ ] **Message Attributes**: SNS messages include Environment, Severity, Source attributes
- [ ] **DynamoDB State**: State table updated correctly
- [ ] **EMF Metrics**: CloudWatch metrics emitted (MonitoringState, WarnCounter, FailCounter)

---

## 🔍 Troubleshooting

### Issue 1: Lambda Timeout

**Error**: Lambda times out after 3 seconds

**Solution**:
```bash
# Check Lambda configuration
aws lambda get-function-configuration --function-name MetricsMonitorFunction-dev

# Increase timeout if needed
aws lambda update-function-configuration \
  --function-name MetricsMonitorFunction-dev \
  --timeout 30
```

---

### Issue 2: SNS Notification Not Received

**Error**: No email/endpoint delivery

**Solution**:
```bash
# Check SNS subscription status
aws sns list-subscriptions --query 'Subscriptions[?contains(TopicArn, `thf-alerts-dev`)]'

# If Status = "PendingConfirmation", resend confirmation
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:thf-alerts-dev \
  --protocol email \
  --notification-endpoint your-email@example.com

# Check SNS delivery failures
aws cloudwatch get-metric-statistics \
  --namespace AWS/SNS \
  --metric-name NumberOfNotificationsFailed \
  --dimensions Name=TopicName,Value=thf-alerts-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 --statistics Sum \
  --region us-east-1
```

---

### Issue 3: Import Error (sns_notifier not found)

**Error**: `Warning: Could not import sns_notifier`

**Solution**:
```bash
# Verify Lambda deployment package includes src/monitoring/sns_notifier.py
aws lambda get-function --function-name MetricsMonitorFunction-dev \
  --query 'Code.Location' --output text | xargs curl -o /tmp/lambda.zip

unzip -l /tmp/lambda.zip | grep sns_notifier

# If missing, rebuild and redeploy
sam build
sam deploy --parameter-overrides Environment=dev
```

---

### Issue 4: Contract Validation Failed

**Error**: `MessageValidationError: Invalid env`

**Solution**:
```bash
# Check environment variables
aws lambda get-function-configuration \
  --function-name MetricsMonitorFunction-dev \
  --query 'Environment.Variables'

# Verify ENVIRONMENT is set correctly
# Expected: {"ENVIRONMENT": "dev", "RULES_VERSION": "v2.1", ...}
```

---

## 📊 Verification Metrics

Check these metrics after testing:

```bash
# SNS delivery success rate
aws cloudwatch get-metric-statistics \
  --namespace AWS/SNS \
  --metric-name NumberOfNotificationsDelivered \
  --dimensions Name=TopicName,Value=thf-alerts-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 --statistics Sum \
  --region us-east-1

# Lambda invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=MetricsMonitorFunction-dev \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 --statistics Sum \
  --region us-east-1

# Monitoring state metrics (EMF)
aws cloudwatch get-metric-statistics \
  --namespace THF/MotionScan/Monitoring \
  --metric-name MonitoringState \
  --dimensions Name=Environment,Value=dev Name=RulesVersion,Value=v2.1 Name=MetricName,Value=BCR \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 --statistics Maximum \
  --region us-east-1
```

---

## 🔄 Cleanup

After testing, reset state:

```bash
# Delete DynamoDB test records
aws dynamodb delete-item \
  --table-name metrics-monitoring-state-dev \
  --key '{"metric_name":{"S":"BCR"},"env_version":{"S":"dev#v2.1"}}'

aws dynamodb delete-item \
  --table-name metrics-monitoring-state-dev \
  --key '{"metric_name":{"S":"Kappa"},"env_version":{"S":"dev#v2.1"}}'

aws dynamodb delete-item \
  --table-name metrics-monitoring-state-dev \
  --key '{"metric_name":{"S":"OverrideRatio"},"env_version":{"S":"dev#v2.1"}}'

# Remove test CloudWatch metrics (optional)
# Note: Metrics expire automatically after 15 months
```

---

## 📚 Related Documentation

- [SNS Delivery Test Runbook](./sns_delivery_test.md) - SNS topic verification procedures
- [SNS Message Contract](../../contracts/sns_notification.yaml) - Contract specification (v1.0.0)
- [Metrics Monitor Lambda](../../lambda/monitoring/metrics_monitor.py) - Implementation
- [Unit Tests](../../tests/lambda/test_metrics_monitor_notification.py) - Local test suite

---

**Maintenance Note**: Update this runbook when:
- Contract version is incremented
- Debounce thresholds change (WARN: 15min, FAIL: 5min)
- New metrics added to METRICS_CONFIG
- Lambda deployment process changes
