# SQS DLQ Redrive Runbook

This runbook documents the minimum operational steps to safely redrive messages from the **Motion Scan processing DLQ** back to the main SQS queue and observe the result. Follow it whenever CloudWatch raises the *MotionScan-<env>-LandmarkDetectionFailures* or other queue-related alarms and the DLQ contains recoverable events.

## 1. Preconditions

- ✅ Confirm CloudWatch alarm(s) and capture the alert context (SNS email from `thf-alerts`).
- ✅ Review the DLQ messages in the AWS console to understand the dominant failure reason.
- ✅ Ensure no ongoing emergency changes: coordinate with the backend lead if deploying simultaneously.
- ✅ Export AWS credentials for the target environment (`AWS_PROFILE`, or `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`).

## 2. Command Reference

Run the helper script from the repository root. Replace the placeholders with the environment-specific queue URLs (available via `aws sqs get-queue-url` or CloudFormation outputs).

```bash
python3 scripts/redrive.py \
  --source-queue https://sqs.ap-northeast-1.amazonaws.com/<acct>/thf-motion-scan-processing-queue \
  --dlq https://sqs.ap-northeast-1.amazonaws.com/<acct>/thf-motion-scan-dlq \
  --environment prod \
  --rules-version 2025-Phase5 \
  --artifact-sha $(git rev-parse HEAD)
```

### Key options

- `--batch-size` (default **25**): maximum messages to requeue per batch (Lambda limit).
- `--interval` (default **60s**): wait time between batches to let the system stabilise.
- `--max-batches` (default **10**): hard guardrail for total messages (<= 250).
- `--order` (**asc** default): requeue oldest messages first; use `desc` for targeted recent events.
- `--table-name` (default `motion-scan-results`): DynamoDB table used for the UserErrors spike check.

The script emits a JSON summary to `stdout`, for example:

```json
{"moved": 25, "batches": 1, "stopped_reason": "DLQ_DRAINED", ...}
```

Store this output in the incident trail (Notion card + Slack thread).

## 3. Automatic Stop Conditions

The script enforces the Phase 5 guardrails automatically:

1. **Repeated failure reason** – stops if 5 consecutive messages share the same extracted root cause (prevents infinite loops).
2. **DynamoDB UserErrors spike** – calls CloudWatch after each batch and aborts when `AWS/DynamoDB:UserErrors` increases by ≥10 within the trailing 5 minutes.
3. **Safety caps** – DLQ empty, fewer than `batch-size` messages returned, or `max-batches` reached.
4. ** Operator interrupt** – Ctrl+C is handled gracefully and logged as `INTERRUPTED`.

All stops include an `stopped_reason` code in the summary JSON.

## 4. Observability Checklist

- **CloudWatch Metrics**
  - `THF/MotionScan:RedriveSuccessCount` / `RedriveFailureCount` – emitted per message.
  - `THF/MotionScan:LandmarkDetectionFailures` – drops after successful reprocessing.
  - `AWS/SQS:ApproximateNumberOfMessagesVisible` for both the main queue and DLQ.
- **Alarms**
  - Verify that `MotionScan-<env>-LandmarkDetectionFailures` and `MotionScan-<env>-DynamoUserErrors` return to OK.
  - Confirm SNS notification from `thf-alerts-<env>` for both ALARM and OK transitions.
- **Dashboard**
  - `MotionScan-Ops-<env>` dashboard widgets should visualise the redrive (Requests, Error Rate, Retry Success Rate, DLQ panels).
  - Logs Insights widgets (Error trend, detection rate ranking) should reflect the recovery.

## 5. Post-run Actions

1. Validate a representative message in DynamoDB (`motion-scan-results`) to ensure the processing result is present and contains the mandatory fields (`athleteId`, `sessionId`, `requestId`, etc.).
2. Share the JSON summary plus any noteworthy observations in the Notion Phase 5 Ops card and Slack `#motion-scan-ops`.
3. If failures persist for the same root cause, escalate to the backend lead before attempting another redrive.

## 6. References

- Script: `scripts/redrive.py`
- CloudFormation Guardrails: `template.yaml` (`AlertsTopic`, alarms, dashboard)
- Metrics namespace: `THF/MotionScan`
- SNS topic: `thf-alerts-<env>` (email subscription until Slack integration lands)
