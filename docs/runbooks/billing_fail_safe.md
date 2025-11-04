# Billing Fail-Safe Runbook

Purpose: Validate the cost guardrails that ship with Billing Guard v0.1.
Scope: CloudWatch billing alarms, auto-suspend, EBS cleanup, and the Streamlit dashboard indicator.

## Prerequisites
- `aws` CLI configured for the target account. Runbook assumes `dev`/`staging`/`prod` stacks are deployed from `template.yaml` in this repo.
- You are subscribed to the SNS topic `thf-alerts-<env>` (email or Slack bridge) so you can observe notifications.
- Basic familiarity with the resource tags:
  - `AutoSuspend=true` on any EC2 instance or Lambda function that can be frozen automatically.
  - `AutoCleanup=allow` on EBS volumes that may be deleted after snapshot.
- (Optional) CloudWatch Logs console access to inspect `/thf/billing/<env>` structured events.

## Guardrail Components
| Component | Resource name | Behaviour |
| --- | --- | --- |
| Billing WARN / FAIL alarms | `MotionScan-<env>-Billing-Warn` / `MotionScan-<env>-Billing-Fail` | Triggers at 80% / 100% of the $5 budget, publishes to `thf-alerts-<env>` |
| Auto-Suspend scheduler | `MotionScan-<env>-AutoSuspend` Lambda, hourly EventBridge rule | Examines 2h request count; on <= threshold (default 1) it stops tagged EC2 and throttles tagged Lambda/EventBridge triggers |
| Billing Guard | `MotionScan-<env>-BillingGuard` Lambda (SNS target) | Fires when FAIL alarm enters `ALARM`, executes the same stop/throttle flow immediately |
| Auto-Cleanup | `MotionScan-<env>-AutoCleanup` Lambda (daily schedule) | Dry-run lists unattached >=48h volumes; production mode snapshots + deletes before notifying |
| Billing monitor logs | CloudWatch log group `/thf/billing/<env>` | Every guardrail writes structured JSON (`evt=billing_monitor`) for audit and dashboard use |

> Billing alarms are region-bound to `us-east-1`. Deploy the stack with identical parameters in each environment that requires guardrails.

## 0. Dev Guardrail Deployment (SNS + CloudWatch Alarms)
1. Deploy the stack to `us-east-1` with the dev-specific thresholds. Replace the stack name if needed but keep the region fixed (billing metrics are only emitted in `us-east-1`):
   ```bash
   sam deploy \
     --region us-east-1 \
     --stack-name thf-billing-guardrails-dev \
     --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
     --parameter-overrides \
       Environment=dev \
       EstimatedChargesWarnUsd=4 EstimatedChargesFailUsd=5 \
       UnattachedEbsWarnCount=1 UnattachedEbsFailCount=2 \
       LambdaInvocationsWarn5Min=3000 LambdaInvocationsFail5Min=5000 \
       AlertsEmail="tfujimoto913@gmail.com"
   ```
   Notifications will be sent to `thf-alerts-dev`; update the email address above if ownership changes.
2. Approve the email subscription sent to `tfujimoto913@gmail.com`. Until the confirmation link is accepted, SNS will drop the notifications.
3. Simulate WARN/FAIL transitions for all six alarms to confirm notifications and guardrail wiring (replace the environment if you cloned the stack name):
   ```bash
   aws cloudwatch set-alarm-state --region us-east-1 \
     --alarm-name thf-billing-EstimatedCharges-WARN-dev --state-value ALARM --state-reason "simulated warn"
   aws cloudwatch set-alarm-state --region us-east-1 \
     --alarm-name thf-billing-EstimatedCharges-FAIL-dev --state-value ALARM --state-reason "simulated fail"

   aws cloudwatch set-alarm-state --region us-east-1 \
     --alarm-name thf-ebs-unattached-WARN-dev --state-value ALARM --state-reason "simulated warn"
   aws cloudwatch set-alarm-state --region us-east-1 \
     --alarm-name thf-ebs-unattached-FAIL-dev --state-value ALARM --state-reason "simulated fail"

   aws cloudwatch set-alarm-state --region us-east-1 \
     --alarm-name thf-lambda-invocations-5m-WARN-dev --state-value ALARM --state-reason "simulated warn"
   aws cloudwatch set-alarm-state --region us-east-1 \
     --alarm-name thf-lambda-invocations-5m-FAIL-dev --state-value ALARM --state-reason "simulated fail"
   ```
