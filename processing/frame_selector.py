"""
Purpose: Static frame selection and storage helpers for rep/session pipelines
Responsibility: Pick best/worst/representative frames/reps and build storage keys
Dependencies: typing, re, pathlib, boto3 (optional for upload), statistics
Created: 2025-11-06 by Codex
Updated: 2025-11-04 by Claude Code - Phase2 KPI-based frame selection
Decision Log: Task E - Static frame selection (Phase2 Rep基盤), Phase2 Overlay仕様FIX, Phase2 静止画選出ロジック

CRITICAL:
- select_representative_reps() selects 3 reps (best/worst/repr) from multiple reps
- N/A handling: exclude N/A KPIs, require >= 50% valid KPIs
- Tiebreak: N/A rate (lower is better) -> rep_number (earlier is better)
- extract_frame_kpis() extracts B1-B8 KPIs from evaluator output for frame-level selection
"""

from __future__ import annotations

import logging
import math
import re
import statistics
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

FRAME_TYPES = ("best", "worst", "repr")

# B1-B8 KPI names (8 principles)
B_PRINCIPLES_KEYS = [
    "B1_core_stability",
    "B2_support_foundation",
    "B3_3joint_coordination",
    "B4_pelvis_horizontal",
    "B5_knee_stability",
    "B6_ankle_mobility",
    "B7_upper_body_control",
    "B8_breathing_pattern",
]

# Major KPIs for selection priority (B1, B4, B2)
MAJOR_KPI_KEYS = [
    "B1_core_stability",
    "B4_pelvis_horizontal",
    "B2_support_foundation",
]

logger = logging.getLogger(__name__)


def _normalise_frame(frame: Mapping[str, Any]) -> Dict[str, Any]:
    """Return frame data with guaranteed keys and numeric fields."""
    score = frame.get("composite_score", frame.get("score", 0.0))
    angle = frame.get("angle_score", frame.get("angle", 0.0))
    stability = frame.get("stability_score", frame.get("stability", 0.0))
    frame_idx = frame.get("frame_idx", frame.get("index", 0))

    try:
        score_val = float(score)
    except (TypeError, ValueError):
        score_val = 0.0

    try:
        angle_val = float(angle)
    except (TypeError, ValueError):
        angle_val = 0.0

    try:
        stability_val = float(stability)
    except (TypeError, ValueError):
        stability_val = 0.0

    try:
        frame_idx_val = int(frame_idx)
    except (TypeError, ValueError):
        frame_idx_val = 0

    return {
        "frame_idx": frame_idx_val,
        "score": score_val,
        "angle_score": angle_val,
        "stability_score": stability_val,
        "source": dict(frame),
    }


def _score_tuple(frame: Mapping[str, Any]) -> tuple:
    """Return tuple used for ranking frames by quality."""
    return (
        frame["score"],
        frame.get("angle_score", 0.0),
        frame.get("stability_score", 0.0),
        -frame.get("frame_idx", 0),
    )


def _median_frame_idx(frames: Sequence[Mapping[str, Any]]) -> float:
    """Return median frame index (handles even/odd counts)."""
    if not frames:
        return 0.0
    sorted_idx = sorted(frame["frame_idx"] for frame in frames)
    mid = len(sorted_idx) // 2
    if len(sorted_idx) % 2 == 1:
        return float(sorted_idx[mid])
    return (sorted_idx[mid - 1] + sorted_idx[mid]) / 2.0


def _select_representative_frame(
    frames: Sequence[Mapping[str, Any]],
    session_mean: Optional[float] = None,
) -> Mapping[str, Any]:
    """
    Select representative frame: closest score to session mean, then middle index.
    """
    if not frames:
        return {"frame_idx": 0, "score": 0.0, "angle_score": 0.0, "stability_score": 0.0}

    if session_mean is None:
        session_mean = sum(frame["score"] for frame in frames) / len(frames)

    median_idx = _median_frame_idx(frames)

    def sort_key(frame: Mapping[str, Any]) -> tuple:
        score_diff = abs(frame["score"] - session_mean)
        idx_diff = abs(frame["frame_idx"] - median_idx)
        return (
            score_diff,
            idx_diff,
            -frame["score"],
            -frame.get("angle_score", 0.0),
            -frame.get("stability_score", 0.0),
        )

    return min(frames, key=sort_key)


