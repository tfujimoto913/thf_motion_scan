"""
Purpose: Detect repetitions for single-leg squat using knee flexion angles.
Responsibility: Smooth knee angle trajectory and extract rep start/end frames.
Dependencies: numpy
Created: 2024-03-08 by Codex
Decision Log: Phase 1 pipeline bootstrap (rep segmentation)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import math
import numpy as np

# MediaPipe pose landmark indices
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28


@dataclass
class AngleSample:
    """Container for a single frame's knee angle measurement."""

    frame_index: int
    angle_deg: float
    leg: str  # 'left' or 'right'


def _get_landmark(
    landmarks: Sequence[Optional[Dict[str, float]]], index: int, min_visibility: float
) -> Optional[Dict[str, float]]:
    if index < 0 or index >= len(landmarks):
        return None
    landmark = landmarks[index]
    if landmark is None:
        return None
    if landmark.get("visibility", 0.0) < min_visibility:
        return None
    return landmark


def _compute_knee_angle(
    hip: Dict[str, float], knee: Dict[str, float], ankle: Dict[str, float]
) -> Optional[float]:
    """Return knee flexion angle in degrees (0-180) or None."""
    hip_vec = np.array([hip["x"], hip["y"], hip.get("z", 0.0)], dtype=np.float64)
    knee_vec = np.array([knee["x"], knee["y"], knee.get("z", 0.0)], dtype=np.float64)
    ankle_vec = np.array([ankle["x"], ankle["y"], ankle.get("z", 0.0)], dtype=np.float64)

    vec_thigh = hip_vec - knee_vec
    vec_shank = ankle_vec - knee_vec

    norm_thigh = np.linalg.norm(vec_thigh)
    norm_shank = np.linalg.norm(vec_shank)
    if norm_thigh == 0 or norm_shank == 0:
        return None

    cos_angle = float(np.dot(vec_thigh, vec_shank) / (norm_thigh * norm_shank))
    cos_angle = max(-1.0, min(1.0, cos_angle))
    angle_rad = math.acos(cos_angle)
    return math.degrees(angle_rad)


def _extract_knee_angles(
    frames: Iterable[Dict[str, Any]],
    *,
    min_visibility: float = 0.5,
) -> List[AngleSample]:
    samples: List[AngleSample] = []

    for frame in frames:
        landmarks = frame.get("landmarks")
        if not landmarks:
            continue

        left = (
            _get_landmark(landmarks, LEFT_HIP, min_visibility),
            _get_landmark(landmarks, LEFT_KNEE, min_visibility),
            _get_landmark(landmarks, LEFT_ANKLE, min_visibility),
        )
        right = (
            _get_landmark(landmarks, RIGHT_HIP, min_visibility),
            _get_landmark(landmarks, RIGHT_KNEE, min_visibility),
            _get_landmark(landmarks, RIGHT_ANKLE, min_visibility),
        )

        left_angle = None
        right_angle = None
        if all(part is not None for part in left):
            left_angle = _compute_knee_angle(left[0], left[1], left[2])
        if all(part is not None for part in right):
            right_angle = _compute_knee_angle(right[0], right[1], right[2])

        if left_angle is None and right_angle is None:
            continue

        if left_angle is not None and right_angle is not None:
            if left_angle <= right_angle:
                chosen = ("left", left_angle)
            else:
                chosen = ("right", right_angle)
        elif left_angle is not None:
            chosen = ("left", left_angle)
        else:
            chosen = ("right", right_angle)

        samples.append(
            AngleSample(
                frame_index=int(frame.get("frame", len(samples))),
                angle_deg=float(chosen[1]),
                leg=chosen[0],
            )
        )

    return samples


def _savgol_coefficients(window_size: int, poly_order: int) -> np.ndarray:
    half_window = (window_size - 1) // 2
    order_range = range(poly_order + 1)
    # Construct Vandermonde matrix for positions -half_window ... +half_window
    A = np.array(
        [[k ** i for i in order_range] for k in range(-half_window, half_window + 1)],
        dtype=np.float64,
    )
    # Compute pseudoinverse once; central smoothing uses row for derivative order 0
    AtA_inv = np.linalg.pinv(A.T @ A)
    coeffs = A @ (AtA_inv @ np.eye(poly_order + 1)[:, 0])
    return coeffs


