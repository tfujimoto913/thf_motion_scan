"""
Purpose: Convert SLS sample data to dry-run input format
Responsibility: Transform various input formats to standard DataFrame schema
Dependencies: pandas
Created: 2025-11-04 by Claude Code
Decision Log: Phase 2 - Threshold dry-run sample preparation

CRITICAL:
- Preserve sample_id for traceability
- Handle missing/NaN values appropriately
- Output format must match dry_run_threshold_change() contract
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

# Add project root to path for CLI execution
if __name__ == "__main__":
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


def convert_rep_results_to_samples(
    rep_results: list[dict[str, Any]],
    metric_id: str,
    old_bands: list[dict[str, Any]],
) -> pd.DataFrame:
    """
    What: Convert rep_result JSON records to dry-run sample format
    Why: Enable dry-run on existing rep_result data
    Design Decision: Extract metric_value from nested structure

    CRITICAL: Metric ID must match rep_result structure (test:metric path)

    Args:
        rep_results: List of rep_result dicts (from processing pipeline)
        metric_id: Metric identifier (e.g., "SLS:B1:trunk_lean_deg")
        old_bands: Current threshold bands (for computing old_label)

    Returns:
        DataFrame with columns: sample_id, metric_value, old_label

    Examples:
        >>> rep_results = [
        ...     {"rep_id": "rep_001", "test": "SLS", "metrics": {"B1": {"trunk_lean_deg": 8.5}}},
        ...     {"rep_id": "rep_002", "test": "SLS", "metrics": {"B1": {"trunk_lean_deg": 15.2}}},
        ... ]
        >>> old_bands = [{"label": "OK", "max": 10.0}, {"label": "WARN", "max": 20.0}, {"label": "NG", "max": None}]
        >>> df = convert_rep_results_to_samples(rep_results, "SLS:B1:trunk_lean_deg", old_bands)
        >>> df.shape[0]
        2
    """
    from tools.threshold_dryrun import compute_label

    # Parse metric_id (format: "TEST:METRIC_GROUP:METRIC_NAME")
    parts = metric_id.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid metric_id format: {metric_id}. Expected 'TEST:GROUP:METRIC'")

    test_code, group, metric_name = parts

    samples = []

    for rep in rep_results:
        # Skip if wrong test
        if rep.get("test") != test_code:
            continue

        rep_id = rep.get("rep_id", "unknown")

        # Navigate nested structure: rep["metrics"][group][metric_name]
        metrics = rep.get("metrics", {})
        if group not in metrics:
            continue

        metric_group = metrics[group]
        if metric_name not in metric_group:
            continue

        metric_value = metric_group[metric_name]

        # Compute old label
        old_label = compute_label(metric_value, old_bands, direction="lower_is_better")

        samples.append({
            "sample_id": rep_id,
            "metric_value": float(metric_value),
            "old_label": old_label,
        })

    return pd.DataFrame(samples)


def convert_csv_to_samples(
    csv_path: str | Path,
    sample_id_col: str = "sample_id",
    metric_value_col: str = "metric_value",
    old_label_col: str = "old_label",
) -> pd.DataFrame:
    """
    What: Load samples from CSV file
    Why: Support external data sources (e.g., exported from dashboard)
    Design Decision: Flexible column mapping for various CSV formats

    Args:
        csv_path: Path to CSV file
        sample_id_col: Column name for sample IDs
        metric_value_col: Column name for metric values
        old_label_col: Column name for old labels

    Returns:
        DataFrame with standard schema: sample_id, metric_value, old_label

    Examples:
        >>> # CSV with columns: rep_id, trunk_lean, current_label
        >>> df = convert_csv_to_samples(
        ...     "data/sls_samples.csv",
        ...     sample_id_col="rep_id",
        ...     metric_value_col="trunk_lean",
        ...     old_label_col="current_label"
        ... )
    """
    df = pd.read_csv(csv_path)

    # Validate required columns
    required = {sample_id_col, metric_value_col, old_label_col}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    # Rename to standard schema
    renamed = df.rename(columns={
        sample_id_col: "sample_id",
        metric_value_col: "metric_value",
        old_label_col: "old_label",
    })

    # Select only required columns (drop extras)
    return renamed[["sample_id", "metric_value", "old_label"]].copy()


def generate_synthetic_samples(
    n_samples: int = 20,
    metric_id: str = "SLS:B1:trunk_lean_deg",
    old_bands: list[dict[str, Any]] | None = None,
    seed: int = 42,
) -> pd.DataFrame:
    """
    What: Generate synthetic sample data for testing
    Why: Enable dry-run testing without real data
    Design Decision: Gaussian distribution centered on band boundaries

    CRITICAL: Only for testing/demo purposes, not production

    Args:
        n_samples: Number of samples to generate
        metric_id: Metric identifier (used for sample naming)
        old_bands: Threshold bands (defaults to standard OK/WARN/NG)
        seed: Random seed for reproducibility

    Returns:
        DataFrame with synthetic samples

    Examples:
        >>> df = generate_synthetic_samples(n_samples=15, seed=42)
        >>> df.shape[0]
        15
        >>> set(df["old_label"].unique()) <= {"OK", "WARN", "NG"}
        True
    """
    import numpy as np
    from tools.threshold_dryrun import compute_label

    np.random.seed(seed)

    if old_bands is None:
        old_bands = [
            {"label": "OK", "max": 10.0},
            {"label": "WARN", "max": 20.0},
            {"label": "NG", "max": None},
        ]

    # Generate values across all bands (centered on boundaries)
    # Distribution: 40% near OK/WARN boundary, 40% near WARN/NG boundary, 20% extremes
    ok_boundary = old_bands[0]["max"]
    warn_boundary = old_bands[1]["max"]

    n_ok = int(n_samples * 0.4)
    n_warn = int(n_samples * 0.4)
    n_ng = n_samples - n_ok - n_warn

    values = np.concatenate([
        np.random.normal(ok_boundary, 2.0, n_ok),      # Around OK/WARN boundary
        np.random.normal(warn_boundary, 2.0, n_warn),  # Around WARN/NG boundary
        np.random.uniform(warn_boundary + 5, warn_boundary + 15, n_ng),  # NG range
    ])

    # Shuffle and clip to positive values
    np.random.shuffle(values)
    values = np.clip(values, 0.1, None)  # Minimum 0.1 (avoid zero/negative)

    samples = []
    for i, value in enumerate(values):
        old_label = compute_label(value, old_bands, direction="lower_is_better")
        samples.append({
            "sample_id": f"synthetic_{i:03d}",
            "metric_value": float(value),
            "old_label": old_label,
        })

    return pd.DataFrame(samples)


def save_samples_to_csv(df: pd.DataFrame, output_path: str | Path) -> None:
    """
    What: Save sample DataFrame to CSV
    Why: Export samples for sharing/archiving
    Design Decision: Standard CSV with UTF-8 encoding

    Args:
        df: Sample DataFrame
        output_path: Output CSV path
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False, encoding="utf-8")
    print(f"Saved {len(df)} samples to {output}")


