#!/usr/bin/env python3
"""
Validate THF Motion Scan threshold configuration files against the JSON schema.

Usage:
    python scripts/validate.py                          # Validate config/thresholds.json
    python scripts/validate.py config/thresholds.json
    python scripts/validate.py tests/fixtures/thresholds/valid
    python scripts/validate.py path/to/file1 path/to/dir2
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

try:
    from jsonschema import Draft7Validator
    from jsonschema.exceptions import ValidationError
except ImportError as exc:  # pragma: no cover - provides friendly hint
    raise SystemExit(
        "Missing dependency 'jsonschema'. Install development dependencies with:\n"
        "  pip install -r requirements-dev.txt"
    ) from exc


DEFAULT_SCHEMA_PATH = Path("schema/thresholds.schema.json")
DEFAULT_TARGET = Path("config/thresholds.json")


class ThresholdValidationError:
    """Container for human-readable validation errors."""

    def __init__(self, path: str, message: str) -> None:
        self.path = path or "<root>"
        self.message = message

    def __str__(self) -> str:  # noqa: D401
        return f"{self.path}: {self.message}"


def _format_json_path(error: ValidationError) -> str:
    """Render a jsonschema error path like $.tests.single_leg_squat."""
    segments: List[str] = ["$"]
    for part in error.absolute_path:
        if isinstance(part, int):
            segments.append(f"[{part}]")
        else:
            segments.append(f".{part}")
    return "".join(segments)


def load_schema(schema_path: Path) -> Draft7Validator:
    with schema_path.open("r", encoding="utf-8") as fh:
        schema = json.load(fh)
    return Draft7Validator(schema)


def load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_json_files(targets: Sequence[Path]) -> Iterable[Path]:
    """Yield JSON files for given targets (files or directories)."""
    for target in targets:
        if target.is_dir():
            yield from sorted(
                p for p in target.rglob("*.json") if p.is_file()
            )
        else:
            yield target


def run_jsonschema_validation(validator: Draft7Validator, data: Dict) -> List[ThresholdValidationError]:
    errors: List[ThresholdValidationError] = []
    for error in sorted(validator.iter_errors(data), key=lambda e: e.json_path):
        errors.append(ThresholdValidationError(_format_json_path(error), error.message))
    return errors


def run_custom_checks(data: Dict) -> List[ThresholdValidationError]:
    """Perform validations that are hard to express in pure JSON Schema."""
    errors: List[ThresholdValidationError] = []

    tests = data.get("tests")
    if not isinstance(tests, dict):
        return errors

    seen_codes: Dict[str, str] = {}
    for test_key, test_body in tests.items():
        if not isinstance(test_body, dict):
            continue

        code = test_body.get("code")
        json_path_prefix = f"$.tests.{test_key}"

        if isinstance(code, str):
            if code in seen_codes:
                errors.append(
                    ThresholdValidationError(
                        f"{json_path_prefix}.code",
                        f"duplicate code '{code}' also used by '{seen_codes[code]}'",
                    )
                )
            else:
                seen_codes[code] = test_key

            if code != test_key:
                errors.append(
                    ThresholdValidationError(
                        f"{json_path_prefix}.code",
                        f"code '{code}' must match key '{test_key}'",
                    )
                )

        thresholds = test_body.get("thresholds")
        if not isinstance(thresholds, dict):
            continue

        primary = thresholds.get("primary")
        if not isinstance(primary, dict):
            continue

        bands = primary.get("bands")
        if not isinstance(bands, list):
            continue

        seen_band_names: Dict[str, int] = {}
        for idx, band in enumerate(bands):
            if not isinstance(band, dict):
                continue

            band_name = band.get("name")
            band_path = f"{json_path_prefix}.thresholds.primary.bands[{idx}]"

            if isinstance(band_name, str):
                if band_name in seen_band_names:
                    first_idx = seen_band_names[band_name]
                    errors.append(
                        ThresholdValidationError(
                            f"{band_path}.name",
                            f"duplicate band classification '{band_name}' also used at index {first_idx}",
                        )
                    )
                else:
                    seen_band_names[band_name] = idx

            if band.get("op") == "range_inc":
                value = band.get("value")
                if (
                    isinstance(value, list)
                    and len(value) == 2
                    and isinstance(value[0], (int, float))
                    and isinstance(value[1], (int, float))
                    and value[0] > value[1]
                ):
                    errors.append(
                        ThresholdValidationError(
                            f"{band_path}.value",
                            f"range_inc lower bound {value[0]} must be <= upper bound {value[1]}",
                        )
                    )

    return errors
# fmt: off

def validate_file(validator: Draft7Validator, file_path: Path, quiet: bool = False) -> List[ThresholdValidationError]:
    # fmt: on
    try:
        data = load_json(file_path)
    except json.JSONDecodeError as exc:  # type: ignore[attr-defined]
        return [
            ThresholdValidationError(
                file_path.as_posix(),
                f"invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})",
            )
        ]

    errors = run_jsonschema_validation(validator, data)
    errors.extend(run_custom_checks(data))

    if not errors and not quiet:
        print(f"✔ {file_path.as_posix()} ✓")

    return errors


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate threshold configuration JSON files.")
    parser.add_argument(
        "targets",
        nargs="*",
        type=Path,
        help="Files or directories to validate (defaults to config/thresholds.json).",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help=f"Path to JSON schema (default: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only print failures.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    schema_path = args.schema
    if not schema_path.exists():
        print(f"[ERROR] Schema not found: {schema_path}")
        return 2

    validator = load_schema(schema_path)

    targets = args.targets if args.targets else [DEFAULT_TARGET]
    files = list(iter_json_files(targets))
    if not files:
        print("[ERROR] No JSON files to validate.")
        return 2

    any_errors = False
    for json_file in files:
        errors = validate_file(validator, json_file, quiet=args.quiet)
        if errors:
            any_errors = True
            print(f"✖ {json_file.as_posix()}")
            for error in errors:
                print(f"  - {error}")

    if any_errors:
        return 1

    if not args.quiet:
        print(f"Validated {len(files)} file(s) successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
