# Billing Guardrail Deployment Guide

**Purpose**: Deploy billing monitoring, auto-suspend, and auto-cleanup infrastructure
**Prerequisites**: AWS CLI, SAM CLI, boto3, valid AWS credentials
**Deployment Time**: ~15 minutes
**Last Updated**: 2025-11-04

---

## 📋 Overview

The Billing Guardrail system consists of:

1. **CloudWatch Alarms**: Monitor EstimatedCharges metric
2. **SNS Notifications**: Email/Slack alerts on threshold breach
3. **Auto-Suspend Lambda**: Stop low-traffic resources
4. **Auto-Cleanup Lambda**: Delete unattached EBS volumes
5. **Billing Status UI**: Dashboard for monitoring and manual controls

---

## 🚀 Deployment Steps

### Step 1: Deploy CloudWatch Alarms + SNS

```bash
# Navigate to infrastructure directory
cd infrastructure

# Deploy CloudFormation stack
aws cloudformation deploy \
  --template-file cloudwatch-alarms.yaml \
  --stack-name thf-billing-guardrail-dev \
  --parameter-overrides \
    Environment=dev \
    WarnThresholdUSD=4.0 \
    FailThresholdUSD=5.0 \
    AlertEmail=your-email@example.com \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

# Verify stack creation
aws cloudformation describe-stacks \
  --stack-name thf-billing-guardrail-dev \
  --region us-east-1
```

**Important**: You'll receive a confirmation email from SNS. Click the link to confirm subscription.

---

### Step 2: Verify Billing Metrics Enabled

Billing metrics are **only available in us-east-1** and must be enabled:

```bash
# Check if billing metrics are enabled
aws cloudwatch list-metrics \
  --namespace AWS/Billing \
  --metric-name EstimatedCharges \
  --region us-east-1

# If empty, enable in AWS Console:
# 1. Go to Billing Dashboard → Billing Preferences
# 2. Enable "Receive Billing Alerts"
# 3. Wait 6-12 hours for first data points
```

---

### Step 3: Deploy Auto-Suspend Lambda

Auto-Suspend Lambda is already defined in `template.yaml`. Update environment variables:

```yaml
# In template.yaml
BillingAutoSuspend:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: !Sub 'thf-billing-auto-suspend-${Environment}'
    CodeUri: lambda/billing/
    Handler: auto_suspend.handler
    Environment:
      Variables:
        DRY_RUN: "true"  # Set to "false" after testing
        REQ_THRESHOLD: "1"
        LOOKBACK_H: "2"
        AUTOSUSPEND_TAG_KEY: "AutoSuspend"
        AUTOSUSPEND_TAG_VALUE: "true"
```

Deploy:

```bash
# Build and deploy
sam build
sam deploy --guided

# Test in DRY_RUN mode
aws lambda invoke \
  --function-name thf-billing-auto-suspend-dev \
  --payload '{}' \
  /tmp/response.json \
  --region us-east-1

# Check output
cat /tmp/response.json
```

**Expected Output** (dry-run):
```json
{
  "dry_run": true,
  "actions_taken": 2,
  "actions": [
    {"action": "suspend_lambda", "resource": "thf-old-function", "status": "dry_run"},
    {"action": "stop_ec2", "resource": "i-123456", "status": "dry_run"}
  ]
}
```

**Disable DRY_RUN** (after verification):
```bash
aws lambda update-function-configuration \
  --function-name thf-billing-auto-suspend-dev \
  --environment "Variables={DRY_RUN=false,REQ_THRESHOLD=1,LOOKBACK_H=2}" \
  --region us-east-1
```

---

### Step 4: Deploy Auto-Cleanup Lambda

Similarly, Auto-Cleanup is in `template.yaml`:

