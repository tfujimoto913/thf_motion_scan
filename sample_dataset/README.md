# Dry-run Sample Dataset

Seeded manifests used by the Threshold Editor dry-run workflow.  Each test directory contains:

- `manifest.json` with the random seed and curated rep IDs (max two per athlete/video)
- Optional parquet/CSV payloads under the same directory

The contents are immutable in CI; update manifests via a pull request when refreshing the seed set.
