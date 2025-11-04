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
REP_FIXTURES = ROOT / "tests" / "fixtures" / "rep_result"
SESSION_FIXTURES = ROOT / "tests" / "fixtures" / "session_result"
THRESHOLDS_FIXTURES = ROOT / "tests" / "fixtures" / "thresholds_v2"


def _load_schema(path: Path) -> Draft7Validator:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Draft7Validator(payload)


def _iter_documents(path: Path) -> Iterator[Tuple[int, dict]]:
    yield 1, json.loads(path.read_text(encoding="utf-8"))


def _format_errors(errors) -> str:
    return "\n".join(f"{list(err.path)}: {err.message}" for err in errors)


rep_result_valid_cases = sorted((REP_FIXTURES / "valid").glob("*.json"))
rep_result_warn_cases = sorted((REP_FIXTURES / "warn").glob("*.json"))
rep_result_invalid_cases = sorted((REP_FIXTURES / "invalid").glob("*.json"))

session_result_valid_cases = sorted((SESSION_FIXTURES / "valid").glob("*.json"))
session_result_warn_cases = sorted((SESSION_FIXTURES / "warn").glob("*.json"))
session_result_invalid_cases = sorted((SESSION_FIXTURES / "invalid").glob("*.json"))

thresholds_valid_cases = sorted((THRESHOLDS_FIXTURES / "valid").glob("*.json"))
thresholds_warn_cases = sorted((THRESHOLDS_FIXTURES / "warn").glob("*.json"))
thresholds_invalid_cases = sorted((THRESHOLDS_FIXTURES / "invalid").glob("*.json"))


@pytest.mark.parametrize("fixture_path", rep_result_valid_cases, ids=lambda p: p.name)
def test_rep_result_schema_accepts_valid_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "rep_result.schema.json")
    for line_no, document in _iter_documents(fixture_path):
        errors = list(validator.iter_errors(document))
        assert not errors, f"{fixture_path}:{line_no} { _format_errors(errors) }"


@pytest.mark.parametrize("fixture_path", rep_result_warn_cases, ids=lambda p: p.name)
def test_rep_result_schema_accepts_warn_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "rep_result.schema.json")
    for line_no, document in _iter_documents(fixture_path):
        errors = list(validator.iter_errors(document))
        assert not errors, f"{fixture_path}:{line_no} { _format_errors(errors) }"


@pytest.mark.parametrize("fixture_path", rep_result_invalid_cases, ids=lambda p: p.name)
def test_rep_result_schema_rejects_invalid_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "rep_result.schema.json")
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
        agg = document.get("aggregates", {})
        valid_count = agg.get("valid_rep_count")
        total_count = agg.get("total_rep_count")
        if isinstance(valid_count, int) and isinstance(total_count, int):
            assert valid_count <= total_count, (
                f"{fixture_path}:{line_no} valid_rep_count ({valid_count}) exceeds total_rep_count ({total_count})"
            )


@pytest.mark.parametrize("fixture_path", session_result_warn_cases, ids=lambda p: p.name)
def test_session_result_schema_accepts_warn_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "session_result.schema.json")
    for line_no, document in _iter_documents(fixture_path):
        errors = list(validator.iter_errors(document))
        assert not errors, f"{fixture_path}:{line_no} { _format_errors(errors) }"


@pytest.mark.parametrize("fixture_path", session_result_invalid_cases, ids=lambda p: p.name)
def test_session_result_schema_rejects_invalid_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "session_result.schema.json")
    seen_error = False
    for _, document in _iter_documents(fixture_path):
        errors = list(validator.iter_errors(document))
        if errors:
            seen_error = True
    assert seen_error, f"{fixture_path} unexpectedly passed schema validation"


@pytest.mark.parametrize("fixture_path", thresholds_valid_cases + thresholds_warn_cases, ids=lambda p: p.name)
def test_thresholds_v2_schema_accepts_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "thresholds_v2.schema.json")
    document = json.loads(fixture_path.read_text(encoding="utf-8"))
    errors = list(validator.iter_errors(document))
    assert not errors, f"{fixture_path}: { _format_errors(errors) }"


@pytest.mark.parametrize("fixture_path", thresholds_invalid_cases, ids=lambda p: p.name)
def test_thresholds_v2_schema_rejects_invalid_documents(fixture_path: Path) -> None:
    validator = _load_schema(SCHEMA_DIR / "thresholds_v2.schema.json")
    document = json.loads(fixture_path.read_text(encoding="utf-8"))
    errors = list(validator.iter_errors(document))
    assert errors, f"{fixture_path} unexpectedly passed schema validation"
