#!/usr/bin/env python3
"""
Purpose: Split docs/adr/decision_log.md into individual ADR files.
Responsibility: Generate 0001-*.md style files, ADR index README, and archive legacy log.
Dependencies: Python 3.10+, pathlib, re, unicodedata
Created: 2025-11-06 by Codex
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple


SOURCE_PATH = Path("docs/adr/decision_log.md")
ADR_DIR = Path("docs/adr")
ARCHIVE_DIR = ADR_DIR / "_archive"
ARCHIVE_PATH = ARCHIVE_DIR / "decision_log_legacy.md"
ADR_PATTERN = re.compile(r"^## (ADR-(\d{3})):\s*(.+)$", re.MULTILINE)


def slugify(title: str, existing: set[str], number: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_title = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_title = ascii_title.lower()
    ascii_title = re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")
    if not ascii_title:
        ascii_title = f"adr-{number}"

    slug = ascii_title
    counter = 1
    while slug in existing:
        counter += 1
        slug = f"{ascii_title}-{counter}"
    existing.add(slug)
    return slug


def extract_metadata(section: str) -> Tuple[Optional[str], str]:
    date_match = re.search(r"^\s*[-*]\s*(?:日付|Date)[:：]\s*(.+)$", section, re.MULTILINE)
    status_match = re.search(r"^\s*[-*]\s*(?:ステータス|Status)[:：]\s*(.+)$", section, re.MULTILINE)

    date = date_match.group(1).strip() if date_match else ""
    status = status_match.group(1).strip() if status_match else "Accepted"

    return date, status


def split_adrs() -> List[Dict[str, str]]:
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Source file not found: {SOURCE_PATH}")

    content = SOURCE_PATH.read_text(encoding="utf-8")
    matches = list(ADR_PATTERN.finditer(content))
    if not matches:
        raise ValueError("No ADR entries found in decision_log.md")

    existing_slugs: set[str] = set()
    metadata_rows: List[Dict[str, str]] = []

    # Remove existing ADR files (0000-*.md) to avoid stale content
    for path in ADR_DIR.glob("[0-9][0-9][0-9][0-9]-*.md"):
        path.unlink()

    for index, match in enumerate(matches):
        adr_label = match.group(1)
        number = match.group(2)
        title = match.group(3).strip()
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        section = content[start:end].strip() + "\n"

        slug = slugify(title, existing_slugs, number)
        filename = f"{int(number):04d}-{slug}.md"
        output_path = ADR_DIR / filename
        output_path.write_text(section, encoding="utf-8")

        date, status = extract_metadata(section)
        metadata_rows.append(
            {
                "number": number,
                "label": adr_label,
                "title": title,
                "date": date,
                "status": status,
                "filename": filename,
            }
        )

    return metadata_rows


def write_readme(metadata_rows: List[Dict[str, str]]) -> None:
    rows = sorted(metadata_rows, key=lambda item: int(item["number"]))

    lines = [
        "# Architecture Decision Records",
        "",
        "This directory contains the codified decisions that guide the THF Motion Scan project.",
        "",
        "## Index",
        "",
        "| ADR | Title | Date | Status |",
        "| --- | ----- | ---- | ------ |",
    ]

    for row in rows:
        link = f"[{row['title']}]({row['filename']})"
        lines.append(
            f"| {row['label']} | {link} | {row['date']} | {row['status']} |"
        )

    lines.extend(
        [
            "",
            "## How to Create a New ADR",
            "",
            "1. Copy `template.md` to a new file named `XXXX-your-slug.md` where `XXXX` is the next sequential number.",
            "2. Update the heading (`# ADR-XXXX: Title`) and complete each section of the template.",
            "3. Link related ADRs in the References section to maintain traceability.",
            "4. Submit the ADR in a pull request; once merged, update this README table.",
            "",
            "## Template",
            "",
            "- See [`template.md`](template.md) for the canonical ADR structure.",
            "- Fields follow [Michael Nygard's ADR format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions).",
        ]
    )

    (ADR_DIR / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_template() -> None:
    template_path = ADR_DIR / "template.md"
    if template_path.exists():
        return

    template_path.write_text(
        """# ADR-XXXX: [Title]

- Date: YYYY-MM-DD
- Status: Accepted | Deprecated | Superseded by ADR-XXXX
- Deciders: [Who made the decision]

## Context

[What is the issue we're trying to solve? Background and motivation.]

## Decision

[What did we decide? The change or action being proposed.]

## Rationale

[Why did we decide this way? The reasoning behind the decision.]

## Consequences

**Positive**:
- [Benefit 1]
- [Benefit 2]

**Negative**:
- [Trade-off 1]
- [Risk or cost 2]

**Neutral**:
- [Impact that is neither clearly positive nor negative]

## Alternatives Considered

**Alternative 1: [Name]**
- Description: [Brief description]
- Pros: [Advantages]
- Cons: [Disadvantages]
- Decision: ❌ Rejected because [reason]

**Alternative 2: [Name]**
- ...

## Implementation Details

[Optional: Technical details, code snippets, configuration examples]

## References

- Related ADRs: ADR-XXX, ADR-YYY
- Commits: abc1234, def5678
- Files: `path/to/file.py`, `path/to/config.json`
- External docs: [Link to documentation]

## Notes

[Optional: Additional context, follow-up tasks, or historical notes]
""",
        encoding="utf-8",
    )


def archive_legacy_log() -> None:
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    SOURCE_PATH.rename(ARCHIVE_PATH)


def main() -> None:
    ensure_template()
    metadata_rows = split_adrs()
    write_readme(metadata_rows)
    archive_legacy_log()


if __name__ == "__main__":
    main()
