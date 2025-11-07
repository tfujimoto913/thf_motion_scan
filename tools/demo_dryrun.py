"""
Purpose: Demonstration script for threshold dry-run
Responsibility: End-to-end example of dry-run workflow
Dependencies: pandas, tools.threshold_dryrun
Created: 2025-11-04 by Claude Code

Usage:
    python tools/demo_dryrun.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pandas as pd
from tools.threshold_dryrun import dry_run_threshold_change, log_threshold_decision


def main():
    print("=" * 60)
    print("Threshold Dry-Run Demonstration")
    print("=" * 60)

    # Load sample data
    sample_path = "sample_dataset/sls_samples_demo.csv"
    if not Path(sample_path).exists():
        print(f"\nError: {sample_path} not found.")
        print("Run the following command first:")
        print("  python tools/convert_sls_samples.py --generate --output sample_dataset/sls_samples_demo.csv --n-samples 20")
        return 1

    samples_df = pd.read_csv(sample_path)
    print(f"\nLoaded {len(samples_df)} samples from {sample_path}")
    print(f"Label distribution: {samples_df['old_label'].value_counts().to_dict()}")

    # Current thresholds (baseline)
    old_bands = [
        {"label": "OK", "max": 10.0},
        {"label": "WARN", "max": 20.0},
        {"label": "NG", "max": None},
    ]
    print(f"\nCurrent thresholds: OK ≤{old_bands[0]['max']}°, WARN ≤{old_bands[1]['max']}°, NG >{old_bands[1]['max']}°")

    # Proposed new thresholds (relaxed)
    new_bands = [
        {"label": "OK", "max": 12.0},
        {"label": "WARN", "max": 22.0},
        {"label": "NG", "max": None},
    ]
    print(f"Proposed thresholds: OK ≤{new_bands[0]['max']}°, WARN ≤{new_bands[1]['max']}°, NG >{new_bands[1]['max']}°")

    # Run dry-run
    print("\n" + "-" * 60)
    print("Running dry-run...")
    print("-" * 60)

    result = dry_run_threshold_change(
        metric_id="SLS:B1:trunk_lean_deg",
        new_bands=new_bands,
        samples_df=samples_df,
        seed=42,
        sample_n=20,
    )

    # Display results
    print(f"\n✅ Dry-run completed in {result['dry_run_duration_ms']}ms")
    print(f"\n📊 Impact Summary:")
    print(f"   - Samples evaluated: {result['n_sample']}")
    print(f"   - Reclassified: {result['affected_count']} ({result['reclassified_rate']:.1%})")

    # Representative examples
    print(f"\n🔍 Representative Examples:")

    if result["examples"]["best"]:
        best = result["examples"]["best"]
        print(f"   ✨ Best (Improvement):")
        print(f"      ID: {best['sample_id']}")
        print(f"      Change: {best['old_label']} → {best['new_label']}")
        print(f"      Value: {best['metric_value']:.1f}°")
        print(f"      Margin: {best['margin']:.1f}")

    if result["examples"]["worst"]:
        worst = result["examples"]["worst"]
        print(f"   ⚠️  Worst (Degradation):")
        print(f"      ID: {worst['sample_id']}")
        print(f"      Change: {worst['old_label']} → {worst['new_label']}")
        print(f"      Value: {worst['metric_value']:.1f}°")
        print(f"      Margin: {worst['margin']:.1f}")

    if result["examples"]["neutral"]:
        neutral = result["examples"]["neutral"]
        print(f"   📍 Neutral (No Change, Near Boundary):")
        print(f"      ID: {neutral['sample_id']}")
        print(f"      Label: {neutral['old_label']} (unchanged)")
        print(f"      Value: {neutral['metric_value']:.1f}°")
        print(f"      Margin: {neutral['margin']:.1f}")

    # Decision simulation
    print(f"\n" + "-" * 60)
    print("Decision Simulation")
    print("-" * 60)

    # Simulate approval
    approve = input("\nApprove this threshold change? (yes/no): ").strip().lower()

    if approve == "yes":
        print("\n✅ Change approved. Logging decision...")

        # Log decision
        entry = log_threshold_decision(
            metric_id="SLS:B1:trunk_lean_deg",
            old_bands=old_bands,
            new_bands=new_bands,
            dryrun_summary=result,
            actor="demo_user@example.com",
        )

        print(f"   - Logged to: config/thresholds/changelog.jsonl")
        print(f"   - Timestamp: {entry['ts']}")
        print(f"   - Actor: {entry['actor']}")

        print("\n📝 Next steps:")
        print("   1. Update config/thresholds.json with new bands")
        print("   2. Deploy updated thresholds to production")
        print("   3. Monitor impact on session results")

    else:
        print("\n❌ Change rejected.")
        print("   - No changes made")
        print("   - Try adjusting thresholds and re-running dry-run")

    print("\n" + "=" * 60)
    print("Demonstration complete")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
