"""
Purpose: Validate sigma_probe tooling on synthetic dataset.
"""
from __future__ import annotations

import csv
from pathlib import Path

from tools.sigma_probe import SigmaConfig, run_sigma_probe


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sigma"


def _load_summary(summary_path: Path) -> str:
    return summary_path.read_text(encoding="utf-8")


def test_sigma_probe_end_to_end(tmp_path):
    cfg = SigmaConfig(
        rep_results=[FIXTURE_DIR / "rep_results.jsonl"],
        metadata_path=FIXTURE_DIR / "metadata.csv",
        output_dir=tmp_path,
        artifact_sha="demo-sha",
        generated_at="2025-11-05T00:00:00Z",
    )

    outputs = run_sigma_probe(cfg)

    assert outputs["sigma_table"].exists()
    assert outputs["std_heatmap"].exists()
    assert outputs["bcr_heatmap"].exists()
    assert outputs["summary"].exists()

    with outputs["sigma_table"].open("r", encoding="utf-8") as handle:
        reader = list(csv.DictReader(handle))
    assert len(reader) == 9

    far_high_row = next(
        (row for row in reader if row["distance"] == "far" and row["resolution"] == "high"),
        None,
    )
    assert far_high_row is not None
    assert float(far_high_row["bcr"]) > 0.12

    summary = _load_summary(outputs["summary"])
    assert "Sigma Summary" in summary
    assert "far/high/low" in summary  # caution list
    assert "Generated at: `2025-11-05T00:00:00Z`" in summary
