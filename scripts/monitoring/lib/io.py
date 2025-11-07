"""
I/O helpers for monitoring scripts.

Provides UTF-8 JSON/Markdown utilities and helpers for persisting
partial results (exit code 2 scenarios).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Optional


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> object:
    """Read UTF-8 JSON from disk."""
    with Path(path).open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_json(path: Path, data: object, *, indent: int = 2) -> None:
    """Write UTF-8 JSON, creating parent directories automatically."""
    target = Path(path)
    _ensure_parent(target)
    with target.open("w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=indent)
        fp.write("\n")


def _build_markdown_table(
    metrics: Iterable[Mapping[str, object]],
    *,
    partial: bool = False,
    retry_command: Optional[str] = None,
) -> str:
    lines = [
        "| Metric | Value | Timestamp |",
        "| --- | --- | --- |",
    ]

    for item in metrics:
        metric = str(item.get("metric", "-"))
        value = item.get("value", "-")
        timestamp = item.get("timestamp", "-")
        lines.append(f"| {metric} | {value} | {timestamp} |")

    if partial:
        lines.append("")
        lines.append("> ⚠️ 部分結果のみ保存されています。")

    if retry_command:
        lines.append("")
        lines.append("```bash")
        lines.append(retry_command)
        lines.append("```")

    return "\n".join(lines)


def write_markdown(
    path: Path,
    metrics: Iterable[Mapping[str, object]],
    *,
    partial: bool = False,
    retry_command: Optional[str] = None,
) -> None:
    """Write Markdown table with optional partial-result note and retry hint."""
    target = Path(path)
    _ensure_parent(target)
    content = _build_markdown_table(metrics, partial=partial, retry_command=retry_command)
    target.write_text(content + "\n", encoding="utf-8")


__all__ = [
    "read_json",
    "write_json",
    "write_markdown",
]