```yaml
BillingAutoCleanup:
  Type: AWS::Serverless::Function
  Properties:
    FunctionName: !Sub 'thf-billing-auto-cleanup-${Environment}'
    CodeUri: lambda/billing/
    Handler: auto_cleanup.handler
    Environment:
      Variables:
        DRY_RUN: "true"
        UNATTACHED_TTL_H: "48"
        AUTOCLEANUP_TAG_KEY: "AutoCleanup"
        AUTOCLEANUP_TAG_VALUE: "allow"
```

Deploy and test:

```bash
# Deploy (included in sam deploy above)

# Test in DRY_RUN mode
aws lambda invoke \
  --function-name thf-billing-auto-cleanup-dev \
  --payload '{}' \
  /tmp/cleanup_response.json \
  --region us-east-1

cat /tmp/cleanup_response.json
```

**Expected Output**:
```json
{
  "dry_run": true,
  "eligible_volumes": 3,
  "snapshots_created": 0,
  "volumes_deleted": 0,
  "details": [
    {"volume_id": "vol-abc123", "size": 8, "age_hours": 72, "action": "would_snapshot_and_delete"}
  ]
}
```

**Disable DRY_RUN** (after verification):
```bash
aws lambda update-function-configuration \
  --function-name thf-billing-auto-cleanup-dev \
  --environment "Variables={DRY_RUN=false,UNATTACHED_TTL_H=48}" \
  --region us-east-1
```

---

### Step 5: Schedule Lambda Executions

EventBridge rules for automatic execution:

```bash
# Auto-Suspend: Every hour
aws events put-rule \
  --name thf-auto-suspend-schedule-dev \
  --schedule-expression "rate(1 hour)" \
  --region us-east-1

aws events put-targets \
  --rule thf-auto-suspend-schedule-dev \
  --targets "Id=1,Arn=arn:aws:lambda:us-east-1:ACCOUNT_ID:function:thf-billing-auto-suspend-dev" \
  --region us-east-1

# Grant permission
aws lambda add-permission \
  --function-name thf-billing-auto-suspend-dev \
  --statement-id AllowEventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:ACCOUNT_ID:rule/thf-auto-suspend-schedule-dev \
  --region us-east-1

# Auto-Cleanup: Daily at 02:00 UTC
aws events put-rule \
  --name thf-auto-cleanup-schedule-dev \
  --schedule-expression "cron(0 2 * * ? *)" \
  --region us-east-1

aws events put-targets \
  --rule thf-auto-cleanup-schedule-dev \
  --targets "Id=1,Arn=arn:aws:lambda:us-east-1:ACCOUNT_ID:function:thf-billing-auto-cleanup-dev" \
  --region us-east-1

aws lambda add-permission \
  --function-name thf-billing-auto-cleanup-dev \
  --statement-id AllowEventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:ACCOUNT_ID:rule/thf-auto-cleanup-schedule-dev \
  --region us-east-1
```

---

### Step 6: Verify Billing Status UI

```bash
# Start Streamlit dashboard
streamlit run dashboard/pages/billing.py

# Navigate to: http://localhost:8501
# Check:
# - Billing status displays (OK/WARN/FAIL)
# - Metrics cards show current cost
# - Event log shows recent actions
# - Toggle "Use Real CloudWatch Data" (requires AWS credentials)
```

---

## ✅ Verification Checklist

- [ ] CloudWatch Alarms created and in OK state
- [ ] SNS subscription confirmed (check email)
- [ ] Auto-Suspend Lambda dry-run successful
- [ ] Auto-Cleanup Lambda dry-run successful
- [ ] EventBridge schedules enabled
- [ ] Billing Status UI displays live data
- [ ] Test notification: Manually set alarm to ALARM state

---

## 🧪 Testing

### Test 1: Manual Alarm Trigger

```bash
# Set WARN alarm to ALARM state (for testing)
aws cloudwatch set-alarm-state \
  --alarm-name MotionScan-dev-Billing-Warn \
  --state-value ALARM \
  --state-reason "Manual test" \
  --region us-east-1

# Check if SNS notification received
# Check Billing Status UI shows WARN state

# Reset to OK
aws cloudwatch set-alarm-state \
  --alarm-name MotionScan-dev-Billing-Warn \
  --state-value OK \
  --state-reason "Test complete" \
  --region us-east-1
```

