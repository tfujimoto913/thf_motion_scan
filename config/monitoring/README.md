# Monitoring Configuration

**Purpose**: Environment-specific monitoring thresholds and alerting rules  
**Created**: 2025-11-04  
**Decision Log**: ADR-040 (UI Monitoring 2-Tier Alert Design)

---

## 📁 File Structure

```
config/monitoring/
├── README.md        # This file
├── base.yaml        # Base configuration (default thresholds)
├── dev.yaml         # Development overrides
├── stg.yaml         # Staging overrides
└── prod.yaml        # Production overrides
```

---

## 📊 Configuration Schema

### Top-Level Structure

```yaml
version: string            # Config version (e.g., "1.0.0")
environment: string        # dev | stg | prod

billing:
  cost:
    warn_threshold: float  # USD amount for WARN alarm
    fail_threshold: float  # USD amount for FAIL alarm
    period_hours: int      # Evaluation period

ui:
  render_time_ms:
    warn_threshold_p75: int  # P75 milliseconds
    fail_threshold_p90: int  # P90 milliseconds
  
  error_rate:
    warn_threshold_p75: float  # P75 percentage (0.0-1.0)
    fail_threshold_p90: float  # P90 percentage
  
  availability:
    warn_threshold_percent: float  # Uptime percentage
    fail_threshold_percent: float  # Uptime percentage

rollback:
  conditions:
    - condition: string
      threshold: string
      description: string
  max_duration_minutes: int

incident_response:
  primary_response_minutes: int
  resolution_target_minutes: int
  escalation:
    - level: int
      role: string
      timeout_minutes: int
```

### Python Type Definitions

```python
from typing import TypedDict, List

class CostThresholds(TypedDict):
    warn_threshold: float
    fail_threshold: float
    period_hours: int

class UIRenderThresholds(TypedDict):
    warn_threshold_p75: int
    fail_threshold_p90: int

class RollbackCondition(TypedDict):
    condition: str
    threshold: str
    description: str

class MonitoringConfig(TypedDict):
    version: str
    environment: str
    billing: dict  # CostThresholds
    ui: dict       # UIRenderThresholds, etc.
    rollback: dict
    incident_response: dict
```

---

## 🔄 Configuration Merging

**Merge Strategy**: Deep merge (env-specific overrides base)

**Example**:

base.yaml:
```yaml
billing:
  cost:
    warn_threshold: 4.0
    fail_threshold: 5.0
ui:
  render_time_ms:
    warn_threshold_p75: 800
```

prod.yaml (overrides only):
```yaml
billing:
  cost:
    warn_threshold: 16.0  # Override
# ui settings inherited from base.yaml
```

**Result** (prod):
```yaml
billing:
  cost:
    warn_threshold: 16.0   # From prod.yaml
    fail_threshold: 5.0    # From base.yaml
ui:
  render_time_ms:
    warn_threshold_p75: 800  # From base.yaml
```

---

## 🔧 Usage

### Load Configuration

```python
from src.monitoring.config_loader import load_monitoring_config, get_threshold

# Load configuration for current environment (from ENVIRONMENT env var)
config = load_monitoring_config()

# Load configuration for specific environment
config_dev = load_monitoring_config(environment='dev')
config_prod = load_monitoring_config(environment='prod')

# Get specific threshold with fallback
warn_threshold = get_threshold(
    config, 
    'billing.cost.warn_threshold', 
    default=4.0
)
```

### Fallback Behavior

1. **Base config fails** → Return empty dict `{}`
2. **Env config fails** → Use base config only
3. **Merge fails** → Use base config only

All errors are logged but don't crash the system.

---

## 📝 Change Management

### Change Workflow

**1. Create Feature Branch**
```bash
git checkout -b config/update-prod-thresholds
```

**2. Edit Environment-Specific File**
```bash
# Edit only the environment you want to change
vim config/monitoring/prod.yaml
```

**3. Create Pull Request**

**Required in PR Description:**
- **What**: Which thresholds changed
- **Why**: Business/technical justification
- **Impact**: Expected alarm behavior changes
- **Rollback**: How to revert if needed

