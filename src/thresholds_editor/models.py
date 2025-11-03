"""
Data models for the half-open band representation used by the Threshold Editor.
"""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional


@dataclass(frozen=True)
class Band:
    """Single half-open band boundary definition."""

    lower: float
    upper: float

    def contains(self, value: float) -> bool:
        return self.lower <= value < self.upper


@dataclass(frozen=True)
class ThreeTierBands:
    """Three-tier half-open band definition (OK / ATTENTION / NG)."""

    ok: Band
    attn: Band
    ng: Band

    def validate(self) -> None:
        assert self.ok.lower <= self.ok.upper, "OK band invalid"
        assert self.ok.upper == self.attn.lower, "Bands must be contiguous"
        assert self.attn.upper == self.ng.lower, "Bands must be contiguous"

    def as_dict(self) -> Dict[str, List[float]]:
        return {
            "ok": [self.ok.lower, self.ok.upper],
            "attn": [self.attn.lower, self.attn.upper],
            "ng": [self.ng.lower, self.ng.upper],
        }


@dataclass
class MetricThreshold:
    """Per-metric threshold configuration."""

    unit: str
    banding: str
    by_side: bool = False
    values: Mapping[str, ThreeTierBands] = field(default_factory=dict)

    def get_bands(self, side: Optional[str] = None) -> ThreeTierBands:
        if self.by_side:
            key = side or "left"
        else:
            key = "default"
        return self.values[key]

    def update_bands(self, bands: ThreeTierBands, *, side: Optional[str] = None) -> None:
        if self.by_side:
            key = side or "left"
        else:
            key = "default"
        if isinstance(self.values, dict):
            self.values[key] = bands
        else:  # pragma: no cover - defensive (Mapping may not be mutable)
            temp = dict(self.values)
            temp[key] = bands
            self.values = temp

    def serialize(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "unit": self.unit,
            "banding": self.banding,
            "by_side": self.by_side,
        }
        if self.by_side:
            payload.update(
                {
                    "left": self.values["left"].as_dict(),
                    "right": self.values["right"].as_dict(),
                }
            )
        else:
            payload.update(self.values["default"].as_dict())
        return payload


@dataclass
class ThresholdDocument:
    """Root document for schema_version 2.0 thresholds."""

    schema_version: str
    tests: Mapping[str, Dict[str, MetricThreshold]]
    versions: Optional[Mapping[str, str]] = None

    def get_metric(self, test: str, metric: str) -> MetricThreshold:
        return self.tests[test][metric]

    def to_dict(self) -> Dict[str, object]:
        return serialize_threshold_document(self)


def load_threshold_document(payload: Mapping[str, object]) -> ThresholdDocument:
    schema_version = str(payload.get("schema_version", "2.0"))
    versions = payload.get("versions")
    tests_payload = payload.get("tests", {})
    tests: Dict[str, Dict[str, MetricThreshold]] = {}

    for test_name, test_block in tests_payload.items():
        metrics_block = test_block.get("metrics", {})
        metric_map: Dict[str, MetricThreshold] = {}
        for metric_key, metric_payload in metrics_block.items():
            unit = metric_payload["unit"]
            banding = metric_payload.get("banding", "three_tier_half_open")
            by_side = bool(metric_payload.get("by_side", False))

            def _bands_from_dict(obj: Mapping[str, List[float]]) -> ThreeTierBands:
                bands = ThreeTierBands(
                    ok=Band(*obj["ok"]),
                    attn=Band(*obj["attn"]),
                    ng=Band(*obj["ng"]),
                )
                bands.validate()
                return bands

            if by_side:
                values = {
                    "left": _bands_from_dict(metric_payload["left"]),
                    "right": _bands_from_dict(metric_payload["right"]),
                }
            else:
                values = {
                    "default": _bands_from_dict(
                        {
                            "ok": metric_payload["ok"],
                            "attn": metric_payload["attn"],
                            "ng": metric_payload["ng"],
                        }
                    )
                }

            metric_map[metric_key] = MetricThreshold(
                unit=unit,
                banding=banding,
                by_side=by_side,
                values=values,
            )
        tests[test_name] = metric_map

    return ThresholdDocument(schema_version=schema_version, tests=tests, versions=versions)


def serialize_threshold_document(doc: ThresholdDocument) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "schema_version": doc.schema_version,
        "tests": {},
    }
    if doc.versions:
        payload["versions"] = dict(doc.versions)

    for test_name, metrics in doc.tests.items():
        metric_payload: Dict[str, object] = {}
        for metric_key, metric in metrics.items():
            metric_payload[metric_key] = metric.serialize()
        payload["tests"][test_name] = {"metrics": metric_payload}

    return payload


def load_document_from_file(path: Path) -> ThresholdDocument:
    data = json.loads(path.read_text(encoding="utf-8"))
    return load_threshold_document(data)


def save_document_to_file(doc: ThresholdDocument, path: Path) -> None:
    payload = serialize_threshold_document(doc)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
