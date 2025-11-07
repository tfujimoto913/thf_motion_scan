# UI Monitoring Runbook v1.0

**Purpose**: Incident response procedures for billing and UI performance alerts
**Trigger**: CloudWatch Alarms (WARN/FAIL thresholds)
**Expected Duration**: 5-30 minutes (first response to resolution)
**Last Updated**: 2025-11-04

---

## 📋 Overview

This runbook guides engineers through responding to monitoring alerts from the Billing Status Dashboard and UI Performance monitoring system.

**Monitored Components:**
1. **Billing Cost** - AWS monthly charges (WARN: $4, FAIL: $5)
2. **UI Render Time** - Streamlit page load performance (WARN: P75>800ms, FAIL: P90>1200ms)
3. **UI Error Rate** - Validation errors and exceptions (WARN: P75, FAIL: P90)
4. **UI Availability** - Dashboard uptime (WARN: <99%, FAIL: <95%)

---

## ⚙️ Operational Guidelines

### Rule Change Policy
- **Minimum Change Unit**: Implement monitoring rule changes incrementally with clear impact scope and rollback steps documented
- **Threshold Setting Process**:
  1. Base initial threshold on measured P95 ± 10% buffer
  2. Observe for 1 business day (A/B comparison)
  3. Finalize after verification
- **False Positive Review Trigger**: If false positive rate exceeds 7-day average by +20%, schedule mini-review immediately

### Response SLAs
- **High Priority Events (Priority=High)**:
  - First response: Within 5 minutes
  - Root cause hypothesis and temporary mitigation: Logged within 30 minutes

### Change Management
All monitoring rule changes must include:
- Link to tracking ticket
- Before/after metrics:
  - Detection count
  - False positive rate
  - Reproduction steps

### Rollback Criteria (Automatic)
Execute rollback **immediately** if any condition is met:
- False positive rate increases by +30%
- Single critical event miss detected
- Multiple concurrent FAIL-level alerts (3+)

---

## 🚨 Alert Notification

You will receive notifications via:
- **SNS Email**: Subject line indicates severity and component
- **Dashboard Banner**: Alert badge on Billing Status page
- **Slack** (future): #thf-alerts channel

**Severity Levels:**
- 🟡 **WARN**: Approaching threshold, investigation recommended
- 🔴 **FAIL**: Threshold exceeded, immediate action required

---

## 1️⃣ First Response (Within 5 Minutes)

### Step 1: Acknowledge Alert

**Actions:**
1. Open Billing Status Dashboard: `streamlit run dashboard/pages/billing.py`
2. Check alert badges at top of page
3. Click **"📋 View Runbook"** button
4. Click **"✅ Acknowledge & Close"** to confirm receipt

### Step 2: Quick Diagnostics

**For Billing WARN/FAIL:**
```bash
# Check current cost
aws cloudwatch get-metric-statistics \
  --namespace AWS/Billing \
  --metric-name EstimatedCharges \
  --dimensions Name=Currency,Value=USD \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 21600 \
  --statistics Maximum \
  --region us-east-1

# Review recent resource changes
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=RunInstances \
  --start-time $(date -u -d '24 hours ago' +%s) \
  --max-results 10

# Check Cost Explorer (AWS Console)
# Navigate to: Billing Dashboard → Cost Explorer
```

**For UI Performance WARN/FAIL:**
```bash
# Check Streamlit logs
tail -n 100 logs/streamlit.log | grep -E "error|exception|timeout"

# Measure page load time manually
time curl http://localhost:8501/health

# Check render time metrics
aws cloudwatch get-metric-statistics \
  --namespace THF/MotionScan \
  --metric-name RenderTimeMilliseconds \
  --dimensions Name=Environment,Value=dev Name=Component,Value=ui \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,p75,p90 \
  --region us-east-1
```

