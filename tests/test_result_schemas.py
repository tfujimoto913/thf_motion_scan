"""
Purpose: Validate rep_result and session_result schemas against fixture data.
Responsibility: Ensure schema changes keep downstream contracts stable.
Dependencies: jsonschema Draft7Validator, pytest
Created: 2025-11-05 by Codex
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator, Tuple

import pytest
from jsonschema import Draft7Validator


ROOT = Path(__file__).parent.parent
SCHEMA_DIR = ROOT / "schema"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "schemas"


def _load_schema(path: Path) -> Draft7Validator:
    """Load a JSON Schema file and return a Draft7Validator."""
    raw = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback for .jsonl schema (single JSON object per line)
        lines = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if len(lines) != 1:
            raise
        payload = lines[0]
    return Draft7Validator(payload)


def _iter_documents(path: Path) -> Iterator[Tuple[int, dict]]:
    """Yield (line_number, document) pairs from JSON or JSONL fixtures."""
    if path.suffix == ".jsonl":
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            yield line_no, json.loads(line)
    else:
        yield 1, json.loads(path.read_text(encoding="utf-8"))


def _format_errors(errors) -> str:
    return "\n".join(f"{list(err.path)}: {err.message}" for err in errors)


rep_result_valid_cases = sorted((FIXTURE_ROOT / "rep_result" / "valid").glob("*.json*"))
rep_result_invalid_cases = sorted((FIXTURE_ROOT / "rep_result" / "invalid").glob("*.json*"))
session_result_valid_cases = sorted((FIXTURE_ROOT / "session_result" / "valid").glob("*.json*"))
session_result_invalid_cases = sorted((FIXTURE_ROOT / "session_result" / "invalid").glob("*.json*"))


@pytest.mark.parametrize("fixture_path", rep_result_valid_cases, ids=lambda p: p.name)
def test_rep_result_schema_accepts_valid_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "rep_result.schema.jsonl")
    for line_no, document in _iter_documents(fixture_path):
        errors = list(validator.iter_errors(document))
        assert not errors, f"{fixture_path}:{line_no} { _format_errors(errors) }"


@pytest.mark.parametrize("fixture_path", rep_result_invalid_cases, ids=lambda p: p.name)
def test_rep_result_schema_rejects_invalid_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "rep_result.schema.jsonl")
    seen_error = False
    for _, document in _iter_documents(fixture_path):
        errors = list(validator.iter_errors(document))
        if errors:
            seen_error = True
    assert seen_error, f"{fixture_path} unexpectedly passed schema validation"


@pytest.mark.parametrize("fixture_path", session_result_valid_cases, ids=lambda p: p.name)
def test_session_result_schema_accepts_valid_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "session_result.schema.json")
    for line_no, document in _iter_documents(fixture_path):
        errors = list(validator.iter_errors(document))
        assert not errors, f"{fixture_path}:{line_no} { _format_errors(errors) }"
        # Cross-field constraint: qc_pass_count must not exceed total_reps
        qc_pass = document.get("qc_pass_count")
        total_reps = document.get("total_reps")
        if isinstance(qc_pass, int) and isinstance(total_reps, int):
            assert qc_pass <= total_reps, (
                f"{fixture_path}:{line_no} qc_pass_count ({qc_pass}) "
                f"cannot exceed total_reps ({total_reps})"
            )


@pytest.mark.parametrize("fixture_path", session_result_invalid_cases, ids=lambda p: p.name)
def test_session_result_schema_rejects_invalid_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "session_result.schema.json")
    seen_error = False
    for _, document in _iter_documents(fixture_path):
        errors = list(validator.iter_errors(document))
        if errors:
            seen_error = True
            continue
        qc_pass = document.get("qc_pass_count")
        total_reps = document.get("total_reps")
        if isinstance(qc_pass, int) and isinstance(total_reps, int) and qc_pass > total_reps:
            seen_error = True
    assert seen_error, f"{fixture_path} unexpectedly passed schema validation"
