"""
Purpose: Validate QC gate rule evaluation
Responsibility: Ensure qc_gate rules flag violations and pass valid results
Dependencies: processing.qc_gate
Created: 2025-11-03 by Codex
Decision Log: Phase 0-4 適用ルール運用開始
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from processing.qc_gate import QCGate


@pytest.fixture
def qc_config(tmp_path: Path) -> Path:
    data = {
        "single_leg_squat": {
            "rules": [
                {
                    "id": "B4_SIGMA_MIN",
                    "path": "B_principles.eccentric.B4_pelvis_horizontal",
                    "operator": "gte",
                    "value": 3.0,
                    "severity": "WARN",
                    "message": "B4 pelvis horizontal score below QC gate (>= 3.0)",
                }
            ]
        }
    }
    config_path = tmp_path / "qc_gate.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")
    return config_path


def test_qc_gate_flags_violation(qc_config: Path) -> None:
    gate = QCGate(qc_config)
    evaluation = {
        "B_principles": {
            "eccentric": {
                "B4_pelvis_horizontal": 2.5,
            }
        }
    }

    result = gate.evaluate("single_leg_squat", evaluation)

    assert result["passed"] is False
    assert result["violations"][0]["observed"] == 2.5


def test_qc_gate_passes_when_threshold_met(qc_config: Path) -> None:
    gate = QCGate(qc_config)
    evaluation = {
        "B_principles": {
            "eccentric": {
                "B4_pelvis_horizontal": 3.2,
            }
        }
    }

    result = gate.evaluate("single_leg_squat", evaluation)

    assert result["passed"] is True
    assert result["violations"] == []


def test_qc_gate_missing_metric_fails(qc_config: Path) -> None:
    gate = QCGate(qc_config)
    evaluation = {"B_principles": {"eccentric": {}}}

    result = gate.evaluate("single_leg_squat", evaluation)

    assert result["passed"] is False
