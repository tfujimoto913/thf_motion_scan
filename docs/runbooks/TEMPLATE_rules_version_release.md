# Rules Version Release Checklist Template

**Purpose**: Copy this template for each release. Fill in blanks and check boxes as you progress.

**Notion Instructions**: Copy this entire document to Notion, convert checkboxes to Notion tasks, and track progress in real-time.

---

## 📋 Release Information

| Item | Value |
|------|-------|
| **Release Version** | v_______ → v_______ |
| **Release Date** | YYYY-MM-DD |
| **Environment** | ☐ dev ☐ staging ☐ prod |
| **Release Type** | ☐ Standard ☐ Canary ☐ Emergency Hotfix |
| **ADR Reference** | ADR-_______ |

---

## 👥 Team Assignment

| Role | Name | Contact | Status |
|------|------|---------|--------|
| **Release Owner** | __________ | __________ | ☐ Assigned |
| **Monitoring Lead** | __________ | __________ | ☐ Assigned |
| **Rollback Executor** | __________ | __________ | ☐ Assigned |
| **Escalation Contact** | __________ | __________ | ☐ Assigned |

**Communication Channels**:
- Primary: __________
- Secondary: __________
- Emergency: __________

---

## ✅ Pre-Release Checklist

### Technical Validation
- [ ] New thresholds validated in dev environment
- [ ] `thresholds.json` updated with new rules_version
- [ ] JSON schema validation passed (`sam validate`)
- [ ] Unit tests passed (`pytest tests/`)
- [ ] Changelog updated in `docs/adr/`
- [ ] Git commit created: `__________ (commit SHA)`

### Operational Governance
- [ ] Release team roles assigned (see table above)
- [ ] Monitoring dashboard accessible: `__________ (URL)`
- [ ] SNS topic subscriptions confirmed
- [ ] Rollback executor has AWS credentials
- [ ] Communication channels tested
- [ ] Post-deployment monitoring schedule agreed upon
- [ ] Escalation path defined
- [ ] Canary deployment decision: ☐ Yes ☐ No (Reason: __________)

---

## 🚀 Release Execution

### Step 1: Update Thresholds
- [ ] **Timestamp**: __________
- [ ] Edited `config/thresholds.json`
- [ ] Version updated to: __________
- [ ] Git commit SHA: __________

### Step 2: Deploy to Dev
- [ ] **Timestamp**: __________
- [ ] Ran `sam build`
- [ ] Ran `sam deploy --parameter-overrides Environment=dev`
- [ ] Stack status: `__________ (UPDATE_COMPLETE expected)`

### Step 3: Enable Metrics Monitoring
- [ ] **Timestamp**: __________
- [ ] Verified MetricsMonitorFunction enabled
- [ ] Verified EventBridge rule enabled
- [ ] Verified DynamoDB table exists

### Step 4: Monitor Dev (30 Minutes)
- [ ] **Start Time**: __________
- [ ] **End Time**: __________
- [ ] CloudWatch Dashboard checked every 5 minutes
- [ ] DynamoDB state table checked (no WARN/FAIL)
- [ ] No SNS alarm notifications received
- [ ] Metrics stable: BCR ≥ 0.5, Kappa ≥ 0.3, Override ≤ 30%

**Monitoring Log** (record every 5 minutes):
| Time | BCR | Kappa | Override | State | Notes |
|------|-----|-------|----------|-------|-------|
| +5min | ____ | ____ | ____ | ____ | ____ |
| +10min | ____ | ____ | ____ | ____ | ____ |
| +15min | ____ | ____ | ____ | ____ | ____ |
| +20min | ____ | ____ | ____ | ____ | ____ |
| +25min | ____ | ____ | ____ | ____ | ____ |
| +30min | ____ | ____ | ____ | ____ | ____ |

### Step 5: Rollback Decision
- [ ] **Dev monitoring passed**: ☐ Yes ☐ No
- [ ] **If No, reason**: __________
- [ ] **Rollback executed**: ☐ Yes ☐ No ☐ N/A
- [ ] **Rollback timestamp**: __________

### Step 6: Deploy to Staging (If Dev OK)
- [ ] **Timestamp**: __________
- [ ] Ran `sam deploy --parameter-overrides Environment=staging`
- [ ] Stack status: `__________ (UPDATE_COMPLETE expected)`
- [ ] Monitored staging for 30 minutes: ☐ Pass ☐ Fail

### Step 7: Deploy to Production (If Staging OK)
- [ ] **Timestamp**: __________
- [ ] Ran `sam deploy --parameter-overrides Environment=prod`
- [ ] Stack status: `__________ (UPDATE_COMPLETE expected)`

---

## 🐤 Canary Deployment (If Applicable)

**Decision**: ☐ Execute Canary ☐ Skip Canary

**If Canary**:
- [ ] **Start Time**: __________
- [ ] Set canary_percentage: __________ %
- [ ] Monitored canary metrics separately (Dimension: RulesVersion=v_______)

**Gradual Rollout**:
- [ ] **Hour 0-1**: 10% canary - ☐ Pass ☐ Fail
- [ ] **Hour 1-2**: 25% canary - ☐ Pass ☐ Fail
- [ ] **Hour 2-4**: 50% canary - ☐ Pass ☐ Fail
- [ ] **Hour 4+**: 100% rollout - ☐ Pass ☐ Fail

