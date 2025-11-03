"""
Preview analytics for threshold adjustments.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .models import ThreeTierBands


def classify_value(value: Optional[float], bands: ThreeTierBands) -> str:
    """Classify a numeric value into OK/ATTN/NG (half-open bands)."""
    if value is None or math.isnan(value):
        return "NA"
    if bands.ok.contains(value):
        return "OK"
    if bands.attn.contains(value):
        return "ATTN"
    return "NG"


@dataclass
class RepresentativeSample:
    rep_id: str
    old_band: str
    new_band: str
    old_value: Optional[float]
    new_value: Optional[float]
    score_delta: float


@dataclass
class PreviewResult:
    reclassified_count: int
    reclassified_rate: float
    impact_count: int
    representatives: Dict[str, List[RepresentativeSample]]


def analyse_reclassification(
    records: Sequence[Mapping[str, object]],
    old_bands: ThreeTierBands,
    new_bands: ThreeTierBands,
    *,
    side: Optional[str] = None,
) -> PreviewResult:
    """
    Calculate reclassification metrics and representatives.

    Each record is expected to expose:
      - rep_id
      - old_value
      - new_value (optional; falls back to old_value)
    """
    samples_up: List[RepresentativeSample] = []
    samples_down: List[RepresentativeSample] = []
    reclassified = 0
    valid_records = 0

    for record in records:
        rep_id = str(record.get("rep_id"))
        old_val = record.get("old_value", record.get("value"))
        new_val = record.get("new_value", old_val)

        old_band = classify_value(
            float(old_val) if old_val is not None else None,
            old_bands,
        )
        new_band = classify_value(
            float(new_val) if new_val is not None else None,
            new_bands,
        )

        if old_band == "NA" or new_band == "NA":
            continue

        valid_records += 1
        score_delta = float(new_val) - float(old_val) if old_val is not None and new_val is not None else 0.0

        if old_band != new_band:
            reclassified += 1
            sample = RepresentativeSample(
                rep_id=rep_id,
                old_band=old_band,
                new_band=new_band,
                old_value=float(old_val) if old_val is not None else None,
                new_value=float(new_val) if new_val is not None else None,
                score_delta=score_delta,
            )
            if score_delta >= 0:
                samples_up.append(sample)
            else:
                samples_down.append(sample)

    reclassified_rate = (reclassified / valid_records) if valid_records else 0.0

    samples_up.sort(key=lambda item: abs(item.score_delta), reverse=True)
    samples_down.sort(key=lambda item: abs(item.score_delta), reverse=True)

    return PreviewResult(
        reclassified_count=reclassified,
        reclassified_rate=reclassified_rate,
        impact_count=reclassified,
        representatives={
            "upshift": samples_up[:3],
            "downshift": samples_down[:3],
        },
    )
