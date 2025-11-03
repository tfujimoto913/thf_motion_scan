# Billing Fail-Safe Runbook

Purpose: validate the billing guardrails that protect THF Motion Scan from runaway charges.  
Scope: CloudWatch alarms for estimated AWS charges, unattached EBS volumes, and Lambda invocation usage.

## Prerequisites

- `aws` CLI configured for the `dev` account/region that hosts the stack.  
- The SAM stack deployed with the latest template (contains the new alarms and SNS topic).  
- Access to the SNS subscription used by `thf-alerts-<env>` so you can observe the notifications.

## Alarm Names

| Alarm | Purpose |
| ----- | ------- |
| `MotionScan-dev-Billing-Warn` / `MotionScan-dev-Billing-Fail` | Warn at 80 % / Fail at 100 % of `MonthlyBillingBudgetAmount`. |
| `MotionScan-dev-EBSUnattached-Warn` / `MotionScan-dev-EBSUnattached-Fail` | Watch unattached EBS volume counts (80 % / 100 % of `EBSUnattachedVolumeLimit`). |
| `MotionScan-dev-LambdaInvocations-Warn` / `MotionScan-dev-LambdaInvocations-Fail` | Track Lambda invocation usage relative to `LambdaMonthlyInvocationLimit`. |

> Replace `dev` in the alarm name with the target environment if you are validating another stage.

## Test Procedure (Simulated Events)

Because billing and usage metrics cannot be forced easily in non-prod, use the CloudWatch `set-alarm-state` API to simulate WARN/FAIL transitions. This keeps the workflow identical while avoiding real overages.

```bash
ENV=dev
TOPIC_EMAIL=<your-email@example.com>  # Ensure the SNS subscription is confirmed.

# 1. Force Billing WARN
aws cloudwatch set-alarm-state \
  --alarm-name "MotionScan-${ENV}-Billing-Warn" \
  --state-value ALARM \
  --state-reason "Simulated billing WARN for runbook validation"

# 2. Force Billing FAIL
aws cloudwatch set-alarm-state \
  --alarm-name "MotionScan-${ENV}-Billing-Fail" \
  --state-value ALARM \
  --state-reason "Simulated billing FAIL for runbook validation"

# 3. Force EBS Unattached WARN/FAIL
for LEVEL in Warn Fail; do
  aws cloudwatch set-alarm-state \
    --alarm-name "MotionScan-${ENV}-EBSUnattached-${LEVEL}" \
    --state-value ALARM \
    --state-reason "Simulated EBS ${LEVEL} threshold breach"
done

# 4. Force Lambda Invocation WARN/FAIL
for LEVEL in Warn Fail; do
  aws cloudwatch set-alarm-state \
    --alarm-name "MotionScan-${ENV}-LambdaInvocations-${LEVEL}" \
    --state-value ALARM \
    --state-reason "Simulated Lambda usage ${LEVEL} threshold breach"
done
```

After each command:

1. Confirm the SNS notification is delivered.  
2. Record `alarm_trigger_count` and `notification_delivery_success` in Mission Control notes.  
3. Reset the alarm to `OK` once testing is complete:

```bash
aws cloudwatch set-alarm-state \
  --alarm-name "MotionScan-${ENV}-Billing-Warn" \
  --state-value OK \
  --state-reason "Reset after simulation"
# Repeat for each alarm exercised.
```

## Updating Thresholds

Threshold parameters are exposed in `template.yaml`:

- `MonthlyBillingBudgetAmount` (USD).  
- `EBSUnattachedVolumeLimit` (count).  
- `LambdaMonthlyInvocationLimit` (count per month).

To adjust the limits:

1. Update the parameter value in `samconfig.toml` or provide `--parameter-overrides` during deployment.  
2. Redeploy the stack. Alarms will immediately adopt the new thresholds.

## References

- ADR-026 – Phase 5 Ops Guardrails.  
- Billing Fail-Safe design notes (Notion).  
- Mission Control Board – Operational rules.