4. Reset every alarm back to `OK` once notifications are collected to avoid leaving the environment in alarm:
   ```bash
   for a in \
     thf-billing-EstimatedCharges-WARN-dev \
     thf-billing-EstimatedCharges-FAIL-dev \
     thf-ebs-unattached-WARN-dev \
     thf-ebs-unattached-FAIL-dev \
     thf-lambda-invocations-5m-WARN-dev \
     thf-lambda-invocations-5m-FAIL-dev; do
     aws cloudwatch set-alarm-state --region us-east-1 \
       --alarm-name "$a" --state-value OK --state-reason "reset to OK after test"
   done
   ```
5. Capture delivery evidence:
   ```bash
   TOPIC_ARN=$(aws cloudformation describe-stacks --region us-east-1 \
     --stack-name thf-billing-guardrails-dev \
     --query "Stacks[0].Outputs[?OutputKey=='AlertsTopicArn'].OutputValue" --output text)

   aws cloudwatch get-metric-statistics --region us-east-1 \
     --namespace AWS/SNS --metric-name NumberOfNotificationsDelivered \
     --statistics Sum --period 300 \
     --start-time "$(date -u -v-15M +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '15 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
     --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     --dimensions Name=TopicName,Value="$(echo "$TOPIC_ARN" | awk -F: '{print $NF}')"

   aws cloudwatch describe-alarm-history --region us-east-1 \
     --alarm-name thf-billing-EstimatedCharges-WARN-dev \
     --history-item-type StateUpdate --max-items 10
   ```

### Monitoring KPI
- `alarm_trigger_count`: use `describe-alarm-history` (StateUpdate) per alarm to confirm WARN/FAIL transitions were exercised.
- `notification_delivery_success`: rely on `AWS/SNS:NumberOfNotificationsDelivered` for `thf-alerts-dev`; investigate any spikes in `NumberOfNotificationsFailed`.

## 1. Billing Alarms (WARN / FAIL)
1. Enable AWS billing alerts for the account (`Billing → Preferences → Receive Billing Alerts`).
2. Simulate the WARN transition:
   ```bash
   ENV=dev
   aws cloudwatch set-alarm-state \
     --region us-east-1 \
     --alarm-name "MotionScan-${ENV}-Billing-Warn" \
     --state-value ALARM \
     --state-reason "Simulated WARN for validation"
   ```
3. Confirm:
   - SNS notification arrives (subject includes `WARN`).
   - `/thf/billing/${ENV}` log stream contains a `kind: "traffic_ok"` event with the simulated change.
   - Streamlit sidebar shows `WARN` in yellow.
4. Reset WARN back to OK once validated:
   ```bash
   aws cloudwatch set-alarm-state \
     --region us-east-1 \
     --alarm-name "MotionScan-${ENV}-Billing-Warn" \
     --state-value OK \
     --state-reason "Reset after WARN simulation"
   ```
5. Repeat steps 2–4 for the FAIL alarm (`MotionScan-${ENV}-Billing-Fail`). The FAIL test should also trigger the Billing Guard Lambda (covered below).

## 2. Billing Guard (FAIL -> Emergency Stop)
1. Pre-check the scope: list tagged resources to ensure only expendable compute will be touched.
   ```bash
   aws ec2 describe-instances --filters Name=tag:AutoSuspend,Values=true Name=instance-state-name,Values=running --query 'Reservations[].Instances[].InstanceId'
   aws lambda list-functions --query 'Functions[?contains(Tags.AutoSuspend, `true`)].FunctionName'
   ```
2. Dry-run the Billing Guard manually to see the plan without stopping anything:
   ```bash
   aws lambda invoke \
     --function-name MotionScan-${ENV}-BillingGuard \
     --payload '{"force": true, "dry_run": true}' \
     --cli-binary-format raw-in-base64-out /tmp/billing_guard_dry_run.json
   cat /tmp/billing_guard_dry_run.json
   ```
   The response enumerates which instances/functions would be frozen.