### Test 2: Auto-Suspend Dry-Run

```bash
# Create a test Lambda with AutoSuspend tag
aws lambda tag-resource \
  --resource arn:aws:lambda:us-east-1:ACCOUNT_ID:function:test-function \
  --tags AutoSuspend=true

# Invoke Auto-Suspend (ensure DRY_RUN=true)
aws lambda invoke \
  --function-name thf-billing-auto-suspend-dev \
  --payload '{}' \
  /tmp/test_suspend.json

# Verify test-function appears in dry-run output
cat /tmp/test_suspend.json
```

### Test 3: Auto-Cleanup Dry-Run

```bash
# Create unattached EBS volume with AutoCleanup tag
VOLUME_ID=$(aws ec2 create-volume \
  --size 1 \
  --availability-zone us-east-1a \
  --tag-specifications 'ResourceType=volume,Tags=[{Key=AutoCleanup,Value=allow},{Key=Name,Value=test-cleanup}]' \
  --query 'VolumeId' \
  --output text)

# Wait 48h (or modify TTL_HOURS to 1 for testing)

# Invoke Auto-Cleanup
aws lambda invoke \
  --function-name thf-billing-auto-cleanup-dev \
  --payload '{}' \
  /tmp/test_cleanup.json

# Verify volume appears in output
cat /tmp/test_cleanup.json

# Cleanup test volume
aws ec2 delete-volume --volume-id $VOLUME_ID
```

---

## 🚨 Troubleshooting

### Issue: Alarms always in "INSUFFICIENT_DATA"

**Cause**: Billing metrics not enabled or not enough data points

**Solution**:
1. Enable billing alerts in AWS Console (Billing Preferences)
2. Wait 6-12 hours for first data points
3. Check metrics: `aws cloudwatch list-metrics --namespace AWS/Billing`

### Issue: Lambda invocation fails with permission error

**Cause**: Missing IAM permissions

**Solution**: Attach policy to Lambda execution role:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:GetMetricStatistics",
        "ec2:DescribeInstances",
        "ec2:StopInstances",
        "ec2:DescribeVolumes",
        "ec2:CreateSnapshot",
        "ec2:DeleteVolume",
        "lambda:PutFunctionConcurrency",
        "lambda:ListFunctions",
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "*"
    }
  ]
}
```

### Issue: Auto-Suspend not stopping resources

**Cause**: DRY_RUN still enabled

**Solution**: Update Lambda environment variable to `DRY_RUN=false`

---

## 📊 Monitoring

After deployment, monitor:

1. **CloudWatch Logs**: Check Lambda execution logs
   ```bash
   aws logs tail /aws/lambda/thf-billing-auto-suspend-dev --follow
   ```

2. **Billing Events Log**: Check S3 for audit trail
   ```bash
   aws s3 cp s3://thf-logs/billing_events.jsonl - | tail -n 20
   ```

3. **Cost Explorer**: Verify cost reduction after auto-suspend/cleanup

---

## 🔄 Rollback

To disable billing guardrails:

```bash
# Disable EventBridge schedules
aws events disable-rule --name thf-auto-suspend-schedule-dev
aws events disable-rule --name thf-auto-cleanup-schedule-dev

# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name thf-billing-guardrail-dev

# Manually restore stopped resources if needed
aws ec2 start-instances --instance-ids i-xxxxx
aws lambda delete-function-concurrency --function-name thf-xxxxx
```

---

**Related Docs**:
- [Billing Emergency Stop Runbook](../runbooks/billing_emergency_stop.md)
- [CloudWatch Alarms Template](../../infrastructure/cloudwatch-alarms.yaml)
- [Auto-Suspend Lambda](../../lambda/billing/auto_suspend.py)
- [Auto-Cleanup Lambda](../../lambda/billing/auto_cleanup.py)
