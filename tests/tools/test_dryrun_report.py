"""
Purpose: Test suite for dry-run report generation (PR#4)
Responsibility: Verify Markdown report output and changelog integration
Dependencies: pytest, pandas
Created: 2025-11-04 by Claude Code
Decision Log: PR#4 - MVP completion pack

CRITICAL:
- Report format validation (Markdown structure)
- Changelog auto-recording on report generation
- Timestamp and file naming consistency
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from tools.generate_dryrun_report import (
    format_dryrun_report,
    generate_report_file,
    record_to_changelog,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_batch_result():
    """
    What: Sample batch dry-run result for report testing
    Why: Reusable test data matching run_batch_dryrun() output
    """
    return {
        "summary_df": pd.DataFrame({
            "metric_id": ["M1_trunk_lean", "M2_knee_valgus", "M3_balance"],
            "direction": ["lower", "lower", "higher"],
            "affected_count": [5, 3, 2],
            "reclassified_rate": [0.25, 0.15, 0.10],
            "n_sample": [20, 20, 20],
        }),
        "overall_reclassified_rate": 0.187,
        "top3_metrics": ["M1_trunk_lean", "M2_knee_valgus", "M3_balance"],
        "representative_examples": [
            {
                "category": "best",
                "metric_id": "M1_trunk_lean",
                "sample_id": "sample_001",
                "old_label": "WARN",
                "new_label": "OK",
                "metric_value": 8.5,
            },
            {
                "category": "worst",
                "metric_id": "M2_knee_valgus",
                "sample_id": "sample_002",
                "old_label": "OK",
                "new_label": "WARN",
                "metric_value": 11.2,
            },
        ],
        "execution_time_ms": 1200,
        "direction_summary": {
            "lower_count": 2,
            "higher_count": 1,
            "unspecified_count": 0,
        },
    }


# ============================================================================
# Test: Markdown Report Formatting
# ============================================================================

def test_format_dryrun_report_structure(sample_batch_result):
    """
    What: Verify Markdown report contains required sections
    Why: Ensure report completeness for manual review

    CRITICAL: Must include all MVP sections
    """
    report_md = format_dryrun_report(sample_batch_result)

    # Verify required sections
    assert "# Threshold Dry-run Report" in report_md
    assert "## Overall Impact" in report_md
    assert "## Summary by Metric" in report_md
    assert "## Top 3 Metrics (Highest Impact)" in report_md
    assert "## Representative Examples" in report_md
    assert "## Direction Summary" in report_md

    # Verify overall metrics
    assert "18.7%" in report_md  # overall_reclassified_rate
    assert "1200ms" in report_md or "1.2s" in report_md  # execution_time

    # Verify Top 3 listing
    assert "M1_trunk_lean" in report_md
    assert "M2_knee_valgus" in report_md
    assert "M3_balance" in report_md


def test_format_dryrun_report_markdown_table(sample_batch_result):
    """
    What: Verify summary table is valid Markdown
    Why: Ensure report renders correctly in Markdown viewers
    """
    report_md = format_dryrun_report(sample_batch_result)

    # Verify Markdown table syntax
    assert "|" in report_md  # Table delimiter
    assert "Metric" in report_md
    assert "Direction" in report_md
    assert "Reclassified" in report_md

    # Verify data rows
    assert "M1_trunk_lean" in report_md
    assert "lower" in report_md
    assert "25%" in report_md or "25.0%" in report_md


def test_format_dryrun_report_examples(sample_batch_result):
    """
    What: Verify representative examples are included
    Why: Critical for understanding threshold impact
    """
    report_md = format_dryrun_report(sample_batch_result)

    # Verify example categories
    assert "best" in report_md.lower() or "✨" in report_md
    assert "worst" in report_md.lower() or "⚠️" in report_md

    # Verify example details
    assert "sample_001" in report_md
    assert "WARN" in report_md
    assert "OK" in report_md


# ============================================================================
# Test: Report File Generation
# ============================================================================

def test_generate_report_file_creates_file(sample_batch_result, tmp_path):
    """
    What: Verify report file is created with correct naming
    Why: File persistence for review workflow

    CRITICAL: Timestamp-based naming for uniqueness
    """
    output_dir = tmp_path / "dryrun_reports"

    report_path = generate_report_file(
        batch_result=sample_batch_result,
        output_dir=output_dir,
    )

    # Verify file exists
    assert report_path.exists()
    assert report_path.suffix == ".md"

    # Verify filename contains timestamp
    assert "report_" in report_path.name
    assert len(report_path.stem) > 7  # "report_" + timestamp

    # Verify content
    content = report_path.read_text(encoding="utf-8")
    assert "# Threshold Dry-run Report" in content


def test_generate_report_file_creates_directory(sample_batch_result, tmp_path):
    """
    What: Verify output directory is auto-created
    Why: Simplify user workflow (no manual mkdir)
    """
    output_dir = tmp_path / "nonexistent" / "dryrun_reports"
    assert not output_dir.exists()

    report_path = generate_report_file(
        batch_result=sample_batch_result,
        output_dir=output_dir,
    )

    # Verify directory was created
    assert output_dir.exists()
    assert report_path.exists()


def test_generate_report_file_unique_names(sample_batch_result, tmp_path):
    """
    What: Verify multiple reports have unique filenames
    Why: Avoid overwriting previous reports
    """
    output_dir = tmp_path / "dryrun_reports"

    report1 = generate_report_file(sample_batch_result, output_dir)
    report2 = generate_report_file(sample_batch_result, output_dir)

    # Verify both exist and are different
    assert report1.exists()
    assert report2.exists()
    assert report1 != report2


# ============================================================================
# Test: Changelog Integration
# ============================================================================

def test_record_to_changelog_structure(sample_batch_result, tmp_path):
    """
    What: Verify changelog entry structure
    Why: Contract enforcement for changelog readers

    CRITICAL: Must include report_path and metrics summary
    """
    changelog_path = tmp_path / "changelog.jsonl"
    report_path = Path("results/dryrun_reports/report_20251104_190000.md")

    record_to_changelog(
        batch_result=sample_batch_result,
        report_path=report_path,
        changelog_path=changelog_path,
    )

    # Verify file created
    assert changelog_path.exists()

    # Parse entry
    entry = json.loads(changelog_path.read_text(encoding="utf-8"))

    # Verify required fields
    assert "timestamp" in entry
    assert "event" in entry
    assert entry["event"] == "dryrun_report_generated"
    assert "report_path" in entry
    assert str(report_path) in entry["report_path"]
    assert "overall_reclassified_rate" in entry
    assert entry["overall_reclassified_rate"] == 0.187
    assert "top3_metrics" in entry
    assert len(entry["top3_metrics"]) == 3
    assert "direction_summary" in entry


def test_record_to_changelog_appends(sample_batch_result, tmp_path):
    """
    What: Verify multiple records are appended (not overwritten)
    Why: Preserve full history
    """
    changelog_path = tmp_path / "changelog.jsonl"
    report_path1 = Path("results/report1.md")
    report_path2 = Path("results/report2.md")

    # First record
    record_to_changelog(sample_batch_result, report_path1, changelog_path)

    # Second record
    record_to_changelog(sample_batch_result, report_path2, changelog_path)

    # Verify both entries exist
    lines = changelog_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2

    entry1 = json.loads(lines[0])
    entry2 = json.loads(lines[1])

    assert "report1.md" in entry1["report_path"]
    assert "report2.md" in entry2["report_path"]


def test_record_to_changelog_timestamp_format(sample_batch_result, tmp_path):
    """
    What: Verify timestamp is ISO 8601 format
    Why: Standard format for parsing and sorting
    """
    changelog_path = tmp_path / "changelog.jsonl"
    report_path = Path("results/report.md")

    record_to_changelog(sample_batch_result, report_path, changelog_path)

    entry = json.loads(changelog_path.read_text(encoding="utf-8"))

    # Verify ISO 8601 format (e.g., "2025-11-04T19:00:00Z")
    timestamp = entry["timestamp"]
    assert "T" in timestamp
    assert timestamp.endswith("Z") or "+" in timestamp or "-" in timestamp[-6:]

    # Verify parseable
    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