**Canary Metrics**:
- [ ] BCR within ±5% of baseline: Baseline: ____, Canary: ____
- [ ] Kappa within ±5% of baseline: Baseline: ____, Canary: ____
- [ ] OverrideRatio within ±10% of baseline: Baseline: ____, Canary: ____

---

## ⏰ 24-Hour Monitoring

### Hour-by-Hour Checklist

| Hour | Check Time | BCR | Kappa | Override | Alarms | Notes | Status |
|------|------------|-----|-------|----------|--------|-------|--------|
| 0 | __________ | ____ | ____ | ____ | ☐ None | ____ | ☐ Pass |
| 1 | __________ | ____ | ____ | ____ | ☐ None | ____ | ☐ Pass |
| 2 | __________ | ____ | ____ | ____ | ☐ None | ____ | ☐ Pass |
| 4 | __________ | ____ | ____ | ____ | ☐ None | ____ | ☐ Pass |
| 8 | __________ | ____ | ____ | ____ | ☐ None | ____ | ☐ Pass |
| 12 | __________ | ____ | ____ | ____ | ☐ None | ____ | ☐ Pass |
| 24 | __________ | ____ | ____ | ____ | ☐ None | ____ | ☐ Pass |

### Monitoring Script Execution

**Command Used**:
```bash
# Record the exact command you ran
__________
```

**Sample Output**:
```
# Paste sample output here for audit trail
```

### Success Criteria (All Must Be True)
- [ ] No WARN/FAIL alarms triggered in 24 hours
- [ ] BCR > 0.5 for entire period
- [ ] Kappa > 0.3 for entire period
- [ ] Override < 30% for entire period
- [ ] No user-reported issues
- [ ] Lambda error rate < 1%
- [ ] P95 duration within baseline ±20%

---

## 🚨 Incident Log (If Applicable)

**Use this section if any issues occurred during release**

### Incident 1
- **Time**: __________
- **Severity**: ☐ WARN ☐ FAIL ☐ Emergency
- **Description**: __________
- **Root Cause**: __________
- **Action Taken**: ☐ Rollback ☐ Investigate ☐ Escalate
- **Resolution**: __________
- **ADR Created**: ☐ Yes (ADR-_____) ☐ No

### Incident 2
- **Time**: __________
- **Severity**: ☐ WARN ☐ FAIL ☐ Emergency
- **Description**: __________
- **Root Cause**: __________
- **Action Taken**: ☐ Rollback ☐ Investigate ☐ Escalate
- **Resolution**: __________
- **ADR Created**: ☐ Yes (ADR-_____) ☐ No

---

## 🎯 Post-Release Actions

### Immediate (Within 1 Hour of Success)
- [ ] **Timestamp**: __________
- [ ] Update CHANGELOG.md
- [ ] Notify stakeholders (Slack, Email, etc.)
- [ ] Archive monitoring logs to: __________
- [ ] Update Notion release tracker

### Follow-Up (Within 1 Week)
- [ ] Conduct retrospective meeting
  - **Date**: __________
  - **Participants**: __________
  - **Key Learnings**: __________
- [ ] Update ADR with post-release insights
- [ ] Document any runbook improvements needed
- [ ] Schedule next release (if applicable): __________

---

## 📊 Release Summary

**Overall Status**: ☐ Success ☐ Partial Success ☐ Rollback ☐ Cancelled

**Metrics Summary**:
| Metric | Pre-Release Baseline | Post-Release (24hr avg) | Delta | Status |
|--------|---------------------|-------------------------|-------|--------|
| BCR | ____ | ____ | ____ | ☐ Improved ☐ Stable ☐ Degraded |
| Kappa | ____ | ____ | ____ | ☐ Improved ☐ Stable ☐ Degraded |
| Override | ____ | ____ | ____ | ☐ Improved ☐ Stable ☐ Degraded |

**Release Notes** (Concise summary for stakeholders):
```
[Write 2-3 sentences summarizing the release outcome]
```

**Lessons Learned**:
1. __________
2. __________
3. __________

**Action Items for Next Release**:
1. __________
2. __________
3. __________

---

## 🔗 References

- Full Runbook: `docs/runbooks/rules_version_release.md`
- ADR: `docs/adr/0040-ui-monitoring-2-tier-alert-design.md`
- CloudWatch Dashboard: `__________ (URL)`
- Git Commit: `__________ (SHA)`
- Notion Release Page: `__________ (URL)`

---

## ✍️ Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| **Release Owner** | __________ | __________ | __________ |
| **Monitoring Lead** | __________ | __________ | __________ |
| **Rollback Executor** | __________ | __________ | __________ |

**Final Approval**: ☐ Approved ☐ Rejected

**Approver**: __________
**Date**: __________
**Comments**: __________

---

**End of Template**

---

## 📝 Notion Conversion Instructions

To use this template in Notion:

1. **Create a new page** in your Notion workspace
2. **Copy this entire markdown file**
3. **Paste into Notion** - Notion will auto-convert markdown
4. **Convert checkboxes**:
   - In Notion, select all `- [ ]` items
   - Right-click → "Turn into" → "To-do list"
5. **Add database properties** (optional):
   - Status: Select (Not Started, In Progress, Completed)
   - Assignee: Person
   - Due Date: Date
6. **Create a template** in Notion for reuse
7. **Duplicate this template** for each new release

**Notion-Specific Enhancements**:
- Add `/timeline` view for 24-hour monitoring schedule
- Add `/board` view for team task assignment
- Add `/table` view for historical release tracking
- Link to related ADR pages in Notion
