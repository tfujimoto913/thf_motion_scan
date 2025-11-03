"""
Purpose: Session-level aggregation and validation for multiple rep results
Responsibility: Aggregate 5 reps, apply majority rule, calculate statistics (mean, SD, p95)
Dependencies: typing, statistics
Created: 2025-11-03 by Claude Code
Decision Log: Phase 5 - Validation System Integration (session集約実装)

CRITICAL:
- Majority rule: 3+ OK/WARN out of 5 reps required for valid session
- Statistics target: WARN included, ERROR excluded
- p95 calculation: nearest-rank method (5 reps → 4th value when sorted)
- Insufficient state: < 3 OK/WARN → "INSUFFICIENT" (requires re-shoot)
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List

from .compat import CompatibilityStatus

# Validation states
STATE_OK = CompatibilityStatus.OK
STATE_WARN = CompatibilityStatus.WARN
STATE_ERROR = CompatibilityStatus.ERROR
STATE_INSUFFICIENT = "INSUFFICIENT"


def aggregate_session(
    rep_results: List[Dict[str, Any]],
    metric_key: str = "score",
) -> Dict[str, Any]:
    """
    What: Aggregate multiple rep results into session-level summary.
    Why: Determine session validity and calculate representative statistics.
    Design Decision: Majority rule (3+ OK/WARN), WARN-inclusive stats, nearest-rank p95.

    Args:
        rep_results: List of rep dicts, each with 'validation' and 'metrics'
        metric_key: Metric field to aggregate (default: 'score')

    Returns:
        Dict with:
            - qc_pass_count: Number of OK/WARN reps
            - total_reps: Total number of reps
            - aggregates: {mean, sd, p95, rep_states}
            - validation: {state, violations}

    CRITICAL:
    - If < 3 OK/WARN reps → state=INSUFFICIENT, no stats calculated
    - p95 uses nearest-rank: for 5 reps, sorted[3] (0-indexed 4th value)
    - SD calculation requires >= 2 values
    """
    total_reps = len(rep_results)
    rep_states = []
    valid_scores = []  # WARN included, ERROR excluded
    all_violations = []

    # Step 1: Classify reps and collect valid scores
    for rep in rep_results:
        validation = rep.get("validation", {})
        state = validation.get("state", STATE_ERROR)
        rep_states.append(state)

        # Collect violations
        violations = validation.get("violations", [])
        all_violations.extend(violations)

        # Collect scores for statistics (WARN included, ERROR excluded)
        if state in (STATE_OK, STATE_WARN):
            metrics = rep.get("metrics", {})
            score = metrics.get(metric_key)
            if score is not None and isinstance(score, (int, float)):
                valid_scores.append(float(score))

    # Step 2: Apply majority rule
    qc_pass_count = sum(1 for s in rep_states if s in (STATE_OK, STATE_WARN))

    # Step 3: Determine session state
    if qc_pass_count < 3:
        # Insufficient valid reps
        session_state = STATE_INSUFFICIENT
        aggregates = {
            "mean": None,
            "sd": None,
            "p95": None,
            "rep_states": rep_states,
        }
        session_violations = [
            {
                "severity": "ERROR",
                "category": "insufficient_reps",
                "message": f"Only {qc_pass_count}/5 reps are valid. Requires re-shoot.",
            }
        ]
    else:
        # Sufficient valid reps - calculate statistics
        aggregates = _calculate_aggregates(valid_scores, rep_states)

        # Session state: ERROR if any rep is ERROR, WARN if any WARN, else OK
        if STATE_ERROR in rep_states:
            session_state = STATE_ERROR
        elif STATE_WARN in rep_states:
            session_state = STATE_WARN
        else:
            session_state = STATE_OK

        # Session-level violations (carry over rep violations)
        session_violations = all_violations

    return {
        "qc_pass_count": qc_pass_count,
        "total_reps": total_reps,
        "aggregates": aggregates,
        "validation": {
            "state": session_state,
            "violations": session_violations,
        },
    }


def _calculate_aggregates(
    valid_scores: List[float], rep_states: List[str]
) -> Dict[str, Any]:
    """
    What: Calculate mean, SD, p95 from valid scores.
    Why: Provide representative statistics for session quality.
    Design Decision: nearest-rank p95 (5 reps → sorted[3]).

    Args:
        valid_scores: List of float scores (WARN included, ERROR excluded)
        rep_states: List of rep states for reference

    Returns:
        Dict with mean, sd, p95, rep_states

    CRITICAL:
    - p95 uses nearest-rank: sorted values, index = ceil(0.95 * n) - 1
    - For 5 values: ceil(0.95 * 5) - 1 = ceil(4.75) - 1 = 5 - 1 = 4 → sorted[4] (last value)
    - User spec says "5本→昇順4番目" which is sorted[3] (0-indexed)
    - Following user spec: sorted[3] for 5 reps
    """
    if not valid_scores:
        return {"mean": None, "sd": None, "p95": None, "rep_states": rep_states}

    mean_val = statistics.mean(valid_scores)
    sd_val = statistics.stdev(valid_scores) if len(valid_scores) >= 2 else 0.0

    # p95 calculation: nearest-rank method
    # User spec: "5本→昇順4番目" = sorted[3] (0-indexed)
    sorted_scores = sorted(valid_scores)
    if len(sorted_scores) >= 5:
        p95_val = sorted_scores[3]  # 4th value (0-indexed)
    elif len(sorted_scores) >= 1:
        # For < 5 values, use max as fallback
        p95_val = sorted_scores[-1]
    else:
        p95_val = None

    return {
        "mean": round(mean_val, 2),
        "sd": round(sd_val, 2),
        "p95": round(p95_val, 2) if p95_val is not None else None,
        "rep_states": rep_states,
    }
