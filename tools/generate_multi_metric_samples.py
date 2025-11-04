"""
Purpose: Generate multi-metric sample data for batch dry-run testing
Responsibility: Create CSV with multiple metric columns
Dependencies: pandas, numpy
Created: 2025-11-04 by Claude Code

Usage:
    python tools/generate_multi_metric_samples.py --output sample_dataset/multi_metric_samples.csv --n-samples 20
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd


def generate_multi_metric_samples(n_samples: int = 20, seed: int = 42) -> pd.DataFrame:
    """
    What: Generate sample data with multiple metrics
    Why: Enable batch dry-run testing without real data
    Design Decision: Realistic value ranges for SLS metrics

    Args:
        n_samples: Number of samples to generate
        seed: Random seed for reproducibility

    Returns:
        DataFrame with columns: sample_id, trunk_lean_deg, knee_valgus_deg, balance_score
    """
    np.random.seed(seed)

    # Generate sample IDs
    sample_ids = [f"sample_{i:03d}" for i in range(n_samples)]

    # Metric 1: trunk_lean_deg (5-25 deg, lower is better)
    trunk_lean_deg = np.random.uniform(5, 25, n_samples)

    # Metric 2: knee_valgus_deg (0-15 deg, lower is better)
    knee_valgus_deg = np.random.uniform(0, 15, n_samples)

    # Metric 3: balance_score (50-100, higher is better - for future)
    balance_score = np.random.uniform(50, 100, n_samples)

    df = pd.DataFrame({
        "sample_id": sample_ids,
        "trunk_lean_deg": trunk_lean_deg,
        "knee_valgus_deg": knee_valgus_deg,
        "balance_score": balance_score,
    })

    return df


def main():
    parser = argparse.ArgumentParser(description="Generate multi-metric sample data")
    parser.add_argument("--output", type=str, required=True, help="Output CSV path")
    parser.add_argument("--n-samples", type=int, default=20, help="Number of samples")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    print(f"Generating {args.n_samples} multi-metric samples...")

    df = generate_multi_metric_samples(n_samples=args.n_samples, seed=args.seed)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"✅ Saved {len(df)} samples to {output_path}")
    print(f"\nSample preview:")
    print(df.head())


if __name__ == "__main__":
    main()
