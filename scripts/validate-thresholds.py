#!/usr/bin/env python3
"""
Validate thresholds.json against JSON Schema and business rules.

Purpose: Ensure thresholds.json conforms to schema and contains all required test_codes
Responsibility: Schema validation, coverage check, band continuity check
Created: 2025-11-02
Decision Log: ADR-028 (thresholds.json v1.0.0 export)

Usage:
    python scripts/validate-thresholds.py config/thresholds.json
    python scripts/validate-thresholds.py --schema schema/thresholds.schema.json config/thresholds.json

Exit codes:
    0 - Valid
    1 - Validation errors found
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import jsonschema
    from jsonschema import Draft7Validator
except ImportError:
    print("Error: jsonschema library not found. Install with: pip install jsonschema", file=sys.stderr)
    sys.exit(1)


# CRITICAL: Expected test_code list (ADR-023 v2.1 system)
EXPECTED_TEST_CODES = [
    "single_leg_squat",
    "skater_lunge",
    "stride_mimic",
    "jump_landing",
    "upper_body_swing",
    "push_pull",
    "cross_step",
]


def load_json(file_path: Path) -> Dict[str, Any]:
    """
    Load JSON file with error handling.

    What: Parse JSON file and return as dict
    Why: Centralize file loading with clear error messages
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def validate_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> List[str]:
    """
    Validate data against JSON Schema.

    What: Run jsonschema validation and collect errors
    Why: Ensure structural integrity before business rule checks
    Design Decision: Use Draft7Validator for better error messages

    Returns: List of error messages (empty if valid)
    """
    validator = Draft7Validator(schema)
    errors = []

    for error in sorted(validator.iter_errors(data), key=lambda e: e.path):
        path = ".".join(str(p) for p in error.path)
        errors.append(f"  [{path or 'root'}] {error.message}")

    return errors


def check_test_coverage(data: Dict[str, Any]) -> List[str]:
    """
    Check if all expected test_codes are present.

    What: Verify tests object contains all 7 test_codes
    Why: Prevent missing test configurations
    Design Decision: Use EXPECTED_TEST_CODES constant (ADR-023)

    Returns: List of error messages (empty if all present)
    """
    errors = []
    tests = data.get("tests", {})

    for test_code in EXPECTED_TEST_CODES:
        if test_code not in tests:
            errors.append(f"  Missing test_code: {test_code}")

    extra_tests = set(tests.keys()) - set(EXPECTED_TEST_CODES)
    if extra_tests:
        errors.append(f"  Unexpected test_codes: {', '.join(sorted(extra_tests))}")

    return errors


def check_band_continuity(bands: List[Dict[str, Any]]) -> List[str]:
    """
    Check if bands are non-overlapping and provide continuous coverage (recommended).

    What: Validate band intervals don't overlap
    Why: Ensure unambiguous threshold classification
    Design Decision: Relaxed check (warnings only) since overlap may be intentional

    CRITICAL: This is a heuristic check, not a strict requirement

    Returns: List of warning messages (empty if no issues)
    """
    warnings = []

    # Extract numeric intervals from bands
    intervals = []
    for i, band in enumerate(bands):
        op = band.get("op")
        value = band.get("value")
        name = band.get("name")

        if op == "range_inc" and isinstance(value, list) and len(value) == 2:
            intervals.append((value[0], value[1], name, i))
        elif op in ["gte", "gt"] and isinstance(value, (int, float)):
            intervals.append((value, float('inf'), name, i))
        elif op in ["lte", "lt"] and isinstance(value, (int, float)):
            intervals.append((float('-inf'), value, name, i))
        elif op == "eq" and isinstance(value, (int, float)):
            intervals.append((value, value, name, i))

    # Check for overlaps (simple heuristic)
    for i, (a_min, a_max, a_name, a_idx) in enumerate(intervals):
        for b_min, b_max, b_name, b_idx in intervals[i+1:]:
            # Check if intervals overlap
            if not (a_max < b_min or b_max < a_min):
                warnings.append(
                    f"    Band overlap detected: bands[{a_idx}] ({a_name}: [{a_min}, {a_max}]) "
                    f"and bands[{b_idx}] ({b_name}: [{b_min}, {b_max}])"
                )

    return warnings


def validate_thresholds(thresholds_path: Path, schema_path: Path) -> Tuple[bool, List[str]]:
    """
    Run all validation checks on thresholds.json.

    What: Orchestrate schema validation, coverage check, and band continuity
    Why: Single entry point for all validation logic

    Returns: (is_valid, error_messages)
    """
    errors = []

    # Load files
    data = load_json(thresholds_path)
    schema = load_json(schema_path)

    # 1. Schema validation
    schema_errors = validate_schema(data, schema)
    if schema_errors:
        errors.append("Schema validation errors:")
        errors.extend(schema_errors)

    # 2. Test coverage check
    coverage_errors = check_test_coverage(data)
    if coverage_errors:
        errors.append("\nTest coverage errors:")
        errors.extend(coverage_errors)

    # 3. Band continuity check (warnings only)
    tests = data.get("tests", {})
    for test_code, test_config in tests.items():
        bands = test_config.get("thresholds", {}).get("primary", {}).get("bands", [])
        if bands:
            band_warnings = check_band_continuity(bands)
            if band_warnings:
                errors.append(f"\nBand continuity warnings for '{test_code}':")
                errors.extend(band_warnings)

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description="Validate thresholds.json configuration")
    parser.add_argument(
        "thresholds",
        type=Path,
        help="Path to thresholds.json file"
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("schema/thresholds.schema.json"),
        help="Path to JSON Schema file (default: schema/thresholds.schema.json)"
    )

    args = parser.parse_args()

    print(f"Validating: {args.thresholds}")
    print(f"Schema: {args.schema}")
    print("-" * 60)

    is_valid, errors = validate_thresholds(args.thresholds, args.schema)

    if is_valid:
        print("✅ Validation passed: thresholds.json is valid")
        sys.exit(0)
    else:
        print("❌ Validation failed:\n")
        for error in errors:
            print(error)
        sys.exit(1)


if __name__ == "__main__":
    main()