**For UI Availability FAIL:**
```bash
# Verify dashboard accessibility
curl -I http://localhost:8501

# Check error logs
grep -i "error\|exception" logs/streamlit.log | tail -n 50

# Check Streamlit process
ps aux | grep streamlit

# Restart if needed
pkill -f streamlit
streamlit run dashboard/app.py
```

### Step 3: Review Monitoring Events Log

```bash
# Check recent monitoring events
tail -n 20 logs/monitoring_events.jsonl

# Filter by component
grep "billing" logs/monitoring_events.jsonl | tail -n 10
grep "ui" logs/monitoring_events.jsonl | tail -n 10
```

### Step 4: Notify Tech Lead (If FAIL Severity)

**When to escalate:**
- Any FAIL-level alert
- WARN-level alert lasting >30 minutes
- Multiple concurrent alerts

**Contact:**
- Slack: #thf-alerts
- Email: See `config/monitoring_rules.yaml` for contact list

---

## 2️⃣ Root Cause Analysis

### Investigation Template

Record findings in `logs/incident_reports/YYYY-MM-DD-<alert_name>.md`:

```markdown
# Incident Report: [Alert Name]

**Timestamp**: [YYYY-MM-DD HH:MM UTC]
**Alert**: [Billing Cost / UI Render Time / UI Error Rate / UI Availability]
**Severity**: [WARN / FAIL]
**Duration**: [Start - End]

## Observed Behavior

- **Metric Affected**: [Specific metric, e.g., EstimatedCharges, RenderTimeMilliseconds]
- **Threshold**: [Expected value]
- **Actual Value**: [Observed value]
- **Trend**: [Increasing / Decreasing / Stable]

## Quick Facts

- Recent deployments: [Yes/No - List versions]
- Configuration changes: [Yes/No - List changes]
- External events: [API outages, traffic spikes, etc.]

## Suspected Causes

1. **Hypothesis 1**: [Description]
   - Evidence: [Log entries, metric graphs, etc.]
   - Likelihood: [High / Medium / Low]

2. **Hypothesis 2**: [Description]
   - Evidence: [...]
   - Likelihood: [...]

## Evidence Collected

- CloudWatch metric screenshots: [Attach files]
- Log excerpts: [Paste relevant lines]
- Cost Explorer data: [Attach CSV or screenshot]
```

### Common Root Causes

**Billing Overruns:**
- Untagged resources (missing `preserve=true` tag)
- Lambda cold starts (excessive invocations)
- Data transfer costs (S3, CloudFront)
- Orphaned EBS volumes
- NAT Gateway traffic

**UI Performance Degradation:**
- Large dataset rendering (>1000 rows in st.dataframe)
- Blocking API calls (CloudWatch, S3) without caching
- Missing `@st.cache_data` decorators
- Memory leaks in long-running sessions

**UI Availability Issues:**
- Streamlit process crash
- Port conflict (8501 already in use)
- Missing dependencies (boto3, pandas)
- AWS credential expiration

---

## 3️⃣ Rollback Decision

### Automatic Rollback Triggers

Execute rollback **immediately** if any of these conditions are met:

| Trigger | Threshold | Action |
|---------|-----------|--------|
| False Positive Rate Increase | +30% | Revert threshold changes |
| Critical Event Miss | 1+ occurrences | Revert validation logic |
| Cost Overrun | >$5.00 | Emergency stop (see billing_emergency_stop.md) |
| UI Degradation | P90>1200ms for 3 periods | Revert UI changes, restart Streamlit |

### Rollback Procedure

#### For Lambda Changes