**Example PR Description:**
```markdown
## Monitoring Config Update: Production Billing Threshold

**What Changed:**
- `prod.yaml`: billing.cost.warn_threshold: 16.0 → 18.0
- `prod.yaml`: billing.cost.fail_threshold: 20.0 → 22.0

**Why:**
- Baseline monthly cost increased to $17 due to new features
- Current thresholds cause false alarms

**Impact:**
- Billing WARN alarm will trigger at $18 instead of $16
- Billing FAIL alarm will trigger at $22 instead of $20

**Baseline Measurement:**
- P95 monthly cost over last 3 months: $17.20
- Proposed WARN at $18 = 82% buffer
- Proposed FAIL at $22 = 100% budget

**Rollback:**
- Revert this commit
- Redeploy with previous config
```

**4. Review Checklist**

Reviewer must verify:
- [ ] Changes are in correct env file (dev/stg/prod)
- [ ] Justification provided
- [ ] Baseline data included
- [ ] Rollback plan documented
- [ ] No breaking changes to schema
- [ ] YAML syntax valid

**5. Deploy**
```bash
git merge config/update-prod-thresholds
git push origin main
# Config auto-loaded on next Lambda invocation
```

---

## ⚠️ Rollback Procedures

### Option 1: Revert Commit
```bash
git revert <commit-hash>
git push origin main
```

### Option 2: Manual Override (Emergency)
```bash
# Edit production file directly
vim config/monitoring/prod.yaml

# Commit and push
git add config/monitoring/prod.yaml
git commit -m "emergency: revert prod billing thresholds"
git push origin main
```

### Option 3: Fallback to Base
```bash
# Temporarily delete env-specific file to use base.yaml only
mv config/monitoring/prod.yaml config/monitoring/prod.yaml.disabled
git commit -am "emergency: disable prod overrides, use base config"
git push origin main
```

---

## 🧪 Testing

### Manual Testing

```python
# Test config loading
from src.monitoring.config_loader import load_monitoring_config

config = load_monitoring_config('dev')
print(f"Dev billing WARN: ${config['billing']['cost']['warn_threshold']}")

config = load_monitoring_config('prod')
print(f"Prod billing WARN: ${config['billing']['cost']['warn_threshold']}")
```

### Validation

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('config/monitoring/dev.yaml'))"
python -c "import yaml; yaml.safe_load(open('config/monitoring/stg.yaml'))"
python -c "import yaml; yaml.safe_load(open('config/monitoring/prod.yaml'))"
```

---

## 🔍 Troubleshooting

### Config Not Loading

**Symptom**: System uses unexpected thresholds

**Check**:
1. Verify `ENVIRONMENT` env var is set correctly
   ```bash
   echo $ENVIRONMENT  # Should be dev/stg/prod
   ```

2. Check file permissions
   ```bash
   ls -la config/monitoring/
   ```

3. Check logs
   ```bash
   grep "monitoring config" logs/application.log
   ```

### Merge Conflicts

**Symptom**: Multiple PRs editing same config

**Resolution**:
1. Coordinate with team (announce in Slack)
2. Merge PRs sequentially
3. Test each merge before proceeding

---

## 📚 Related Documentation

- **ADR-040**: UI Monitoring 2-Tier Alert Design
- **Runbook**: `docs/runbooks/ui_monitoring.md`
- **Billing Runbook**: `docs/runbooks/billing_emergency_stop.md`
- **Code**: `src/monitoring/config_loader.py`

---

## 📊 Environment Comparison

| Threshold | dev | stg | prod |
|-----------|-----|-----|------|
| Billing WARN | $4 | $8 | $16 |
| Billing FAIL | $5 | $10 | $20 |
| UI Render WARN (P75) | 1000ms | 800ms | 600ms |
| UI Render FAIL (P90) | 1500ms | 1200ms | 1000ms |
| Response Time | 10min | 5min | 3min |

---

**Version**: 1.0.0  
**Last Updated**: 2025-11-04  
**Maintainer**: Ops Team