def select_rep_frame_triplet(
    frame_scores: Sequence[Mapping[str, Any]],
    *,
    session_mean: Optional[float] = None,
) -> Dict[str, Dict[str, Any]]:
    """
    Pick best/worst/representative frames for a rep.

    Args:
        frame_scores: Iterable of per-frame metrics (frame_idx, score, optional metrics)
        session_mean: Session-level composite mean (Optional; improves representative pick)

    Returns:
        dict: {
            'best': {...},
            'worst': {...},
            'repr': {...}
        }
    """
    if not frame_scores:
        default = {"frame_idx": 0, "score": 0.0, "angle_score": 0.0, "stability_score": 0.0}
        return {frame_type: dict(default) for frame_type in FRAME_TYPES}

    normalised = [_normalise_frame(frame) for frame in frame_scores]

    best_frame = max(normalised, key=_score_tuple)
    worst_frame = min(normalised, key=_score_tuple)
    representative_frame = _select_representative_frame(normalised, session_mean=session_mean)

    return {
        "best": {k: best_frame[k] for k in ("frame_idx", "score", "angle_score", "stability_score")},
        "worst": {k: worst_frame[k] for k in ("frame_idx", "score", "angle_score", "stability_score")},
        "repr": {k: representative_frame[k] for k in ("frame_idx", "score", "angle_score", "stability_score")},
    }


def _sanitize(value: str) -> str:
    """Sanitise identifier for filenames/keys."""
    safe = re.sub(r"[^A-Za-z0-9_-]+", "-", value or "")
    safe = safe.strip("-")
    return safe or "unknown"


def build_frame_filename(session_id: str, rep_id: str, frame_type: str, suffix: str = "jpg") -> str:
    """Return local filename following naming convention."""
    if frame_type not in FRAME_TYPES:
        raise ValueError(f"Unsupported frame type '{frame_type}'. Expected one of {FRAME_TYPES}.")
    session_part = _sanitize(session_id)
    rep_part = _sanitize(rep_id)
    return f"{session_part}_{rep_part}_{frame_type}.{suffix}"


def build_s3_key(
    session_id: str,
    rep_id: str,
    frame_type: str,
    *,
    prefix: Optional[str] = None,
) -> str:
    """Return S3 object key for a frame image."""
    base = f"{_sanitize(session_id)}/{_sanitize(rep_id)}/{frame_type}.jpg"
    if prefix:
        trimmed = prefix.strip("/")
        if trimmed:
            return f"{trimmed}/{base}"
    return base


def build_session_summary_key(session_id: str, frame_type: str, *, prefix: Optional[str] = None) -> str:
    """Return S3 object key for session-level summary frame."""
    if frame_type not in FRAME_TYPES:
        raise ValueError(f"Unsupported frame type '{frame_type}'. Expected one of {FRAME_TYPES}.")
    base = f"{_sanitize(session_id)}/session_summary/{frame_type}.jpg"
    if prefix:
        trimmed = prefix.strip("/")
        if trimmed:
            return f"{trimmed}/{base}"
    return base


