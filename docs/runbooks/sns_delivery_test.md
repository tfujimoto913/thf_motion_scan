# SNS Delivery Verification Runbook

**Purpose**: Verify SNS topic delivery for monitoring alerts before production use
**Scope**: `thf-alerts-<env>` topic configuration, subscription confirmation, message delivery test
**Expected Duration**: 10-15 minutes
**Last Updated**: 2025-11-05
**Decision Log**: ADR-040 (UI Monitoring 2-Tier Alert System)
**Contract**: `contracts/sns_notification.yaml` (v1.0.0)

---

## 📋 Prerequisites

Before running delivery tests:

1. **AWS Credentials**: Configured for target environment
   ```bash
   aws sts get-caller-identity
   # Expected: Account ID and user/role information
   ```

2. **SNS Topic Exists**: `thf-alerts-<env>` deployed via CloudFormation
   ```bash
   aws sns list-topics --query 'Topics[?contains(TopicArn, `thf-alerts`)]'
   ```

3. **Subscription Confirmed**: Email/endpoint subscription is active (not pending)
   ```bash
   aws sns list-subscriptions --query 'Subscriptions[?contains(TopicArn, `thf-alerts-dev`)]'
   # Check Status: "Confirmed" (not "PendingConfirmation")
   ```

4. **Python Environment**: boto3 installed
   ```bash
   pip install boto3 pyyaml
   ```

---

## 🧪 Test Procedure

### Test 1: Simple Delivery (OK State)

**Purpose**: Verify basic SNS delivery without triggering alert workflows

```bash
# Auto-detect topic ARN from AWS account
python tools/test_sns_delivery.py --env dev --test-type simple

# Or provide explicit ARN
python tools/test_sns_delivery.py \
  --env dev \
  --test-type simple \
  --topic-arn arn:aws:sns:us-east-1:123456789012:thf-alerts-dev
```

**Expected Output**:
```
✅ Message sent successfully!
   MessageId: 12345678-1234-1234-1234-123456789012
   Topic ARN: arn:aws:sns:us-east-1:123456789012:thf-alerts-dev
   Test Type: simple

📧 Check your email (or configured endpoint) for delivery confirmation.
   It may take 1-2 minutes for the message to arrive.
```

**Email Subject**: `[TEST] Delivery Verification - dev`

**Email Body** (JSON payload):
```json
{
  "env": "dev",
  "overall": "OK",
  "source": "metrics_monitor",
  "reason": "Test notification - Delivery verification for dev environment",
  "url": "https://github.com/anthropics/thf-motion-scan",
  "timestamp": "2025-11-05T12:34:56.789Z",
  "severity": "INFO",
  "metadata": {
    "test": true,
    "purpose": "Delivery verification",
    "contract_version": "1.0.0"
  }
}
```

---

### Test 2: WARN Alert Simulation

**Purpose**: Verify WARN-level alert delivery (BCR metric example)

```bash
python tools/test_sns_delivery.py --env dev --test-type warn
```

**Expected Email Subject**: `[TEST-WARN] BCR Alert - dev`

**Payload Validation**:
- `overall`: "WARN"
- `source`: "metrics_monitor"
- `severity`: "WARN"
- `metadata.metric_name`: "BCR"
- `metadata.current_value`: 0.48
- `metadata.warn_threshold`: 0.5

---

### Test 3: FAIL Alert Simulation

**Purpose**: Verify FAIL-level alert delivery (Billing threshold example)

```bash
python tools/test_sns_delivery.py --env dev --test-type fail
```

**Expected Email Subject**: `[TEST-FAIL] Billing Alert - dev`

**Payload Validation**:
- `overall`: "FAIL"
- `source`: "billing_monitor"
- `severity`: "CRITICAL"
- `metadata.current_cost_usd`: 5.5
- `metadata.fail_threshold_usd`: 5.0

---

## ✅ Verification Checklist

After each test, confirm:

- [ ] **Email Delivered**: Message arrives within 2 minutes
- [ ] **Subject Line**: Matches expected format (see above)
- [ ] **JSON Structure**: Valid JSON with all required keys
- [ ] **Contract Compliance**: Required keys present (`env`, `overall`, `source`, `reason`, `url`)
- [ ] **SNS Attributes**: Check CloudWatch Logs for message attributes (optional)
- [ ] **No Errors**: No AWS SDK errors in terminal output

---

## 🔍 Troubleshooting

### Issue 1: Topic Not Found

**Error**:
```
❌ SNS delivery error: NotFound - Topic does not exist
```

**Solution**:
```bash
# List all SNS topics
aws sns list-topics

# Check CloudFormation stack outputs
aws cloudformation describe-stacks \
  --stack-name thf-motion-scan-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`AlertsTopicArn`].OutputValue'
```

---

### Issue 2: Subscription Not Confirmed

