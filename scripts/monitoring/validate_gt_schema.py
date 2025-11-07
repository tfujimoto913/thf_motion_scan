#!/usr/bin/env python3
"""
Validate Ground Truth evaluation JSON files.

Usage:
    python scripts/monitoring/validate_gt_schema.py path/to/file.json [...]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple

REQUIRED_FIELDS = {
    "athlete_id": str,
    "session_id": str,
    "test_code": str,
    "ai_score": (int, float),
    "human_score": (int, float),
    "override_flag": bool,
    "reviewer": str,
    "rules_version": str,
    "artifact_sha": str,
    "created_at": str,
}


def _iter_input_paths(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_dir():
            yield from sorted(path.rglob("*.json"))
        else:
            yield path


def _validate_iso8601(value: str) -> bool:
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        datetime.fromisoformat(value)
        return True
    except ValueError:
        return False


def validate_file(path: Path) -> List[str]:
    errors: List[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: failed to parse JSON ({exc})")
        return errors

    if not isinstance(data, dict):
        errors.append(f"{path}: root must be a JSON object")
        return errors

    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"{path}: missing required field '{field}'")
            continue
        value = data[field]
        if field == "override_flag" and isinstance(value, bool):
            pass
        elif isinstance(expected_type, tuple):
            if not isinstance(value, expected_type):
                errors.append(f"{path}: field '{field}' must be numeric")
        elif not isinstance(value, expected_type):
            errors.append(f"{path}: field '{field}' must be of type {expected_type.__name__}")

    created_at = data.get("created_at")
    if isinstance(created_at, str) and not _validate_iso8601(created_at):
        errors.append(f"{path}: created_at '{created_at}' is not ISO8601")

    return errors


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate GT evaluation JSON files")
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="JSON file or directory (directories are scanned recursively)",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    errors: List[str] = []
    for path in _iter_input_paths(args.paths):
        errors.extend(validate_file(path))

    if errors:
        for message in errors:
            print(message, file=sys.stderr)
        return 1

    print("All files valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