def upload_frame_image(
    s3_client: Any,
    bucket: str,
    session_id: str,
    rep_id: str,
    frame_type: str,
    file_path: Path,
    *,
    prefix: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> str:
    """
    Upload frame image to S3 using naming convention.

    Returns:
        S3 key used for the uploaded file.
    """
    if not isinstance(file_path, Path):
        file_path = Path(file_path)

    key = build_s3_key(session_id, rep_id, frame_type, prefix=prefix)

    extra_args: Dict[str, Any] = {"ContentType": "image/jpeg"}
    if metadata:
        meta = {str(k): str(v) for k, v in metadata.items()}
        extra_args["Metadata"] = meta

    s3_client.upload_file(str(file_path), bucket, key, ExtraArgs=extra_args)
    return key


def summarise_session_frames(
    rep_selections: Mapping[str, Mapping[str, Mapping[str, Any]]],
    *,
    strategy: str = "max_score",
) -> Dict[str, Dict[str, Any]]:
    """
    Derive session-level best/worst/repr frames from per-rep selections.

    Args:
        rep_selections: {rep_id: {'best': {...}, 'worst': {...}, 'repr': {...}}}
        strategy: Currently supports 'max_score' (best), 'min_score' (worst), 'closest_to_mean' (repr)

    Returns:
        dict with best/worst/repr selections referencing rep_id
    """
    if not rep_selections:
        placeholder = {"rep_id": "unknown", "frame_idx": 0, "score": 0.0}
        return {frame_type: dict(placeholder) for frame_type in FRAME_TYPES}

    def best_rep() -> tuple:
        return max(
            rep_selections.items(),
            key=lambda item: (
                item[1]["best"]["score"],
                item[1]["best"].get("angle_score", 0.0),
                item[1]["best"].get("stability_score", 0.0),
            ),
        )

    def worst_rep() -> tuple:
        return min(
            rep_selections.items(),
            key=lambda item: (
                item[1]["worst"]["score"],
                item[1]["worst"].get("angle_score", 0.0),
                item[1]["worst"].get("stability_score", 0.0),
            ),
        )

    all_scores = [
        selection["repr"]["score"]
        for selection in rep_selections.values()
        if selection.get("repr")
    ]
    session_mean = sum(all_scores) / len(all_scores) if all_scores else 0.0

    def repr_rep() -> tuple:
        return min(
            rep_selections.items(),
            key=lambda item: (
                abs(item[1]["repr"]["score"] - session_mean),
                item[1]["repr"].get("frame_idx", 0),
            ),
        )

    best_id, best_data = best_rep()
    worst_id, worst_data = worst_rep()
    repr_id, repr_data = repr_rep()

    return {
        "best": {**best_data["best"], "rep_id": best_id},
        "worst": {**worst_data["worst"], "rep_id": worst_id},
        "repr": {**repr_data["repr"], "rep_id": repr_id},
    }


# ========== Rep-level Selection Logic ==========


def _calculate_normalized_score(kpi_scores: Mapping[str, Any]) -> tuple[float, int, int]:
    """
    Calculate normalized score from KPI scores, excluding N/A values.

    Args:
        kpi_scores: Dict of {kpi_name: score_value}, where None/NaN/null represents N/A

    Returns:
        tuple: (normalized_score, valid_kpi_count, total_kpi_count)

    CRITICAL:
    - N/A values are None, float('nan'), or absent keys
    - normalized_score = sum(valid_kpis) / len(valid_kpis)
    - If all KPIs are N/A, normalized_score = 0.0
    """
    if not kpi_scores:
        return (0.0, 0, 0)

    total_kpi_count = len(kpi_scores)
    valid_scores = []

    for value in kpi_scores.values():
        if value is None:
            continue
        try:
            val = float(value)
            # Check for NaN
            if val != val:  # NaN != NaN is True
                continue
            valid_scores.append(val)
        except (TypeError, ValueError):
            # Invalid numeric value, treat as N/A
            continue

    valid_kpi_count = len(valid_scores)

    if valid_kpi_count == 0:
        return (0.0, 0, total_kpi_count)

    normalized_score = sum(valid_scores) / valid_kpi_count

    return (normalized_score, valid_kpi_count, total_kpi_count)


def _calculate_na_rate(valid_kpi_count: int, total_kpi_count: int) -> float:
    """
    Calculate N/A rate as percentage.

    Args:
        valid_kpi_count: Number of valid KPIs
        total_kpi_count: Total number of KPIs

    Returns:
        float: N/A rate (0.0 to 1.0)

    CRITICAL:
    - If total_kpi_count is 0, return 1.0 (100% N/A)
    - N/A rate = 1.0 - (valid_kpi_count / total_kpi_count)
    """
    if total_kpi_count == 0:
        return 1.0

    return 1.0 - (valid_kpi_count / total_kpi_count)


def _filter_valid_reps(
    reps: Sequence[Mapping[str, Any]],
    min_valid_kpi_ratio: float = 0.5,
) -> List[Dict[str, Any]]:
    """
    Filter reps with insufficient valid KPIs.

    Args:
        reps: List of rep dicts with kpi_scores
        min_valid_kpi_ratio: Minimum ratio of valid KPIs (default: 0.5 = 50%)

    Returns:
        List of reps with sufficient valid KPIs

    CRITICAL:
    - Reps with valid_kpi_count < total_kpi_count * min_valid_kpi_ratio are excluded
    - Adds 'normalized_score', 'na_rate', 'valid_kpi_count', 'total_kpi_count' to each rep
    """
    filtered_reps = []

    for rep in reps:
        kpi_scores = rep.get("kpi_scores", {})
        normalized_score, valid_kpi_count, total_kpi_count = _calculate_normalized_score(kpi_scores)
        na_rate = _calculate_na_rate(valid_kpi_count, total_kpi_count)

        # Check if rep meets minimum valid KPI threshold
        if total_kpi_count > 0 and valid_kpi_count < total_kpi_count * min_valid_kpi_ratio:
            # Insufficient valid KPIs, exclude this rep
            continue

        # Add computed fields to rep
        rep_dict = dict(rep)
        rep_dict["normalized_score"] = normalized_score
        rep_dict["na_rate"] = na_rate
        rep_dict["valid_kpi_count"] = valid_kpi_count
        rep_dict["total_kpi_count"] = total_kpi_count

        filtered_reps.append(rep_dict)

    return filtered_reps


def _tiebreak_key(rep: Mapping[str, Any]) -> tuple:
    """
    Generate tiebreak key for rep selection.

    Tiebreak order:
    1. N/A rate (lower is better)
    2. rep_number (earlier is better)

    Args:
        rep: Rep dict with na_rate and rep_number

    Returns:
        tuple: (na_rate, rep_number) for tiebreaking

    CRITICAL:
    - Lower tuple values are preferred (min() will select)
    - rep_number defaults to 0 if not present
    """
    return (rep.get("na_rate", 1.0), rep.get("rep_number", 0))


def select_representative_reps(
    reps: Sequence[Mapping[str, Any]],
    *,
    min_valid_kpi_ratio: float = 0.5,
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Select 3 representative reps (best/worst/repr) from multiple reps.

    What: From N reps, select best (highest score), worst (lowest score), and
          representative (closest to median score) reps.

    Why: Provide objective basis for overlay annotation and rep quality assessment.

    Design Decision:
    - N/A handling: Exclude N/A KPIs from score calculation, require >= 50% valid KPIs
    - Tiebreak: Lower N/A rate -> earlier rep_number
    - Representative: Closest to median normalized_score

    Args:
        reps: List of rep dicts, each with:
            - kpi_scores: {kpi_name: score_value}
            - rep_number: Rep sequence number
            - versions: {rules_version, thresholds_version, normalization_version}
        min_valid_kpi_ratio: Minimum ratio of valid KPIs (default: 0.5 = 50%)

    Returns:
        dict: {
            'best': rep_dict or None,
            'worst': rep_dict or None,
            'repr': rep_dict or None
        }

    CRITICAL:
    - If no reps pass the filter, all selections are None
    - normalized_score = sum(valid_kpis) / len(valid_kpis)
    - Tiebreak: N/A rate (lower) -> rep_number (earlier)
    - Representative: Median normalized_score, tiebreak same as best/worst
    """
    if not reps:
        return {"best": None, "worst": None, "repr": None}

    # Step 1: Filter reps with insufficient valid KPIs
    valid_reps = _filter_valid_reps(reps, min_valid_kpi_ratio=min_valid_kpi_ratio)

    if not valid_reps:
        # No reps passed the filter
        return {"best": None, "worst": None, "repr": None}

    # Step 2: Select best (highest normalized_score, tiebreak by N/A rate -> rep_number)
    best_rep = max(
        valid_reps,
        key=lambda r: (r["normalized_score"], -r["na_rate"], -r.get("rep_number", 0)),
    )

    # Step 3: Select worst (lowest normalized_score, tiebreak by N/A rate -> rep_number)
    worst_rep = min(
        valid_reps,
        key=lambda r: (r["normalized_score"], r["na_rate"], r.get("rep_number", 0)),
    )

    # Step 4: Select representative (closest to median normalized_score)
    scores = [r["normalized_score"] for r in valid_reps]
    median_score = statistics.median(scores)

    repr_rep = min(
        valid_reps,
        key=lambda r: (
            abs(r["normalized_score"] - median_score),
            r["na_rate"],
            r.get("rep_number", 0),
        ),
    )

    return {
        "best": best_rep,
        "worst": worst_rep,
        "repr": repr_rep,
    }


def build_rep_annotation(
    rep: Mapping[str, Any],
    selection_reason: str,
) -> Dict[str, Any]:
    """
    Build annotation data structure for selected rep.

    What: Create structured annotation for overlay display, including KPI values,
          classes, p-values, versions, and metadata.

    Why: Provide traceability and context for rep selection and quality assessment.

    Design Decision: Include all relevant metadata for overlay and audit trail.

    Args:
        rep: Selected rep dict with kpi_scores, versions, etc.
        selection_reason: One of "best", "worst", "repr"

    Returns:
        dict: {
            "kpi_values": {kpi_name: value, ...},
            "kpi_classes": {kpi_name: "A"|"B"|"C", ...},
            "kpi_p_values": {kpi_name: p_value, ...},
            "versions": {rules_version, thresholds_version, normalization_version},
            "metadata": {
                "na_rate": float,
                "valid_kpi_count": int,
                "total_kpi_count": int,
                "selection_reason": str,
                "rep_number": int
            }
        }

    CRITICAL:
    - kpi_classes and kpi_p_values may be empty if not available
    - versions must be present for traceability
    - metadata includes all selection-related info
    """
    kpi_scores = rep.get("kpi_scores", {})
    kpi_classes = rep.get("kpi_classes", {})
    kpi_p_values = rep.get("kpi_p_values", {})
    versions = rep.get("versions", {})

    # Extract metadata fields
    na_rate = rep.get("na_rate", 0.0)
    valid_kpi_count = rep.get("valid_kpi_count", 0)
    total_kpi_count = rep.get("total_kpi_count", 0)
    rep_number = rep.get("rep_number", 0)

    return {
        "kpi_values": dict(kpi_scores),
        "kpi_classes": dict(kpi_classes),
        "kpi_p_values": dict(kpi_p_values),
        "versions": dict(versions),
        "metadata": {
            "na_rate": na_rate,
            "valid_kpi_count": valid_kpi_count,
            "total_kpi_count": total_kpi_count,
            "selection_reason": selection_reason,
            "rep_number": rep_number,
        },
    }


# ========== Stage 1: KPI Extraction from Evaluator Output ==========


def _is_na_value(value: Any) -> bool:
    """
    Check if a value represents N/A.

    What: Detect N/A values (None, NaN, missing keys).
    Why: Unified N/A detection for KPI extraction.
    Design Decision: None, float('nan'), and missing keys are all N/A. 0.0 is valid.

    Args:
        value: KPI value to check

    Returns:
        bool: True if N/A, False otherwise

    CRITICAL:
    - None is N/A
    - float('nan') is N/A (using math.isnan)
    - 0.0 is NOT N/A (explicit valid value)
    """
    if value is None:
        return True

    # Check for NaN
    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except (TypeError, ValueError):
        pass

    return False


def extract_frame_kpis(
    frames_data: Sequence[Mapping[str, Any]],
    phase: str = "eccentric",
) -> List[Dict[str, Any]]:
    """
    Extract B1-B8 KPI vectors from evaluator output frames.

    What: Extract KPI values from B_principles structure for each frame.
    Why: Provide clean KPI vectors for best/worst/repr selection algorithms.
    Design Decision: N/A values (None, NaN, missing keys) are preserved as None.
                     0.0 is treated as a valid value. Major KPI absence triggers warning.

    Args:
        frames_data: List of frame dicts with B_principles structure
                     [{frame_idx: int, B_principles: {phase: {B1_...: float, ...}}}, ...]
        phase: Phase to extract ('eccentric' or 'concentric')

    Returns:
        List[Dict]: [{
            'frame_idx': int,
            'kpis': {B1_core_stability: float|None, B2_...: float|None, ...},
            'na_count': int,
            'na_rate': float (0.0-1.0),
            'major_kpis_missing': bool
        }, ...]

    Raises:
        ValueError: If all KPIs are N/A for a frame

    CRITICAL:
    - N/A values: None, float('nan'), or missing keys
    - 0.0 is valid (not N/A)
    - Major KPIs: B1, B4, B2
    - Overall na_rate > 0.5 triggers warning log
    """
    if not frames_data:
        return []

    result = []
    total_frames = len(frames_data)
    overall_na_count = 0
    total_kpis = len(B_PRINCIPLES_KEYS)

    for frame_data in frames_data:
        frame_idx = frame_data.get("frame_idx", 0)
        b_principles = frame_data.get("B_principles", {})
        phase_data = b_principles.get(phase, {})

        # Extract KPIs
        kpis: Dict[str, Optional[float]] = {}
        na_count = 0

        for kpi_key in B_PRINCIPLES_KEYS:
            value = phase_data.get(kpi_key)

            # Check if N/A
            if _is_na_value(value):
                kpis[kpi_key] = None
                na_count += 1
            else:
                # Valid value (including 0.0)
                try:
                    kpis[kpi_key] = float(value)
                except (TypeError, ValueError):
                    # Cannot convert to float, treat as N/A
                    kpis[kpi_key] = None
                    na_count += 1

        # Check if all KPIs are N/A
        if na_count == total_kpis:
            raise ValueError(
                f"All KPIs are N/A for frame {frame_idx} (phase={phase}). "
                "Cannot proceed with frame selection."
            )

        # Check if major KPIs are all missing
        major_kpis_missing = all(kpis.get(key) is None for key in MAJOR_KPI_KEYS)

        # Calculate N/A rate
        na_rate = na_count / total_kpis

        result.append(
            {
                "frame_idx": frame_idx,
                "kpis": kpis,
                "na_count": na_count,
                "na_rate": na_rate,
                "major_kpis_missing": major_kpis_missing,
            }
        )

        overall_na_count += na_count

    # Calculate overall N/A rate
    overall_na_rate = overall_na_count / (total_frames * total_kpis) if total_frames > 0 else 0.0

    # Warning if overall N/A rate > 50%
    if overall_na_rate > 0.5:
        logger.warning(
            f"High N/A rate detected: {overall_na_rate:.2%} "
            f"({overall_na_count}/{total_frames * total_kpis} KPIs are N/A). "
            "Frame selection quality may be degraded."
        )

    return result


# ========== Stage 4: Composite Score Calculation ==========

# Default equal weights for B1-B8 (1/8 each)
DEFAULT_WEIGHTS = {key: 1.0 / len(B_PRINCIPLES_KEYS) for key in B_PRINCIPLES_KEYS}


def calculate_composite_score(
    kpis: Mapping[str, Optional[float]],
    weights: Optional[Mapping[str, float]] = None,
) -> float:
    """
    Calculate weighted composite score from KPI values.

    What: Compute weighted average of KPI values, excluding N/A.
    Why: Provide tiebreak mechanism and overall quality metric for frame selection.
    Design Decision: Default equal weights (1/8), customizable. N/A values excluded.
                     All N/A returns 0.0. Weights are normalized to sum to 1.0.

    Args:
        kpis: Dict of {kpi_name: value}, where None represents N/A
        weights: Optional custom weights dict. If None, uses equal weights (1/8 each).

    Returns:
        float: Composite score (weighted average of valid KPIs)

    CRITICAL:
    - N/A values (None) are excluded from calculation
    - Weights are auto-normalized to sum to 1.0 for valid KPIs
    - All N/A returns 0.0
    - 0.0 is a valid KPI value (not N/A)
    """
    if not kpis:
        return 0.0

    # Use default weights if not provided
    if weights is None:
        weights = DEFAULT_WEIGHTS

    # Extract valid KPIs (non-None)
    valid_kpis = []
    valid_weights = []

    for key, value in kpis.items():
        if value is not None:  # Exclude N/A
            try:
                val = float(value)
                # Check for NaN (should not happen if extract_frame_kpis worked correctly)
                if not math.isnan(val):
                    valid_kpis.append(val)
                    # Get weight for this KPI (default to equal weight if not in weights dict)
                    weight = weights.get(key, 1.0 / len(B_PRINCIPLES_KEYS))
                    valid_weights.append(weight)
            except (TypeError, ValueError):
                # Cannot convert to float, skip
                continue

    # All N/A case
    if not valid_kpis:
        return 0.0

    # Normalize weights to sum to 1.0
    total_weight = sum(valid_weights)
    if total_weight == 0.0:
        # Fallback to equal weights
        normalized_weights = [1.0 / len(valid_kpis)] * len(valid_kpis)
    else:
        normalized_weights = [w / total_weight for w in valid_weights]

    # Calculate weighted score
    score = sum(kpi * weight for kpi, weight in zip(valid_kpis, normalized_weights))

    return score