def _savgol_filter(values: Sequence[float], window_size: int, poly_order: int) -> np.ndarray:
    data = np.asarray(values, dtype=np.float64)
    n = data.size
    if n == 0:
        return data

    if window_size % 2 == 0:
        window_size += 1
    if window_size > n:
        window_size = n if n % 2 == 1 else n - 1
    if window_size < 3:
        return data.copy()
    if poly_order >= window_size:
        poly_order = window_size - 1
    if poly_order < 0:
        poly_order = 0

    half_window = (window_size - 1) // 2
    coeffs = _savgol_coefficients(window_size, poly_order)

    if half_window > 0:
        first_vals = data[0] - np.abs(data[1 : half_window + 1][::-1] - data[0])
        last_vals = data[-1] + np.abs(data[-half_window - 1 : -1][::-1] - data[-1])
        padded = np.concatenate((first_vals, data, last_vals))
    else:
        padded = data

    smoothed = np.convolve(coeffs[::-1], padded, mode="valid")
    return smoothed


def _compute_primary_score(
    min_angle: float, down_threshold: float, up_threshold: float
) -> float:
    if up_threshold <= down_threshold:
        return 0.0
    depth = up_threshold - min_angle
    span = up_threshold - down_threshold
    score = (depth / span) * 100.0
    return float(max(0.0, min(100.0, score)))


def detect_single_leg_squat_reps(
    landmark_frames: Sequence[Dict[str, Any]],
    *,
    fps: float,
    down_threshold: float = 120.0,
    up_threshold: float = 160.0,
    window_size: int = 21,
    poly_order: int = 3,
    min_visibility: float = 0.5,
    min_duration_frames: int = 5,
) -> Dict[str, Any]:
    """
    Detect repetitions for single-leg squat motion.

    Returns:
        {
          "series": [{"frame": int, "angle_raw": float, "angle_smooth": float, "leg": str}, ...],
          "reps": [
            {
              "rep_index": int,
              "start_frame": int,
              "end_frame": int,
              "apex_frame": int,
              "start_time": float,
              "end_time": float,
              "apex_time": float,
              "start_angle": float,
              "end_angle": float,
              "min_angle": float,
              "score_primary": float,
              "dominant_leg": str,
            },
            ...
          ]
        }
    """
    samples = _extract_knee_angles(landmark_frames, min_visibility=min_visibility)
    if not samples:
        return {"series": [], "reps": []}

    raw_angles = np.array([sample.angle_deg for sample in samples], dtype=np.float64)
    smoothed_angles = _savgol_filter(raw_angles, window_size, poly_order)

    series = [
        {
            "frame": samples[idx].frame_index,
            "angle_raw": float(raw_angles[idx]),
            "angle_smooth": float(smoothed_angles[idx]),
            "leg": samples[idx].leg,
        }
        for idx in range(len(samples))
    ]

    reps: List[Dict[str, Any]] = []

    state = "idle"
    last_high_idx: Optional[int] = None
    start_idx: Optional[int] = None
    min_idx: Optional[int] = None
    min_angle: Optional[float] = None

    for idx, angle in enumerate(smoothed_angles):
        is_high = angle >= up_threshold
        is_low = angle <= down_threshold

        if is_high:
            last_high_idx = idx

        if state == "idle":
            if is_low:
                start_idx = last_high_idx if last_high_idx is not None else idx
                min_idx = idx
                min_angle = float(angle)
                state = "in_rep"
        elif state == "in_rep":
            if angle < (min_angle or angle):
                min_idx = idx
                min_angle = float(angle)
            if is_high and start_idx is not None and min_idx is not None:
                rep_start = samples[start_idx].frame_index
                rep_end = samples[idx].frame_index
                apex_frame = samples[min_idx].frame_index
                if rep_end - rep_start >= max(1, min_duration_frames - 1):
                    reps.append(
                        {
                            "rep_index": len(reps),
                            "start_frame": rep_start,
                            "end_frame": rep_end,
                            "apex_frame": apex_frame,
                            "start_time": float(rep_start / fps) if fps else 0.0,
                            "end_time": float(rep_end / fps) if fps else 0.0,
                            "apex_time": float(apex_frame / fps) if fps else 0.0,
                            "start_angle": float(smoothed_angles[start_idx]),
                            "end_angle": float(angle),
                            "min_angle": float(min_angle),
                            "score_primary": _compute_primary_score(
                                float(min_angle), down_threshold, up_threshold
                            ),
                            "dominant_leg": samples[min_idx].leg,
                        }
                    )
                state = "idle"
                start_idx = None
                min_idx = None
                min_angle = None

    return {"series": series, "reps": reps}


__all__ = ["detect_single_leg_squat_reps"]
