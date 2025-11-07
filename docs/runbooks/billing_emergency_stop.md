# Billing Emergency Stop Runbook

**Purpose**: Manual resource shutdown procedure when billing exceeds $5/month
**Trigger**: `MotionScan-{env}-Billing-Fail` alarm state = ALARM
**Expected Duration**: 5-10 minutes
**Last Updated**: 2025-11-04

---

## 🚨 Alert Notification

You will receive an SNS notification (email/Slack) with:
```
ALARM: MotionScan-dev-Billing-Fail in US East (N. Virginia)
Threshold Crossed: EstimatedCharges > $5.00 (Maximum)
Current Value: $5.23
```

---

## ✅ Pre-Check

Before executing, verify:
1. **Alarm is genuine**: Check CloudWatch console for EstimatedCharges metric
2. **Not a false positive**: Billing metrics update ~4 times/day, confirm trend
3. **Backup status**: Ensure recent snapshots exist (RDS, EBS)

---

## 🛑 Emergency Stop Procedure

### Step 1: Stop Lambda Functions (Highest Cost)

```bash
# List all Lambda functions
aws lambda list-functions --region us-east-1 --query 'Functions[?starts_with(FunctionName, `thf-`)].FunctionName'

# Update concurrency to 0 (effectively disables invocations)
aws lambda put-function-concurrency \
  --function-name thf-rep-rescore-worker-dev \
  --reserved-concurrent-executions 0 \
  --region us-east-1

# Repeat for all thf-* functions
```

### Step 2: Stop EC2 Instances

```bash
# List running instances with project tag
aws ec2 describe-instances \
  --filters "Name=tag:Project,Values=thf-motion-scan" "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].[InstanceId,Tags[?Key==`Name`].Value|[0]]' \
  --region us-east-1

# Stop instances
aws ec2 stop-instances \
  --instance-ids i-1234567890abcdef0 \
  --region us-east-1
```

### Step 3: Stop RDS Instances

```bash
# List RDS instances
aws rds describe-db-instances \
  --query 'DBInstances[?starts_with(DBInstanceIdentifier, `thf-`)].DBInstanceIdentifier' \
  --region us-east-1

# Stop RDS instance (max 7 days, will auto-restart)
aws rds stop-db-instance \
  --db-instance-identifier thf-motion-scan-dev \
  --region us-east-1
```

### Step 4: Disable EventBridge Schedules

```bash
# List schedules
aws events list-rules \
  --name-prefix thf- \
  --region us-east-1

# Disable schedule
aws events disable-rule \
  --name thf-auto-cleanup-schedule-dev \
  --region us-east-1
```

### Step 5: Delete Unattached EBS Volumes (Optional)

```bash
# List unattached volumes
aws ec2 describe-volumes \
  --filters "Name=status,Values=available" "Name=tag:Project,Values=thf-motion-scan" \
  --query 'Volumes[].[VolumeId,Size,CreateTime]' \
  --region us-east-1

# Create snapshot before deletion
aws ec2 create-snapshot \
  --volume-id vol-0987654321fedcba \
  --description "Emergency backup before billing stop" \
  --region us-east-1

# Delete volume
aws ec2 delete-volume \
  --volume-id vol-0987654321fedcba \
  --region us-east-1
```

---

## 📊 Verify Cost Reduction

Wait 6-12 hours, then check:

```bash
# Check current billing estimate
aws cloudwatch get-metric-statistics \
  --namespace AWS/Billing \
  --metric-name EstimatedCharges \
  --dimensions Name=Currency,Value=USD \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 21600 \
  --statistics Maximum \
  --region us-east-1
```

---

## 🔄 Recovery Procedure

Once billing is under control:

1. **Re-enable Lambda**: `put-function-concurrency` with original value (or delete reservation)
2. **Start EC2**: `aws ec2 start-instances --instance-ids ...`
3. **Start RDS**: `aws rds start-db-instance --db-instance-identifier ...`
4. **Enable Schedules**: `aws events enable-rule --name ...`

---

## 📝 Post-Incident Review

Document in `config/thresholds/changelog.jsonl`:

```json
{
  "timestamp": "2025-11-04T12:00:00Z",
  "event": "billing_emergency_stop",
  "trigger": "BillingFailAlarm",
  "estimated_charges": 5.23,
  "actions_taken": ["lambda_disabled", "ec2_stopped", "rds_stopped"],
  "recovery_time": "2025-11-04T18:00:00Z"
}
```

---

## 🚨 Escalation

If billing continues to rise after shutdown:
1. Check for **orphaned resources** (NAT Gateways, Load Balancers)
2. Review **Data Transfer costs** (S3, CloudFront)
3. Contact AWS Support for detailed billing analysis

---

**Related**:
- [Billing Fail-Safe Runbook](./billing_fail_safe.md)
- [Auto-Suspend Lambda](../../lambda/billing/auto_suspend.py)
- [CloudWatch Alarms](../../infrastructure/cloudwatch-alarms.yaml)