```bash
# 1. Stop current deployment
aws lambda update-function-configuration \
  --function-name thf-rep-rescore-worker-dev \
  --environment Variables={DRY_RUN=true} \
  --region us-east-1

# 2. List previous versions
aws lambda list-versions-by-function \
  --function-name thf-rep-rescore-worker-dev \
  --region us-east-1

# 3. Restore previous version (replace $VERSION with actual version number)
aws lambda update-alias \
  --function-name thf-rep-rescore-worker-dev \
  --name live \
  --function-version $VERSION \
  --region us-east-1

# 4. Verify rollback
aws lambda get-function \
  --function-name thf-rep-rescore-worker-dev \
  --region us-east-1 | jq '.Configuration.Version'

# 5. Record rollback event
echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"rollback\",\"component\":\"lambda\",\"reason\":\"cost_overrun\",\"actor\":\"$USER\"}" >> logs/monitoring_events.jsonl
```

#### For Threshold Configuration Changes

```bash
# 1. Restore previous thresholds.json
cd config/thresholds
cp thresholds-$(ls -t thresholds-*.json | head -n 1) thresholds.json

# 2. Verify restoration
cat thresholds.json | jq '.versions'

# 3. Record rollback
echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"rollback\",\"component\":\"thresholds\",\"reason\":\"false_positive_increase\",\"actor\":\"$USER\"}" >> logs/monitoring_events.jsonl

# 4. Restart Streamlit (to load new thresholds)
pkill -f streamlit
streamlit run dashboard/app.py &
```

#### For UI Changes

```bash
# 1. Git revert to last stable commit
git log --oneline -n 10  # Find last stable commit hash
git revert <commit-hash>

# 2. Restart Streamlit
pkill -f streamlit
streamlit run dashboard/app.py &

# 3. Verify UI accessibility
curl -I http://localhost:8501

# 4. Record rollback
echo "{\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"event\":\"rollback\",\"component\":\"ui\",\"reason\":\"performance_degradation\",\"actor\":\"$USER\"}" >> logs/monitoring_events.jsonl
```

---

## 4️⃣ Post-Rollback Verification

### Verification Checklist

**Wait 10-15 minutes after rollback, then verify:**

- [ ] CloudWatch Alarms return to OK state
  ```bash
  aws cloudwatch describe-alarms \
    --alarm-names "MotionScan-dev-Billing-Warn" "MotionScan-dev-Billing-Fail" \
    --region us-east-1 | jq '.MetricAlarms[].StateValue'
  ```

- [ ] Billing cost stabilizes below $4.00
  ```bash
  aws cloudwatch get-metric-statistics \
    --namespace AWS/Billing \
    --metric-name EstimatedCharges \
    --dimensions Name=Currency,Value=USD \
    --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
    --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
    --period 3600 \
    --statistics Maximum \
    --region us-east-1 | jq '.Datapoints[-1].Maximum'
  ```

- [ ] UI render time P75 < 800ms
  ```bash
  # Manual test: Measure page load time
  time streamlit run dashboard/pages/billing.py
  ```

- [ ] No new error spikes in logs
  ```bash
  grep -c "ERROR\|Exception" logs/streamlit.log | tail -n 1
  ```

- [ ] Dashboard accessibility confirmed
  ```bash
  curl -s -o /dev/null -w "%{http_code}" http://localhost:8501
  # Expected: 200
  ```

---

## 5️⃣ Mini-Review Meeting

### Scheduling

**Timeline**: Schedule within 24 hours of incident resolution
**Participants**:
- Tech Lead (required)
- Feature Owner (required)
- On-Call Engineer (required)

**Duration**: 30 minutes

### Meeting Agenda

1. **Incident Summary** (5 min)
   - Alert details (component, severity, duration)
   - Impact metrics (cost, performance, availability)

2. **Root Cause Analysis** (10 min)
   - Confirmed cause(s)
   - Contributing factors
   - Timeline of events

3. **Action Items** (10 min)
   - Preventive measures
   - Monitoring improvements
   - Documentation updates

4. **Threshold Adjustments** (5 min)
   - Current thresholds
   - Proposed changes
   - Rationale

### Meeting Template

