# ADR-039: Dev Billing Guardrails Thresholds & Follow-Ups

- Date: 2025-11-08
- Status: Accepted
- Deciders: Ops Engineering (T. Fujimoto, Billing Guardrails Squad)

## Context

Billing guardrails for the dev environment needed a concrete minimum viable configuration to prevent unexpected AWS charges. The team agreed to ship a lean SAM stack that provisions an alerts SNS topic, subscribes the on-call mailbox, and defines six CloudWatch alarms (billing, EBS unattached, Lambda invocations) so we can dry-run emergency scenarios with `set-alarm-state`. The prior template exposed only percentage-based billing alarms and required manual SNS configuration, which slowed down acceptance testing.

## Decision

- Extend `template.yaml` with explicit parameters for the dev guardrail thresholds:
  - `EstimatedChargesWarnUsd=4`, `EstimatedChargesFailUsd=5`
  - `UnattachedEbsWarnCount=1`, `UnattachedEbsFailCount=2`
  - `LambdaInvocationsWarn5Min=3000`, `LambdaInvocationsFail5Min=5000`
- Always create the alerts SNS topic (`thf-alerts-<env>`) and attach an email subscription when `AlertsEmail` is non-empty. For dev the default contact is `tfujimoto913@gmail.com`.
- Add six CloudWatch alarms named `thf-billing-*`, `thf-ebs-unattached-*`, and `thf-lambda-invocations-5m-*`, each publishing WARN/FAIL transitions (and OK resets) to the SNS topic.
- Document the deployment and simulation workflow in the Billing Fail-Safe runbook, including the validation loop that resets alarms after testing.

## Rationale

- Parameterising absolute thresholds lets us tune per-environment guardrails without editing resource definitions.
- Enforcing a wired SNS subscription removes the manual “create topic → subscribe → attach alarms” loop and ensures notifications work before we rely on them.
- Explicit dev alarm names align with the `set-alarm-state` smoke test scripts and isolate these budget checks from the production `MotionScan-*` alarms.
- Recording the steps in the runbook keeps on-call and reviewers aligned on how to re-validate the guardrails at any time.

## Consequences

**Positive**:
- Dev guardrails can be deployed and validated in minutes, making regressions obvious via `NumberOfNotificationsDelivered`.
- The on-call mailbox (`tfujimoto913@gmail.com`) receives both WARN/FAIL and reset notifications automatically.
- Guardrail adoption is traceable via the runbook and ADR, giving clear provenance for future audits.

**Negative**:
- Until Auto-Cleanup emits `THF/Billing:UnattachedEBSCount`, the EBS alarms rely on manual `set-alarm-state` simulations.
- WARN/FAIL notifications double-fire (entry + clear) which may need filtering once more channels subscribe.

**Neutral**:
- Billing alarms remain us-east-1 specific; non-us-east-1 deployments must still be coordinated manually.

## Alternatives Considered

**Alternative 1: Keep percentage-based alarms only**
- Description: Rely solely on the existing `MotionScan-*-Billing-{Warn,Fail}` ratios.
- Pros: No template changes, reuse established alarms.
- Cons: Hard to simulate charges, no coverage for EBS or Lambda spikes, SNS wiring still manual.
- Decision: ❌ Rejected because it does not deliver the dev MVP guardrail experience.

**Alternative 2: Provision alarms via Terraform module**
- Description: Build a dedicated Terraform module for guardrails instead of modifying SAM.
- Pros: Separates infra concerns, could share with other stacks.
- Cons: Introduces a second IaC toolchain and slows delivery.
- Decision: ❌ Rejected to keep the MVP within the existing SAM deployment workflow.

## Implementation Details

- Parameters and alarms live in `template.yaml` (`EstimatedCharges*`, `UnattachedEbs*`, `LambdaInvocations*`, `thf-*` alarm resources).
- SNS publish permissions are enforced via `AlertsTopicPolicy`; email subscription is conditional on `AlertsEmail`.
- Runbook section “0. Dev Guardrail Deployment (SNS + CloudWatch Alarms)” captures deployment commands and KPI validation.

## References

- Files: `template.yaml`, `docs/runbooks/billing_fail_safe.md`
- Commands: `sam deploy`, `aws cloudwatch set-alarm-state`, `aws cloudwatch get-metric-statistics`

## Notes

- Follow-ups:
  1. Add billing dashboard tiles (Charges, UnattachedEBS, LambdaInvocations) to Streamlit.
  2. Emit `THF/Billing:UnattachedEBSCount` from the Auto-Cleanup flow (default to zero on weekly heartbeat).