**Error**:
```
❌ Email not delivered after 5 minutes
```

**Solution**:
```bash
# Check subscription status
aws sns list-subscriptions --query 'Subscriptions[?contains(TopicArn, `thf-alerts-dev`)]'

# If Status = "PendingConfirmation", check email for confirmation link
# Resend confirmation (if expired)
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:123456789012:thf-alerts-dev \
  --protocol email \
  --notification-endpoint your-email@example.com
```

---

### Issue 3: IAM Permission Denied

**Error**:
```
❌ SNS delivery error: AccessDenied - User is not authorized to perform sns:Publish
```

**Solution**:
```bash
# Check current IAM permissions
aws iam get-user-policy --user-name your-username --policy-name your-policy

# Required IAM policy:
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sns:Publish",
      "Resource": "arn:aws:sns:us-east-1:*:thf-alerts-*"
    }
  ]
}
```

---

### Issue 4: Message Validation Failed

**Error**:
```
❌ Message validation error: Invalid env: test. Allowed: ['dev', 'stg', 'prod']
```

**Solution**:
- Use `--env dev|stg|prod` (not arbitrary values)
- Modify `src/monitoring/sns_notifier.py` to extend `ALLOWED_ENV` if needed

---

## 📊 Delivery Metrics (Optional)

Check SNS delivery metrics in CloudWatch:

```bash
# Get delivery success count (last 15 minutes)
aws cloudwatch get-metric-statistics \
  --namespace AWS/SNS \
  --metric-name NumberOfNotificationsDelivered \
  --dimensions Name=TopicName,Value=thf-alerts-dev \
  --statistics Sum \
  --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --region us-east-1

# Check for delivery failures
aws cloudwatch get-metric-statistics \
  --namespace AWS/SNS \
  --metric-name NumberOfNotificationsFailed \
  --dimensions Name=TopicName,Value=thf-alerts-dev \
  --statistics Sum \
  --start-time $(date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --region us-east-1
```

---

## 🔗 Integration with Release Runbook

After successful delivery verification, update `docs/runbooks/rules_version_release.md`:

1. **Pre-Release Checklist**: Add SNS delivery verification step
   ```markdown
   - [ ] SNS delivery verified (see `docs/runbooks/sns_delivery_test.md`)
   - [ ] All 3 test types (simple, warn, fail) confirmed
   ```

2. **Monitoring Section**: Reference SNS notification procedures
   ```markdown
   ### Alert Notifications
   - WARN alerts: 15-minute debounce, sent to `thf-alerts-prod`
   - FAIL alerts: 5-minute debounce, requires immediate action
   - Delivery verification: `docs/runbooks/sns_delivery_test.md`
   ```

3. **Rollback Triggers**: Include SNS notification failures
   ```markdown
   Rollback if:
   - WARN alert persists > 30 minutes
   - FAIL alert triggered
   - **SNS delivery fails (check `NumberOfNotificationsFailed` metric)**
   ```

---

## 🚀 Next Steps

After delivery verification:

1. **Integrate with Monitoring Lambda**: Update `lambda/monitoring/metrics_monitor.py` to use `sns_notifier.send_notification()`
2. **Configure Filter Policies** (optional): Team-specific subscriptions based on `Severity` or `Source` attributes
3. **Set Up Dead-Letter Queue** (optional): Capture undelivered messages for investigation
4. **Production Deployment**: Repeat tests for `stg` and `prod` environments

---

## 📚 Related Documentation

- [SNS Message Contract](../../contracts/sns_notification.yaml) - Message schema specification (v1.0.0)
- [SNS Notifier Module](../../src/monitoring/sns_notifier.py) - Python implementation
- [Billing Emergency Stop](./billing_emergency_stop.md) - References SNS notifications
- [Rules Version Release](./rules_version_release.md) - Main release procedures

---

## 🔧 Reference Commands

```bash
# List all SNS topics
aws sns list-topics

# Describe specific topic
aws sns get-topic-attributes --topic-arn arn:aws:sns:us-east-1:123456789012:thf-alerts-dev

# List subscriptions for topic
aws sns list-subscriptions-by-topic --topic-arn arn:aws:sns:us-east-1:123456789012:thf-alerts-dev

# Test message with custom payload (advanced)
aws sns publish \
  --topic-arn arn:aws:sns:us-east-1:123456789012:thf-alerts-dev \
  --subject "[TEST] Custom Alert" \
  --message '{"env":"dev","overall":"WARN","source":"metrics_monitor","reason":"Custom test","url":"https://example.com"}'
```

---

**Maintenance Note**: Update this runbook when:
- Contract version is incremented (`contracts/sns_notification.yaml`)
- New `source` types are added (`ALLOWED_SOURCE` in `sns_notifier.py`)
- Subscription protocols change (e.g., add Slack/Teams integration)
