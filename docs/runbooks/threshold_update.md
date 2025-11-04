# Threshold Update Runbook

**Purpose**: Emergency procedures and troubleshooting guide for threshold configuration changes
**Audience**: Operations team, DevOps engineers, System administrators
**Last Updated**: 2025-11-04
**Owner**: Motion Scan Team

---

## Table of Contents
1. [Emergency Procedures](#emergency-procedures)
2. [Standard Update Workflow](#standard-update-workflow)
3. [Troubleshooting](#troubleshooting)
4. [Rollback Procedures](#rollback-procedures)
5. [Monitoring & Verification](#monitoring--verification)
6. [FAQ](#faq)

---

## Emergency Procedures

### 🚨 Immediate Actions (< 5 minutes)

#### Scenario 1: False Positive Rate Spike
**Symptoms**: Sudden increase in WARN/NG classifications

**Actions**:
1. **Verify Current Thresholds**:
   ```bash
   cat config/thresholds_v2.json | jq '.tests[] | {code, direction}'
   ```

2. **Check Recent Changes**:
   ```bash
   tail -5 config/thresholds/changelog.jsonl | jq .
   ```

3. **Run Emergency Dry-run**:
   ```bash
   cd dashboard
   streamlit run app.py
   # Navigate to "Threshold Editor" > "Batch Dry-run"
   # Use production sample data (last 48h)
   ```

4. **Decide**:
   - **Rollback**: If impact > 30% reclassification → proceed to [Rollback](#rollback-procedures)
   - **Monitor**: If 10-30% → verify with P90/P75 auto-calculation
   - **Proceed**: If < 10% → continue monitoring

#### Scenario 2: Direction Field Misconfiguration
**Symptoms**: Inverted judgments (good values marked as NG)

**Actions**:
1. **Validate Direction-Op Consistency**:
   ```bash
   python tools/validate_direction_consistency.py config/thresholds_v2.json
   ```

2. **If Inconsistencies Found**:
   - Run migration script:
     ```bash
     python tools/migrate_add_direction.py --dry-run config/thresholds_v2.json
     python tools/migrate_add_direction.py config/thresholds_v2.json
     ```

3. **Verify Fix**:
   ```bash
   python tools/validate_direction_consistency.py config/thresholds_v2.json
   # Expected: ✅ OK: X tests, ❌ Inconsistent: 0 tests
   ```

---

## Standard Update Workflow

### Phase 1: Investigation (30-60 min)

1. **Gather Sample Data** (last 7 days):
   ```bash
   # Export from DynamoDB or S3
   aws s3 cp s3://thf-motion-scan-data/samples/latest.csv ./samples.csv
   ```

2. **Run Batch Dry-run**:
   - Upload samples to Streamlit UI
   - Configure P90/P75 auto-calculation
   - Review overall reclassified rate

3. **Generate Report**:
   ```python
   from tools.generate_dryrun_report import generate_report_file
   report_path = generate_report_file(result, Path("results/dryrun_reports"))
   ```

4. **Review with Team**:
   - Share Markdown report
   - Discuss Top 3 metrics impact
   - Approve threshold changes

### Phase 2: Apply Changes (15-30 min)

1. **Backup Current Config**:
   ```bash
   cp config/thresholds_v2.json config/thresholds_v2.backup_$(date +%Y%m%d_%H%M%S).json
   ```

2. **Update Configuration**:
   - Edit `config/thresholds_v2.json`
   - Update `direction` field if needed
   - Increment `thresholds_version`

3. **Validate**:
   ```bash
   python tools/validate_direction_consistency.py config/thresholds_v2.json
   ```

4. **Commit**:
   ```bash
   git add config/thresholds_v2.json
   git commit -m "chore(config): update thresholds - <reason>"
   git push
   ```

### Phase 3: Deploy & Monitor (1-2 hours)

1. **Deploy to Staging**:
   ```bash
   sam build && sam deploy --config-env staging
   ```

2. **Smoke Test** (5 test samples):
   ```bash
   # Verify classification results match expectations
   ```

3. **Deploy to Production**:
   ```bash
   sam deploy --config-env production
   ```

4. **Monitor** (first 2 hours):
   - CloudWatch metrics: `ClassificationRate`, `Latency`
   - Alert threshold: > 20% deviation from baseline

---

## Troubleshooting

### Issue 1: Report Generation Fails

**Error**: `ModuleNotFoundError: No module named 'tools.generate_dryrun_report'`

**Solution**:
```bash
# Ensure tools directory is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python -c "from tools.generate_dryrun_report import generate_report_file"
```

**Error**: `KeyError: 'direction'`

**Solution**:
```bash
# Run direction migration
python tools/migrate_add_direction.py config/thresholds_v2.json
```

### Issue 2: P90/P75 Calculation Error

**Error**: `ValueError: Invalid direction 'invalid'`

**Solution**:
- Check metric config: `direction` must be "lower" or "higher"
- Fix in metrics_config JSON input

**Error**: `KeyError: 'nonexistent_column'`

**Solution**:
- Verify sample data columns match `value_column` in config
- Check CSV headers: `sample_id`, `<metric_columns>`

### Issue 3: Changelog Record Failure

**Error**: Permission denied writing to `changelog.jsonl`

**Solution**:
```bash
# Check file permissions
ls -la config/thresholds/changelog.jsonl

# Fix permissions
chmod 644 config/thresholds/changelog.jsonl
```

---

## Rollback Procedures

### Quick Rollback (< 2 minutes)

1. **Identify Last Good Config**:
   ```bash
   ls -lt config/*.backup_* | head -1
   ```

2. **Restore**:
   ```bash
   cp config/thresholds_v2.backup_20251104_120000.json config/thresholds_v2.json
   ```

3. **Validate**:
   ```bash
   python tools/validate_direction_consistency.py config/thresholds_v2.json
   ```

4. **Deploy**:
   ```bash
   sam deploy --config-env production
   ```

### Git-based Rollback (< 5 minutes)

1. **Find Last Good Commit**:
   ```bash
   git log --oneline -- config/thresholds_v2.json | head -5
   ```

2. **Revert**:
   ```bash
   git revert <commit-hash>
   git push
   ```

3. **Deploy**:
   ```bash
   sam deploy --config-env production
   ```

---

## Monitoring & Verification

### Key Metrics

| Metric | Normal Range | Alert Threshold |
|--------|--------------|-----------------|
| Overall Reclassification Rate | < 15% | > 30% |
| P90 Classification Time | < 50ms | > 100ms |
| False Positive Rate | < 5% | > 10% |

### Verification Checklist

After any threshold change:

- [ ] Dry-run report generated
- [ ] Overall reclassified rate < 30%
- [ ] Direction-op consistency validated (0 inconsistencies)
- [ ] Backup created
- [ ] Changelog updated
- [ ] Staging deployment successful
- [ ] Smoke tests passed (5 samples)
- [ ] Production deployment successful
- [ ] Monitored for 2 hours post-deployment

---

## FAQ

**Q: How often should thresholds be updated?**
A: Every 2-4 weeks based on sample distribution changes. Run monthly dry-runs to detect drift.

**Q: What's the difference between "lower" and "higher" direction?**
A:
- `direction="lower"`: Lower values are better (e.g., pelvis_drop_deg, trunk_lean_deg)
- `direction="higher"`: Higher values are better (e.g., balance_score, stability_score)

**Q: Can I manually edit thresholds.json?**
A: Yes, but always:
1. Run dry-run first
2. Validate with `validate_direction_consistency.py`
3. Create backup before editing

**Q: What if P90/P75 auto-calculation gives unreasonable values?**
A: Review sample data quality. P90/P75 assumes normal distribution. For skewed data, use manual thresholds.

**Q: How do I know if direction is correct?**
A: Check test definition:
- If "lower value = better performance" → `direction="lower"`
- If "higher value = better performance" → `direction="higher"`
- Run validation script to verify consistency

---

## Contact & Escalation

**Primary**: Motion Scan Team Slack (#motion-scan-ops)
**Secondary**: On-call Engineer (PagerDuty)
**Escalation**: Engineering Manager

**Related Runbooks**:
- [Billing Emergency Stop](./billing_emergency_stop.md)
- [DLQ Redrive](./dlq_redrive.md)
- [UI Monitoring](./ui_monitoring.md)