3. Trigger an end-to-end FAIL scenario:
   - Run the `set-alarm-state` command for the FAIL alarm (step 1 above).
   - Observe SNS notification (`FAIL`) and the Billing Guard Lambda invocation (CloudWatch Logs + `/thf/billing/<env>` event `kind: "billing_guard"`).
   - Verify effects:
     ```bash
     aws ec2 describe-instances --filters Name=instance-state-name,Values=stopping,stopped Name=tag:AutoSuspend,Values=true
     aws lambda get-function-concurrency --function-name <function-name>
     aws events list-rule-names-by-target --target-arn <function-arn>
     ```
     Target functions should report `ReservedConcurrentExecutions = 0`, and associated EventBridge rules become `DISABLED`.
4. Reset:
   - Set the FAIL alarm back to `OK`.
   - Manually re-enable EventBridge rules and restore reserved concurrency (recorded in the `billing_guard` event payload) before restarting EC2 instances.

## 3. Auto-Suspend (Hourly schedule)
1. The scheduler runs each hour. To review planned actions without stopping anything:
   ```bash
   aws lambda invoke \
     --function-name MotionScan-${ENV}-AutoSuspend \
     --payload '{"force": true, "dry_run": true}' \
     --cli-binary-format raw-in-base64-out /tmp/auto_suspend_dry_run.json
   cat /tmp/auto_suspend_dry_run.json
   ```
2. Optional production test (only in a safe environment): rerun the command without `"dry_run": true`. Tagged EC2 instances will stop and tagged Lambda functions will be throttled. Restore services manually afterwards.
3. Review billing monitor logs (`kind: "auto_suspend"`) for audit evidence.

## 4. Auto-Cleanup (EBS volumes)
1. Confirm the function is in `DRY_RUN=true` mode (default). Invoke to generate the unattached volume report:
   ```bash
   aws lambda invoke \
     --function-name MotionScan-${ENV}-AutoCleanup \
     --cli-binary-format raw-in-base64-out /tmp/auto_cleanup_report.json
   cat /tmp/auto_cleanup_report.json
   ```
   The response contains a `volumes` array and the same payload is logged to `/thf/billing/<env>` (`kind: "ebs_unattached"`).
2. To execute deletion (only after review): either update the Lambda environment variable `DRY_RUN=false` or override per invocation:
   ```bash
   aws lambda invoke \
     --function-name MotionScan-${ENV}-AutoCleanup \
     --payload '{"dry_run": false}' \
     --cli-binary-format raw-in-base64-out /tmp/auto_cleanup_execute.json
   ```
   Each volume is snapshotted (tagged with `OriginVolumeId`, `CleanupAt`, `Environment`) before deletion. SNS subject `[INFO] EBS cleanup completed` confirms success.

## 5. Streamlit Dashboard
1. Launch the dashboard (`run_dashboard.sh` or `streamlit run dashboard/app.py`).
2. The sidebar block **💳 Billing Status** should show:
   - ✅ `OK` when both alarms are in `OK`.
   - ⚠️ `WARN` or ❌ `FAIL` based on the active alarm state.
   - Raw alarm states are listed below the badge for quick troubleshooting.
3. Use the Monitoring page (`pages/monitoring.py`) to cross-check the DLQ view together with the billing banner.

## Cleanup & Reporting
- Always reset simulated alarms to `OK` after tests to allow the scheduler to resume normally.
- Record outcomes in the Mission Board (Milestone 1–5 checkboxes) including notification delivery evidence.
- File a ticket if any guardrail fails to respond or if the Streamlit dashboard does not reflect alarm state within one refresh.

## Reference Commands
- Billing monitor logs: `aws logs tail /thf/billing/<env> --since 1h`.
- Restore Lambda concurrency: `aws lambda delete-function-concurrency --function-name <name>` then set intended limit.
- Re-enable EventBridge triggers: `aws events enable-rule --name <rule-name>`.

## Parameters & Tuning
- Billing budget: `MonthlyBillingBudgetAmount` (default 5 USD).
- Auto-suspend request threshold: `AutoSuspendRequestThreshold` (default 1 request over 2 hours).
- EBS cleanup TTL: `AutoCleanupUnattachedTtlHours` (default 48h).
- Structured log retention: `BillingMonitorLogRetentionInDays` (default 90 days).

Keep this runbook updated as additional guardrails (API throttling, AWS Backup automation) are introduced.
