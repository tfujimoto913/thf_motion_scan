#!/usr/bin/env python3
"""
Purpose: Generate Markdown reports for threshold dry-run results (PR#4)
Responsibility: Format batch dry-run output into human-readable reports
Dependencies: pandas, pathlib, datetime, json
Created: 2025-11-04 by Claude Code
Decision Log: PR#4 - MVP completion pack

CRITICAL:
- Markdown format for GitHub/Notion compatibility
- Automatic changelog recording on report generation
- Timestamp-based file naming for uniqueness

Usage:
    from tools.generate_dryrun_report import generate_report_file

    report_path = generate_report_file(
        batch_result=run_batch_dryrun(...),
        output_dir=Path("results/dryrun_reports"),
    )
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def format_dryrun_report(batch_result: dict[str, Any]) -> str:
    """
    What: Format batch dry-run result as Markdown report
    Why: Human-readable summary for threshold change review
    Design Decision: GitHub-flavored Markdown with tables

    Args:
        batch_result: Output from run_batch_dryrun()

    Returns:
        Markdown-formatted report string

    CRITICAL:
    - Must include all MVP sections
    - Table format for metric summary
    - Top 3 metrics highlighted
    - Representative examples with details

    Examples:
        >>> result = run_batch_dryrun(...)
        >>> report_md = format_dryrun_report(result)
        >>> "# Threshold Dry-run Report" in report_md
        True
    """
    lines = []

    # Header
    lines.append("# Threshold Dry-run Report")
    lines.append("")
    lines.append(f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("")

    # Overall Impact
    lines.append("## Overall Impact")
    lines.append("")
    overall_rate = batch_result["overall_reclassified_rate"]
    exec_time_ms = batch_result["execution_time_ms"]
    exec_time_s = exec_time_ms / 1000.0

    lines.append(f"- **Reclassified Rate**: {overall_rate:.1%}")
    lines.append(f"- **Execution Time**: {exec_time_ms}ms ({exec_time_s:.2f}s)")
    lines.append("")

    # Summary Table
    lines.append("## Summary by Metric")
    lines.append("")

    summary_df = batch_result["summary_df"]

    # Convert to Markdown table
    lines.append("| Metric | Direction | Reclassified | Affected Count | Sample Size |")
    lines.append("|--------|-----------|--------------|----------------|-------------|")

    for _, row in summary_df.iterrows():
        metric_id = row["metric_id"]
        direction = row["direction"]
        reclassified_rate = row["reclassified_rate"]
        affected = row["affected_count"]
        n_sample = row["n_sample"]

        lines.append(
            f"| {metric_id} | {direction} | {reclassified_rate:.1%} | "
            f"{affected} | {n_sample} |"
        )

    lines.append("")

    # Top 3 Metrics
    lines.append("## Top 3 Metrics (Highest Impact)")
    lines.append("")

    top3 = batch_result["top3_metrics"]
    for i, metric_id in enumerate(top3, 1):
        metric_row = summary_df[summary_df["metric_id"] == metric_id]
        if not metric_row.empty:
            row = metric_row.iloc[0]
            lines.append(
                f"{i}. **{metric_id}**: {row['affected_count']} affected "
                f"({row['reclassified_rate']:.1%})"
            )

    lines.append("")

    # Representative Examples
    lines.append("## Representative Examples")
    lines.append("")

    examples = batch_result["representative_examples"]
    if examples:
        for ex in examples:
            category = ex["category"]
            category_emoji = {"best": "✨", "worst": "⚠️", "neutral": "📍"}.get(
                category, "•"
            )

            lines.append(f"### {category_emoji} {category.upper()}")
            lines.append("")
            lines.append(f"- **Metric**: {ex['metric_id']}")
            lines.append(f"- **Sample ID**: {ex['sample_id']}")
            lines.append(f"- **Old Label**: {ex['old_label']}")
            lines.append(f"- **New Label**: {ex['new_label']}")
            lines.append(f"- **Value**: {ex['metric_value']:.2f}")
            lines.append("")
    else:
        lines.append("No representative examples available.")
        lines.append("")

    # Direction Summary
    lines.append("## Direction Summary")
    lines.append("")

    direction_summary = batch_result["direction_summary"]
    lines.append(f"- **Lower (lower_is_better)**: {direction_summary['lower_count']} metrics")
    lines.append(f"- **Higher (higher_is_better)**: {direction_summary['higher_count']} metrics")
    lines.append(f"- **Unspecified**: {direction_summary['unspecified_count']} metrics")
    lines.append("")

    return "\n".join(lines)


def generate_report_file(
    batch_result: dict[str, Any],
    output_dir: Path,
) -> Path:
    """
    What: Generate Markdown report file from batch dry-run result
    Why: Persist report for review and decision workflow
    Design Decision: Timestamp-based naming for uniqueness

    Args:
        batch_result: Output from run_batch_dryrun()
        output_dir: Directory to save report (auto-created if needed)

    Returns:
        Path to generated report file

    CRITICAL:
    - Auto-create output directory
    - Unique filename with timestamp
    - UTF-8 encoding

    Examples:
        >>> result = run_batch_dryrun(...)
        >>> report_path = generate_report_file(result, Path("results/dryrun_reports"))
        >>> report_path.exists()
        True
        >>> report_path.suffix
        '.md'
    """
    # Auto-create directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename with timestamp (including microseconds for uniqueness)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"report_{timestamp}.md"
    report_path = output_dir / filename

    # Format and write report
    report_md = format_dryrun_report(batch_result)
    report_path.write_text(report_md, encoding="utf-8")

    return report_path


def record_to_changelog(
    batch_result: dict[str, Any],
    report_path: Path,
    changelog_path: Path,
) -> None:
    """
    What: Record report generation to changelog.jsonl
    Why: Maintain audit trail of threshold change investigations
    Design Decision: JSONL append-only format

    Args:
        batch_result: Output from run_batch_dryrun()
        report_path: Path to generated report file
        changelog_path: Path to changelog.jsonl (auto-created if needed)

    CRITICAL:
    - Append-only (preserve history)
    - ISO 8601 timestamp
    - Include metrics summary for quick reference

    Examples:
        >>> record_to_changelog(result, report_path, Path("changelog.jsonl"))
        >>> changelog_path.exists()
        True
    """
    # Prepare changelog entry
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "dryrun_report_generated",
        "report_path": str(report_path),
        "overall_reclassified_rate": float(batch_result["overall_reclassified_rate"]),
        "top3_metrics": batch_result["top3_metrics"],
        "metrics_count": len(batch_result["summary_df"]),
        "direction_summary": batch_result["direction_summary"],
    }

    # Append to changelog (create if doesn't exist)
    with open(changelog_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
