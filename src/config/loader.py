"""
Purpose: Load thresholds.json and extract version information
Responsibility: File I/O and basic validation for thresholds config
Dependencies: json, pathlib
Created: 2025-11-03
Decision Log: ADR-031 (thresholds.json compatibility checker)

CRITICAL: Must return versions, metadata, and tests sections
"""

import json
from pathlib import Path
from typing import Any, Dict


def load_thresholds(path: str) -> Dict[str, Any]:
    """
    Load thresholds.json and return parsed data.

    What: Read and parse thresholds.json file
    Why: Centralize thresholds loading logic for reuse
    Design Decision: Simple JSON load without validation (validation handled separately)

    Args:
        path: Path to thresholds.json file

    Returns:
        Dict with keys: versions, metadata, tests

    Raises:
        FileNotFoundError: If file does not exist
        json.JSONDecodeError: If file is not valid JSON

    CRITICAL: Caller must handle missing 'versions' key for compatibility checks
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Thresholds file not found: {path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def get_versions(thresholds_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract version information from thresholds data.

    What: Get versions section from loaded thresholds
    Why: Provide convenient access to version fields
    Design Decision: Return empty dict if versions missing (caller handles)

    Args:
        thresholds_data: Parsed thresholds.json dict

    Returns:
        Dict with rules_version, normalization_version, artifact_sha
        Empty dict if 'versions' key is missing

    CRITICAL: Empty dict indicates missing versions (compatibility check should ERROR)
    """
    return thresholds_data.get("versions", {})
