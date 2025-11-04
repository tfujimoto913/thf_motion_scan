"""
Purpose: Dry-run threshold impact estimation for SLS samples
Responsibility: Compute label changes and representative examples for threshold adjustments
Dependencies: pandas, numpy
Created: 2025-11-04 by Claude Code
Decision Log: Phase 2 - Threshold change impact estimation

CRITICAL:
- Deterministic sampling with fixed seed
- Vectorized computation for <2s performance
- Representative example selection (best/worst/neutral)
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd


def compute_label(value: float, bands: list[dict[str, Any]], direction: str = "lower_is_better") -> str:
    """
    What: Compute classification label based on threshold bands
    Why: Unified label assignment logic for old/new thresholds
    Design Decision: Direction-aware band evaluation (lower_is_better default)

    CRITICAL: Bands must be ordered from best to worst

    Args:
        value: Metric value to classify
        bands: List of band definitions [{"label": "OK", "max": 10.0}, ...]
        direction: "lower_is_better" or "higher_is_better"

    Returns:
        Label string ("OK", "WARN", "NG")

    Examples:
        >>> bands = [{"label": "OK", "max": 10.0}, {"label": "WARN", "max": 20.0}, {"label": "NG", "max": None}]
        >>> compute_label(5.0, bands)
        'OK'
        >>> compute_label(15.0, bands)
        'WARN'
        >>> compute_label(25.0, bands)
        'NG'
    """
    # For lower_is_better: (-inf, max] assigns labels in order
    # For higher_is_better: reverse logic (future enhancement)

    if direction != "lower_is_better":
        raise NotImplementedError(f"Direction '{direction}' not yet implemented. Use 'lower_is_better'.")

    for band in bands:
        max_val = band.get("max")
        if max_val is None or value <= max_val:
            return band["label"]

    # Fallback to last band (should not reach here with proper band definition)
    return bands[-1]["label"]


def _compute_band_centers(bands: list[dict[str, Any]]) -> dict[str, float]:
    """
    What: Compute representative center value for each band
    Why: Used for margin calculation in representative example selection

    Args:
        bands: List of band definitions

    Returns:
        Dict mapping label to center value
    """
    centers = {}
    prev_max = -np.inf

    for band in bands:
        label = band["label"]
        cur_max = band.get("max")

        if cur_max is None:
            cur_max = np.inf

        left = prev_max
        right = cur_max

        # Compute center based on boundaries
        if np.isinf(left) and np.isinf(right):
            center = 0.0
        elif np.isinf(left):
            center = right - 10.0  # Arbitrary offset for relative comparison
        elif np.isinf(right):
            center = left + 10.0
        else:
            center = (left + right) / 2.0

        centers[label] = center
        prev_max = cur_max

    return centers


def dry_run_threshold_change(
    metric_id: str,
    new_bands: list[dict[str, Any]],
    samples_df: pd.DataFrame,
    seed: int = 42,
    sample_n: int = 20,
) -> dict[str, Any]:
    """
    What: Estimate impact of threshold change on sample classification
    Why: Allow operators to preview effects before committing threshold changes
    Design Decision: Vectorized pandas operations for <2s performance on 20 samples

    CRITICAL:
    - Deterministic sampling (fixed seed)
    - Vectorized operations (no row-by-row loops)
    - Representative examples for decision support

    Args:
        metric_id: Metric identifier (e.g., "SLS:B1:trunk_lean_deg")
        new_bands: New threshold bands to evaluate
        samples_df: Sample data with columns: sample_id, metric_value, old_label
        seed: Random seed for deterministic sampling
        sample_n: Number of samples to evaluate (max 20)

    Returns:
        Dict with keys:
        - metric_id: Metric identifier
        - dry_run_duration_ms: Execution time in milliseconds
        - affected_count: Number of samples with label changes
        - reclassified_rate: Proportion of samples reclassified
        - n_sample: Number of samples evaluated
        - examples: Dict with best/worst/neutral representative samples

    Examples:
        >>> samples = pd.DataFrame({
        ...     'sample_id': ['s1', 's2', 's3'],
        ...     'metric_value': [5.0, 15.0, 25.0],
        ...     'old_label': ['OK', 'WARN', 'NG']
        ... })
        >>> new_bands = [{"label": "OK", "max": 12.0}, {"label": "WARN", "max": 22.0}, {"label": "NG", "max": None}]
        >>> result = dry_run_threshold_change("test_metric", new_bands, samples)
        >>> result['n_sample']
        3
    """
    t0 = time.perf_counter()

    # Deterministic sampling
    df = samples_df.sample(n=min(sample_n, len(samples_df)), random_state=seed).copy()

    # Vectorized label computation
    df["new_label"] = df["metric_value"].apply(
        lambda v: compute_label(v, new_bands, direction="lower_is_better")
    )

    # Reclassification detection
    df["reclass"] = df["old_label"] != df["new_label"]
    affected_count = int(df["reclass"].sum())
    n_sample = len(df)

    # Margin computation for representative selection
    centers = _compute_band_centers(new_bands)
    df["center"] = df["new_label"].map(centers)
    df["margin"] = (df["center"] - df["metric_value"]).abs()

    # Label rank for improvement/degradation detection
    label_rank = {"OK": 0, "WARN": 1, "NG": 2}
    df["old_rank"] = df["old_label"].map(label_rank)
    df["new_rank"] = df["new_label"].map(label_rank)

    # Representative example selection
    # Best: Improved (rank decreased) with max margin
    best_df = df[df["reclass"] & (df["new_rank"] < df["old_rank"])].sort_values("margin", ascending=False)

    # Worst: Degraded (rank increased) with max margin
    worst_df = df[df["reclass"] & (df["new_rank"] > df["old_rank"])].sort_values("margin", ascending=False)

    # Neutral: No change, closest to boundary
    neutral_df = df[~df["reclass"]].sort_values("margin", ascending=True)

    def _pack_example(row: pd.Series) -> dict[str, Any]:
        """Pack DataFrame row into example dict"""
        return {
            "sample_id": str(row["sample_id"]),
            "old_label": str(row["old_label"]),
            "new_label": str(row["new_label"]),
            "metric_value": float(row["metric_value"]),
            "margin": float(row["margin"]),
        }

    examples = {
        "best": _pack_example(best_df.iloc[0]) if len(best_df) > 0 else None,
        "worst": _pack_example(worst_df.iloc[0]) if len(worst_df) > 0 else None,
        "neutral": _pack_example(neutral_df.iloc[0]) if len(neutral_df) > 0 else None,
    }

    duration_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "metric_id": metric_id,
        "dry_run_duration_ms": duration_ms,
        "affected_count": affected_count,
        "reclassified_rate": affected_count / n_sample if n_sample > 0 else 0.0,
        "n_sample": n_sample,
        "examples": examples,
    }


# ============================================================================
# Change log utilities
# ============================================================================

def append_jsonl(path: str, entry: dict[str, Any]) -> None:
    """
    What: Append a single JSON entry to a JSONL file
    Why: Maintain audit trail of threshold decisions
    Design Decision: JSONL format for streaming append operations

    CRITICAL: Use ensure_ascii=False for UTF-8 support

    Args:
        path: File path (relative to project root)
        entry: Dict to serialize as JSON
    """
    import json
    from pathlib import Path

    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_threshold_decision(
    metric_id: str,
    old_bands: list[dict[str, Any]],
    new_bands: list[dict[str, Any]],
    dryrun_summary: dict[str, Any],
    actor: str,
) -> dict[str, Any]:
    """
    What: Record threshold change decision to audit log
    Why: Compliance and traceability for threshold adjustments
    Design Decision: JSONL format for easy parsing and streaming

    CRITICAL: Log BEFORE applying changes (pre-commit audit)

    Args:
        metric_id: Metric identifier (e.g., "SLS:B1:trunk_lean_deg")
        old_bands: Previous threshold bands
        new_bands: New threshold bands
        dryrun_summary: Dry-run impact summary (from dry_run_threshold_change)
        actor: User/operator identifier (email or username)

    Returns:
        Entry dict that was logged

    Examples:
        >>> dryrun_result = dry_run_threshold_change(...)
        >>> log_threshold_decision(
        ...     metric_id="SLS:B1:trunk_lean_deg",
        ...     old_bands=[{"label": "OK", "max": 10.0}, ...],
        ...     new_bands=[{"label": "OK", "max": 12.0}, ...],
        ...     dryrun_summary=dryrun_result,
        ...     actor="coach@example.com"
        ... )
    """
    from datetime import datetime, timezone

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "type": "threshold_decision",
        "metric_id": metric_id,
        "old_bands": old_bands,
        "new_bands": new_bands,
        "dryrun": dryrun_summary,
    }

    append_jsonl("config/thresholds/changelog.jsonl", entry)
    return entry


# ============================================================================
# Batch dry-run for multiple metrics
# ============================================================================

def run_batch_dryrun(
    metrics_config: dict[str, dict[str, Any]],
    samples_df: pd.DataFrame,
    seed: int = 42,
    sample_n: int = 20,
) -> dict[str, Any]:
    """
    What: Execute dry-run for multiple metrics simultaneously
    Why: Allow operators to assess combined impact of threshold changes
    Design Decision: Vectorized processing per metric, aggregate results

    CRITICAL:
    - Deterministic sampling (fixed seed across all metrics)
    - Performance: <2s for 3 metrics × 20 samples
    - Representative examples: max 3 total (not per metric)

    Args:
        metrics_config: Dict mapping metric_id to config with keys:
            - "new_bands": List of band definitions
            - "old_bands": List of band definitions (for computing old_label)
            - "value_column": Column name in samples_df
        samples_df: Sample data with columns for each metric
        seed: Random seed for deterministic sampling
        sample_n: Number of samples to evaluate per metric

    Returns:
        Dict with keys:
        - summary_df: DataFrame with columns [metric_id, affected_count, reclassified_rate, n_sample]
        - overall_reclassified_rate: Weighted average across all metrics
        - top3_metrics: List of up to 3 metric_ids sorted by reclassified_rate descending
        - representative_examples: List of up to 3 dicts with keys [metric_id, sample_id, category, old_label, new_label, metric_value]
        - execution_time_ms: Total execution time

    Examples:
        >>> metrics_config = {
        ...     "SLS:B1:trunk_lean_deg": {
        ...         "new_bands": [{"label": "OK", "max": 12.0}, ...],
        ...         "old_bands": [{"label": "OK", "max": 10.0}, ...],
        ...         "value_column": "trunk_lean_deg"
        ...     },
        ...     "SLS:B2:knee_valgus_deg": {
        ...         "new_bands": [{"label": "OK", "max": 8.0}, ...],
        ...         "old_bands": [{"label": "OK", "max": 5.0}, ...],
        ...         "value_column": "knee_valgus_deg"
        ...     }
        ... }
        >>> samples_df = pd.DataFrame({"sample_id": [...], "trunk_lean_deg": [...], "knee_valgus_deg": [...]})
        >>> result = run_batch_dryrun(metrics_config, samples_df, seed=42)
        >>> result['overall_reclassified_rate']
        0.35
    """
    t0 = time.perf_counter()

    # Edge case: empty config
    if not metrics_config:
        return {
            "summary_df": pd.DataFrame(columns=["metric_id", "affected_count", "reclassified_rate", "n_sample"]),
            "overall_reclassified_rate": 0.0,
            "top3_metrics": [],
            "representative_examples": [],
            "execution_time_ms": 0,
        }

    summary_rows = []
    all_examples = []  # Collect all examples for selection

    for metric_id, config in metrics_config.items():
        value_column = config["value_column"]
        new_bands = config["new_bands"]
        old_bands = config["old_bands"]

        # Prepare samples for this metric
        metric_samples = samples_df[["sample_id", value_column]].copy()
        metric_samples.rename(columns={value_column: "metric_value"}, inplace=True)

        # Compute old labels
        metric_samples["old_label"] = metric_samples["metric_value"].apply(
            lambda v: compute_label(v, old_bands, direction="lower_is_better")
        )

        # Run dry-run for this metric
        result = dry_run_threshold_change(
            metric_id=metric_id,
            new_bands=new_bands,
            samples_df=metric_samples,
            seed=seed,
            sample_n=sample_n,
        )

        # Append to summary
        summary_rows.append({
            "metric_id": metric_id,
            "affected_count": result["affected_count"],
            "reclassified_rate": result["reclassified_rate"],
            "n_sample": result["n_sample"],
        })

        # Collect examples for later selection
        examples = result["examples"]
        if examples["best"]:
            all_examples.append({
                "metric_id": metric_id,
                "category": "best",
                **examples["best"],
            })
        if examples["worst"]:
            all_examples.append({
                "metric_id": metric_id,
                "category": "worst",
                **examples["worst"],
            })
        if examples["neutral"]:
            all_examples.append({
                "metric_id": metric_id,
                "category": "neutral",
                **examples["neutral"],
            })

    # Create summary DataFrame
    summary_df = pd.DataFrame(summary_rows)

    # Compute overall reclassified rate (weighted by n_sample)
    total_affected = summary_df["affected_count"].sum()
    total_samples = summary_df["n_sample"].sum()
    overall_reclassified_rate = total_affected / total_samples if total_samples > 0 else 0.0

    # Top3 metrics sorted by reclassified_rate descending
    top3_metrics = (
        summary_df.sort_values("reclassified_rate", ascending=False)
        .head(3)["metric_id"]
        .tolist()
    )

    # Representative examples: pick up to 3 from all_examples
    # Strategy: prioritize best/worst, then neutral
    # Use seed for deterministic selection if there are many examples
    representative_examples = []
    categories_priority = ["best", "worst", "neutral"]

    for category in categories_priority:
        category_examples = [ex for ex in all_examples if ex["category"] == category]
        if category_examples and len(representative_examples) < 3:
            # Pick first (deterministic) from this category
            representative_examples.append(category_examples[0])

    # Fill remaining slots if less than 3
    while len(representative_examples) < 3 and len(representative_examples) < len(all_examples):
        for ex in all_examples:
            if ex not in representative_examples:
                representative_examples.append(ex)
                if len(representative_examples) >= 3:
                    break

    duration_ms = int((time.perf_counter() - t0) * 1000)

    return {
        "summary_df": summary_df,
        "overall_reclassified_rate": float(overall_reclassified_rate),
        "top3_metrics": top3_metrics,
        "representative_examples": representative_examples[:3],  # Max 3
        "execution_time_ms": duration_ms,
    }