```markdown
## Mini-Review: [Date] - [Alert Name]

**Date**: [YYYY-MM-DD]
**Participants**: [Names]
**Duration**: [Actual duration]

### Incident Summary

- **Alert**: [Name]
- **Severity**: [WARN / FAIL]
- **Duration**: [Start - End]
- **Impact**:
  - Cost: [$X.XX]
  - Performance: [P75 XXXms, P90 XXXms]
  - Availability: [XX.X%]

### Root Cause

**Confirmed Cause**:
[Description]

**Contributing Factors**:
- [Factor 1]
- [Factor 2]

### Action Items

- [ ] **[Action 1]**
  - Owner: [Name]
  - Due: [Date]
  - Priority: [High / Medium / Low]

- [ ] **[Action 2]**
  - Owner: [Name]
  - Due: [Date]
  - Priority: [High / Medium / Low]

### Threshold Adjustments

| Metric | Current | Proposed | Rationale |
|--------|---------|----------|-----------|
| Billing WARN | $4.00 | $4.50 | Seasonal traffic spike |
| UI Render Time P75 | 800ms | 900ms | Baseline shift after feature X |

### Follow-Up

**Next Review**: [Date, if needed]
**Documentation Updates**: [List files to update]
```

---

## 6️⃣ Escalation Path

### Escalation Levels

| Level | Role | Timeout | Contact |
|-------|------|---------|---------|
| 1 | On-Call Engineer | 5 minutes | Slack: #thf-alerts |
| 2 | Tech Lead | 10 minutes | Email: tech-lead@example.com |
| 3 | Engineering Manager | 15 minutes | Email: eng-manager@example.com |

### When to Escalate

**Escalate to Level 2** if:
- FAIL-level alert not resolved within 10 minutes
- Multiple concurrent alerts
- Rollback unsuccessful

**Escalate to Level 3** if:
- FAIL-level alert not resolved within 30 minutes
- Service outage affecting users
- Cost exceeding $10.00

---

## 7️⃣ Post-Incident Actions

### Required Documentation

1. **Incident Report**: `logs/incident_reports/YYYY-MM-DD-<alert_name>.md`
2. **Monitoring Event**: Append to `logs/monitoring_events.jsonl`
3. **Mini-Review Notes**: `docs/mini_reviews/YYYY-MM-DD-<alert_name>.md`

### Optional Actions

- Update `config/monitoring_rules.yaml` if thresholds changed
- Add test cases to prevent recurrence
- Update runbooks with new learnings

---

## 📊 Monitoring Events Log Format

Record all significant events in `logs/monitoring_events.jsonl`:

```json
{
  "timestamp": "2025-11-04T12:34:56Z",
  "event_type": "alarm_triggered",
  "component": "billing",
  "severity": "warn",
  "threshold": 4.0,
  "actual_value": 4.23,
  "action_taken": "acknowledged",
  "actor": "engineer@example.com",
  "metadata": {
    "alarm_name": "MotionScan-dev-Billing-Warn",
    "state_reason": "Threshold exceeded"
  }
}
```

**Event Types:**
- `alarm_triggered`: CloudWatch alarm entered ALARM state
- `threshold_breached`: Metric exceeded configured threshold
- `rollback_initiated`: Rollback procedure started
- `rollback_completed`: Rollback verified successful
- `incident_resolved`: Alert returned to OK state

---

## 🔗 Related Documentation

- **Billing Emergency Stop**: `docs/runbooks/billing_emergency_stop.md`
- **Billing Fail-Safe**: `docs/runbooks/billing_fail_safe.md`
- **Billing Guardrail Deployment**: `docs/deployment/billing-guardrail-deployment.md`
- **Monitoring Rules Config**: `config/monitoring_rules.yaml`
- **CloudWatch Alarms**: `infrastructure/ui-monitoring-alarms.yaml`

---

**Version History**:
- v1.1 (2025-11-04): Add Operational Guidelines section (rule change policy, SLAs, rollback criteria)
- v1.0 (2025-11-04): Initial version - UI Monitoring System v1