# ============================================================================
# CLI interface (optional)
# ============================================================================

def main():
    """
    What: CLI for sample data conversion
    Why: Quick ad-hoc conversions without writing code

    Usage:
        # Generate synthetic samples
        python tools/convert_sls_samples.py --generate --output sample_dataset/sls_samples.csv

        # Convert rep results
        python tools/convert_sls_samples.py --rep-results test_reps.json --metric SLS:B1:trunk_lean_deg
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Convert SLS samples to dry-run format")
    parser.add_argument("--generate", action="store_true", help="Generate synthetic samples")
    parser.add_argument("--rep-results", type=str, help="Path to rep_results JSON file")
    parser.add_argument("--csv", type=str, help="Path to CSV file")
    parser.add_argument("--metric", type=str, default="SLS:B1:trunk_lean_deg", help="Metric ID")
    parser.add_argument("--output", type=str, required=True, help="Output CSV path")
    parser.add_argument("--n-samples", type=int, default=20, help="Number of synthetic samples")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    old_bands = [
        {"label": "OK", "max": 10.0},
        {"label": "WARN", "max": 20.0},
        {"label": "NG", "max": None},
    ]

    if args.generate:
        print(f"Generating {args.n_samples} synthetic samples...")
        df = generate_synthetic_samples(
            n_samples=args.n_samples,
            metric_id=args.metric,
            old_bands=old_bands,
            seed=args.seed,
        )

    elif args.rep_results:
        print(f"Loading rep results from {args.rep_results}...")
        with open(args.rep_results, "r", encoding="utf-8") as f:
            rep_results = json.load(f)

        if not isinstance(rep_results, list):
            rep_results = [rep_results]

        df = convert_rep_results_to_samples(rep_results, args.metric, old_bands)

    elif args.csv:
        print(f"Loading CSV from {args.csv}...")
        df = convert_csv_to_samples(args.csv)

    else:
        parser.error("Must specify one of: --generate, --rep-results, --csv")

    print(f"\nConverted {len(df)} samples")
    print(f"Label distribution:")
    print(df["old_label"].value_counts().to_dict())

    save_samples_to_csv(df, args.output)


if __name__ == "__main__":
    main()
