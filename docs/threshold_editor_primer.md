# Threshold Editor Primer

This note captures the seven pre-flight decisions that keep the upcoming Threshold Editor implementation consistent and auditable.

## 1. Terminology

- **reclassified_rate** – `(number of reps whose band changed) ÷ (total evaluated reps)`  
- **impact_count** – raw count of reclassified reps.  
- **representatives** – upshift / downshift lists (max three each) ordered by absolute score delta.

The diff reporter now emits `reclassified_rate`, `impact_count`, and representative samples to match these definitions.

## 2. Band Notation

Three-tier half-open bands only:

```
OK    : [min, t1)
ATTN  : [t1, t2)
NG    : [t2, max]
```

Values are stored internally in SI units; the UI is responsible for user-friendly conversions (°, cm, %height).

## 3. Leading Indicator

SLS uses B4 `pelvis_drop_deg` as the primary early warning metric.  
Metrics are side-aware: use keys such as `SLS.B4.pelvis_drop_deg.left`.

## 4. Dry-run Dataset

Dry run samples are fixed (seeded) per test, 10–20 reps per panel:

- Mix the latest week + varied historical cases.  
- Max two reps per athlete/video to avoid clustering.  
- Store the manifest under `sample_dataset/<test>/manifest.json`.

## 5. Dev Apply Safeguards

Two gates before mutating thresholds:

1. Environment check – only `ENV=dev` allows the Apply button.  
2. Confirmation gate – preview first, then require typing `APPLY` to execute.

## 6. Change Log Schema (minimum viable structure)

```json
{
  "id": "chg_2025-11-04T03:12:09Z",
  "actor": "taka",
  "env": "dev",
  "test": "SLS",
  "metric": "B4.pelvis_drop_deg.left",
  "prev": {"ok": [0, 8], "attn": [8, 15], "ng": [15, 90]},
  "next": {"ok": [0, 10], "attn": [10, 18], "ng": [18, 90]},
  "reclassified_rate": 0.27,
  "reclassified_count": 11,
  "sample_n": 41,
  "representatives": {
    "upshift": ["rep_id_1", "rep_id_2", "rep_id_3"],
    "downshift": ["rep_id_4", "rep_id_5", "rep_id_6"]
  },
  "versions": {
    "thresholds_json": "2.0.1",
    "scoring_engine": "1.6.3",
    "dashboard": "2.1.0"
  },
  "timestamp": "2025-11-04T03:12:09Z"
}
```

## 7. Rollback

- Single-level undo: keep only the most recent snapshot.  
- Snapshots live under `config/thresholds/thresholds-<ISO8601>.json`.  
- Undo restores the latest snapshot wholesale (file granularity).
