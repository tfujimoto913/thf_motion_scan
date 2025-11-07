"""
Purpose: Load session-level aggregates (session_result.json) for dashboard use.
Responsibility: Fetch session_result data from fixtures, local outputs, or S3.
Dependencies: boto3, streamlit, dashboard.utils
Created: 2025-11-08
Decision Log: Phase 2 dashboard handover (valid reps & validation state UI)

CRITICAL: Must fail gracefully when session_result is unavailable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError

from utils import log_dashboard_event, record_error

# Fixture setup for demo mode
FIXTURE_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "session_result"
VALID_DIR = FIXTURE_DIR / "valid"
INVALID_DIR = FIXTURE_DIR / "invalid"


@dataclass(frozen=True)
class FixtureEntry:
    """Metadata for demo fixtures used in dashboard demo mode."""

    path: Path
    category: str  # "valid" or "invalid"


def _discover_demo_fixtures() -> Dict[str, FixtureEntry]:
    """Scan fixture directory and collect available session_result samples."""
    fixtures: Dict[str, FixtureEntry] = {}

    for category, directory in (("valid", VALID_DIR), ("invalid", INVALID_DIR)):
        if not directory.exists():
            continue
        for json_path in sorted(directory.glob("*.json")):
            fixtures[json_path.stem] = FixtureEntry(path=json_path, category=category)

    return fixtures


_FIXTURE_REGISTRY = _discover_demo_fixtures()
DEMO_FIXTURES = {name: entry.path for name, entry in _FIXTURE_REGISTRY.items()}
DEMO_FIXTURE_META = {name: entry.category for name, entry in _FIXTURE_REGISTRY.items()}

DEFAULT_FIXTURE = (
    "valid_ok_all_pass"
    if "valid_ok_all_pass" in DEMO_FIXTURES
    else next(iter(DEMO_FIXTURES), None)
)

# Local search roots for developers running without S3
LOCAL_SEARCH_ROOTS = [
    Path("output_v2.1_test") / "processed",
    Path("output_v2.1_test2") / "processed",
    Path("outputs") / "processed",
]


@dataclass(frozen=True)
class SessionResultLoadResult:
    """Container for session_result load outcome."""

    data: Optional[Dict[str, Any]]
    source: Optional[str] = None
    error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.data is not None


def load_session_result(
    athlete_id: str,
    session_id: str,
    resources: Optional[Dict[str, Any]],
    *,
    demo_mode: bool = False,
    fixture_name: Optional[str] = None,
) -> SessionResultLoadResult:
    """
    Load session_result.json for the given athlete/session pair.

    Priority order:
        1. Demo fixtures (when demo_mode=True)
        2. Local outputs in output_v2.1_test*/processed
        3. S3 (results bucket)
    """
    if demo_mode and DEMO_FIXTURES:
        name = fixture_name or DEFAULT_FIXTURE or next(iter(DEMO_FIXTURES))
        fixture_path = DEMO_FIXTURES.get(name)
        if fixture_path and fixture_path.exists():
            data = _load_json_file(fixture_path)
            if data:
                category = DEMO_FIXTURE_META.get(name, "valid")
                return SessionResultLoadResult(data=data, source=f"fixture:{category}:{name}")
        # Fall through to local/S3 lookup if fixture missing

    local_path = _find_local_session_result(athlete_id, session_id)
    if local_path:
        data = _load_json_file(local_path)
        if data:
            return SessionResultLoadResult(data=data, source=f"local:{local_path}")

    if not resources or "results_bucket" not in (resources or {}):
        return SessionResultLoadResult(data=None, error="missing_resources")

    bucket = resources["results_bucket"]
    key_candidates = [
        f"processed/{athlete_id}/{session_id}/session_result.json",
        f"{athlete_id}/{session_id}/session_result.json",
    ]

    for key in key_candidates:
        try:
            payload = _fetch_session_result_s3(bucket, key)
            if payload is not None:
                log_dashboard_event(
                    "session_result_fetch",
                    source="s3",
                    bucket=bucket,
                    key=key,
                    size=len(json.dumps(payload)),
                )
                return SessionResultLoadResult(data=payload, source=f"s3:{key}")
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"NoSuchKey", "404"}:
                continue
            record_error("load_session_result", f"{bucket}/{key}: {exc}")
            return SessionResultLoadResult(data=None, error=str(exc))
        except (BotoCoreError, json.JSONDecodeError) as exc:
            record_error("load_session_result", f"{bucket}/{key}: {exc}")
            return SessionResultLoadResult(data=None, error=str(exc))

    return SessionResultLoadResult(data=None, error="not_found")


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_session_result_s3(bucket: str, key: str) -> Optional[Dict[str, Any]]:
    """Fetch and decode session_result.json from S3."""
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    payload = response["Body"].read()
    return json.loads(payload)


@st.cache_data(ttl=300, show_spinner=False)
def _load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON content from a local file."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        record_error("load_session_result_local", f"{path}: {exc}")
        return None


def _find_local_session_result(athlete_id: str, session_id: str) -> Optional[Path]:
    """Lookup session_result.json within known local output directories."""
    for root in LOCAL_SEARCH_ROOTS:
        candidate = root / athlete_id / session_id / "session_result.json"
        if candidate.exists():
            return candidate
    return None
