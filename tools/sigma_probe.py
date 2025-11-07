#!/usr/bin/env python3
"""
Purpose: Compute sigma stability metrics for the 9-cell capture experiment.
Responsibility:
  - Load rep-level outputs and environmental metadata
  - Aggregate B1/B4 statistics per (distance, resolution, illumination) cell
  - Emit sigma_table.csv, heatmaps, and summary.md for downstream review
Dependencies: numpy, pandas, matplotlib
Created: 2025-11-05 by Codex

CRITICAL:
  - Requires metadata CSV with rep_id mappings to the 9 cell definitions
  - Input rep results must expose B1/B4 metrics or evaluation_detail with B_principles
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - import guard
    import matplotlib  # type: ignore[import-not-found]

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt  # type: ignore[import-not-found]
except Exception:  # ModuleNotFoundError or backend issues
    matplotlib = None  # type: ignore[assignment]
    plt = None  # type: ignore[assignment]


CELL_DEFINITIONS: List[Tuple[str, str, str]] = [
    ("near", "low", "low"),
    ("near", "medium", "medium"),
    ("near", "high", "high"),
    ("mid", "low", "medium"),
    ("mid", "medium", "high"),
    ("mid", "high", "medium"),
    ("far", "low", "high"),
    ("far", "medium", "medium"),
    ("far", "high", "low"),
]

CELL_ID_ORDER = [
    "near_low",
    "near_medium",
    "near_high",
    "mid_low",
    "mid_medium",
    "mid_high",
    "far_low",
    "far_medium",
    "far_high",
]


@dataclass(frozen=True)
class SigmaConfig:
    rep_results: List[Path]
    metadata_path: Path
    output_dir: Path
    artifact_sha: str
    generated_at: str


def parse_args(argv: Optional[Sequence[str]] = None) -> SigmaConfig:
    parser = argparse.ArgumentParser(
        prog="sigma-probe",
        description="Compute sigma (B1/B4 stability) metrics for 9 cell experiment.",
    )
    parser.add_argument(
        "--rep-results",
        required=True,
        nargs="+",
        help="Path(s) to rep_result files (JSON or JSONL). Directories are scanned recursively.",
    )
    parser.add_argument(
        "--metadata",
        required=True,
        help="CSV with columns rep_id,distance,resolution,illumination[,session_id].",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to write sigma_table.csv, heatmaps, and summary.md.",
    )
    parser.add_argument(
        "--artifact-sha",
        default="unknown",
        help="Artifact SHA recorded in summary & sigma table metadata.",
    )
    parser.add_argument(
        "--timestamp",
        default=None,
        help="ISO8601 timestamp override. Defaults to current UTC time.",
    )

    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    generated_at = args.timestamp or datetime.now(timezone.utc).isoformat()

    rep_paths: List[Path] = []
    for entry in args.rep_results:
        path = Path(entry).resolve()
        if path.is_dir():
            for candidate in path.rglob("*.json*"):
                rep_paths.append(candidate)
        else:
            rep_paths.append(path)

    if not rep_paths:
        raise FileNotFoundError("No rep_result files found for provided --rep-results argument.")

    return SigmaConfig(
        rep_results=rep_paths,
        metadata_path=Path(args.metadata).resolve(),
        output_dir=output_dir,
        artifact_sha=args.artifact_sha,
        generated_at=generated_at,
    )


def load_metadata(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required_cols = {"rep_id", "distance", "resolution", "illumination"}
        missing = required_cols - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Metadata CSV missing required columns: {', '.join(sorted(missing))}")

        metadata: Dict[str, Dict[str, str]] = {}
        for row in reader:
            rep_id = (row.get("rep_id") or "").strip()
            if not rep_id:
                continue
            distance = (row.get("distance") or "").strip().lower()
            resolution = (row.get("resolution") or "").strip().lower()
            illumination = (row.get("illumination") or "").strip().lower()
            metadata[rep_id] = {
                "distance": distance,
                "resolution": resolution,
                "illumination": illumination,
            }

    if not metadata:
        raise ValueError("Metadata CSV contains no rows.")
    return metadata


def _read_json_file(path: Path) -> Iterable[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        for idx, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Failed parsing line {idx} of {path}: {exc}") from exc
    else:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed parsing {path}: {exc}") from exc
        if isinstance(payload, list):
            yield from payload
        else:
            yield payload


def _extract_principle_from_evaluation(evaluation: dict, metric_name: str) -> Optional[float]:
    """
    Extract metric from evaluation.B_principles (mean across phases).
    """
    if not isinstance(evaluation, dict):
        return None
    principles = evaluation.get("B_principles")
    if not isinstance(principles, dict):
        return None

    values: List[float] = []
    for phase in ("eccentric", "concentric"):
        phase_dict = principles.get(phase)
        if not isinstance(phase_dict, dict):
            continue
        value = phase_dict.get(metric_name)
        if isinstance(value, (int, float)) and not math.isnan(value):
            values.append(float(value))
    if not values:
        return None
    return float(statistics.mean(values))


def _extract_metric(rep: dict, metric_key: str) -> Optional[float]:
    # 1) Direct metrics dictionary
    metrics = rep.get("metrics")
    if isinstance(metrics, dict):
        value = metrics.get(metric_key)
        if isinstance(value, (int, float)) and not math.isnan(value):
            return float(value)

    # 2) evaluation_detail (preferred)
    evaluation_detail = rep.get("evaluation_detail") or rep.get("evaluation")
    if isinstance(evaluation_detail, dict):
        return _extract_principle_from_evaluation(evaluation_detail, metric_key)

    # 3) fallback: validation metrics (legacy)
    validation = rep.get("validation")
    if isinstance(validation, dict):
        metrics_field = validation.get("metrics")
        if isinstance(metrics_field, dict):
            value = metrics_field.get(metric_key)
            if isinstance(value, (int, float)):
                return float(value)

    return None


def load_rep_results(rep_paths: Iterable[Path]) -> List[dict]:
    records: List[dict] = []
    for path in rep_paths:
        for payload in _read_json_file(path):
            if not isinstance(payload, dict):
                continue
            record = payload.copy()
            record["_source_file"] = str(path)
            records.append(record)

    if not records:
        raise ValueError("No rep results loaded.")

    processed: List[dict] = []
    missing_metrics: List[str] = []
    for record in records:
        rep_id = record.get("rep_id")
        session_id = record.get("session_id")
        if not rep_id or not session_id:
            continue
        b1 = _extract_metric(record, "B1_core_stability")
        b4 = _extract_metric(record, "B4_pelvis_horizontal")
        if b1 is None or b4 is None:
            missing_metrics.append(str(rep_id))
            continue
        validation = record.get("validation")
        validation_state = None
        if isinstance(validation, dict):
            validation_state = validation.get("state")
        processed.append(
            {
                "rep_id": rep_id,
                "session_id": session_id,
                "validation_state": (validation_state or "UNKNOWN").upper(),
                "B1_core_stability": float(b1),
                "B4_pelvis_horizontal": float(b4),
            }
        )

    if missing_metrics:
        raise ValueError(
            "Unable to extract B1/B4 metrics for rep_ids: "
            + ", ".join(missing_metrics[:10])
            + ("..." if len(missing_metrics) > 10 else "")
        )

    if not processed:
        raise ValueError("Rep results missing required keys rep_id/session_id.")
    return processed


def compute_sigma_table(rep_records: List[dict], metadata_map: Dict[str, Dict[str, str]]) -> List[Dict[str, object]]:
    # Aggregate per cell
    aggregates: Dict[Tuple[str, str, str], Dict[str, List]] = {}

    for record in rep_records:
        meta = metadata_map.get(record["rep_id"])
        if not meta:
            continue
        distance = meta["distance"]
        resolution = meta["resolution"]
        illumination = meta["illumination"]

        cell_key = (distance, resolution, illumination)
        entry = aggregates.setdefault(
            cell_key,
            {
                "rep_ids": [],
                "B1_values": [],
                "B4_values": [],
                "validation_states": [],
            },
        )
        entry["rep_ids"].append(record["rep_id"])
        entry["B1_values"].append(record["B1_core_stability"])
        entry["B4_values"].append(record["B4_pelvis_horizontal"])
        entry["validation_states"].append(record["validation_state"])

    results: List[Dict[str, object]] = []
    expected_map = {(dist, res): illum for dist, res, illum in CELL_DEFINITIONS}

    for distance, resolution in [("near", "low"), ("near", "medium"), ("near", "high"),
                                 ("mid", "low"), ("mid", "medium"), ("mid", "high"),
                                 ("far", "low"), ("far", "medium"), ("far", "high")]:
        illumination = expected_map[(distance, resolution)]
        key = (distance, resolution, illumination)
        entry = aggregates.get(key, {
            "rep_ids": [],
            "B1_values": [],
            "B4_values": [],
            "validation_states": [],
        })

        b1_values = entry["B1_values"]
        b4_values = entry["B4_values"]
        sample_size = len(entry["rep_ids"])

        if sample_size:
            b1_mean = float(statistics.mean(b1_values))
            b4_mean = float(statistics.mean(b4_values))
            b1_std = float(statistics.stdev(b1_values)) if sample_size > 1 else 0.0
            b4_std = float(statistics.stdev(b4_values)) if sample_size > 1 else 0.0
            b1_outlier_rate = _compute_outlier_rate(b1_values)
            b4_outlier_rate = _compute_outlier_rate(b4_values)
            validation_series = [state.upper() for state in entry["validation_states"]]
            bcr = float(sum(state in {"WARN", "ERROR"} for state in validation_series) / sample_size)
        else:
            b1_mean = b4_mean = b1_std = b4_std = 0.0
            b1_outlier_rate = b4_outlier_rate = 0.0
            bcr = 0.0

        results.append(
            {
                "cell_id": f"{distance}_{resolution}",
                "distance": distance,
                "resolution": resolution,
                "illumination": illumination,
                "sample_size": sample_size,
                "B1_mean": b1_mean,
                "B1_std": b1_std,
                "B1_outlier_rate": b1_outlier_rate,
                "B4_mean": b4_mean,
                "B4_std": b4_std,
                "B4_outlier_rate": b4_outlier_rate,
                "bcr": bcr,
                "meets_min_samples": sample_size >= 15,
                "notes": "" if sample_size >= 15 else "N<15",
            }
        )

    return results


def _compute_outlier_rate(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = float(statistics.mean(values))
    std = float(statistics.stdev(values))
    if std == 0.0:
        return 0.0
    outliers = [abs(v - mean) > 2 * std for v in values]
    return float(sum(outliers) / len(values))


def _make_heatmap(
    sigma_table: List[Dict[str, object]],
    value_column: str,
    output_path: Path,
    title: str,
    cmap: str = "viridis",
) -> None:
    lookup = {
        (row["distance"], row["resolution"]): row.get(value_column)
        for row in sigma_table
    }
    data_matrix: List[List[Optional[float]]] = []
    for distance in ["near", "mid", "far"]:
        row_values: List[Optional[float]] = []
        for resolution in ["low", "medium", "high"]:
            value = lookup.get((distance, resolution))
            row_values.append(float(value) if isinstance(value, (int, float)) else None)
        data_matrix.append(row_values)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if plt is None:
        _make_heatmap_pillow(data_matrix, output_path, title)
        return

    try:
        import numpy as _np  # type: ignore  # optional dependency when matplotlib is available
    except Exception:
        _make_heatmap_pillow(data_matrix, output_path, title)
        return

    data = _np.array(
        [[float("nan") if v is None else v for v in row] for row in data_matrix], dtype=float
    )

    fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
    heatmap = ax.imshow(data, cmap=cmap, aspect="auto")

    ax.set_xticks(range(3))
    ax.set_xticklabels(["low", "medium", "high"], fontsize=10)
    ax.set_yticks(range(3))
    ax.set_yticklabels(["near", "mid", "far"], fontsize=10)
    ax.set_title(title, fontsize=12, fontweight="bold")

    for i in range(3):
        for j in range(3):
            val = data[i, j]
            display = "N/A" if math.isnan(val) else f"{val:.2f}"
            ax.text(j, i, display, ha="center", va="center", color="white", fontsize=9)

    cbar = fig.colorbar(heatmap, ax=ax)
    cbar.ax.set_ylabel(value_column, rotation=-90, va="bottom")

    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def _make_heatmap_pillow(data: List[List[Optional[float]]], output_path: Path, title: str) -> None:
    from PIL import Image, ImageDraw, ImageFont  # Imported lazily to avoid hard dependency when unused

    width, height = 600, 400
    cell_width = width // 3
    cell_height = (height - 60) // 3
    img = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(img)

    # Simple gradient coloring based on normalized values
    flat_values = [v for row in data for v in row if isinstance(v, (int, float))]
    if flat_values:
        min_val = min(flat_values)
        max_val = max(flat_values)
    else:
        min_val = 0.0
        max_val = 1.0
    span = max(max_val - min_val, 1e-6)

    for i in range(3):
        for j in range(3):
            x0 = j * cell_width
            y0 = i * cell_height + 60
            x1 = x0 + cell_width
            y1 = y0 + cell_height
            val = data[i][j]
            if val is None:
                color = (80, 80, 80)
                text = "N/A"
            else:
                norm = (val - min_val) / span
                color = (int(255 * norm), int(120 * (1 - norm)), 180)
                text = f"{val:.2f}"
            draw.rectangle([x0, y0, x1, y1], fill=color)
            draw.rectangle([x0, y0, x1, y1], outline=(30, 30, 30), width=2)
            draw.text((x0 + cell_width / 2, y0 + cell_height / 2), text, fill="white", anchor="mm")

    # Axis labels
    for idx, label in enumerate(["low", "medium", "high"]):
        draw.text((idx * cell_width + cell_width / 2, 40), label, fill="white", anchor="mm")
    for idx, label in enumerate(["near", "mid", "far"]):
        draw.text((15, idx * cell_height + cell_height + 60 - cell_height / 2), label, fill="white", anchor="lm")

    draw.text((width / 2, 20), title, fill="white", anchor="mm")
    img.save(output_path)


def _percentile_threshold(values: Iterable[float], percentile: float) -> float:
    clean = [float(v) for v in values if isinstance(v, (int, float)) and not math.isnan(float(v))]
    if not clean:
        return float("nan")
    clean.sort()
    k = (len(clean) - 1) * (percentile / 100)
    low = int(math.floor(k))
    high = int(math.ceil(k))
    if low == high:
        return clean[low]
    frac = k - low
    return clean[low] + (clean[high] - clean[low]) * frac


def build_summary(
    sigma_table: List[Dict[str, object]],
    artifact_sha: str,
    generated_at: str,
) -> str:
    b1_stds = [row["B1_std"] for row in sigma_table]
    b4_stds = [row["B4_std"] for row in sigma_table]
    p95_b1 = _percentile_threshold(b1_stds, 95)
    p95_b4 = _percentile_threshold(b4_stds, 95)

    recommended = [
        row for row in sigma_table
        if row["B1_std"] <= p95_b1 and row["B4_std"] <= p95_b4 and row["bcr"] < 0.10
    ]
    recommended.sort(key=lambda r: (r["bcr"], r["B1_std"], r["B4_std"]))

    caution = [
        row for row in sigma_table
        if (row["B1_outlier_rate"] > 0.15)
        or (row["B4_outlier_rate"] > 0.15)
        or (row["bcr"] > 0.12)
    ]
    caution.sort(key=lambda r: r["bcr"], reverse=True)

    lines: List[str] = [
        "# Sigma Summary",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Artifact SHA: `{artifact_sha}`",
        "",
        "## Recommended Capture Cells",
    ]

    if not recommended:
        lines.append("- (none)")
    else:
        for row in recommended[:3]:
            lines.append(
                f"- `{row['distance']}/{row['resolution']}/{row['illumination']}` "
                f"(B1σ={row['B1_std']:.2f}, B4σ={row['B4_std']:.2f}, BCR={row['bcr']*100:.1f}%, n={row['sample_size']})"
            )

    lines.extend(["", "## Cells Requiring Attention"])
    if not caution:
        lines.append("- (none)")
    else:
        for row in caution:
            driver = []
            if row["B1_outlier_rate"] > 0.15:
                driver.append(f"B1 outliers {row['B1_outlier_rate']*100:.1f}%")
            if row["B4_outlier_rate"] > 0.15:
                driver.append(f"B4 outliers {row['B4_outlier_rate']*100:.1f}%")
            if row["bcr"] > 0.12:
                driver.append(f"BCR {row['bcr']*100:.1f}%")
            reason = ", ".join(driver)
            lines.append(
                f"- `{row['distance']}/{row['resolution']}/{row['illumination']}` "
                f"(n={row['sample_size']}): {reason}"
            )

    return "\n".join(lines) + "\n"


def write_sigma_table(table_rows: List[Dict[str, object]], cfg: SigmaConfig) -> Path:
    output_path = cfg.output_dir / "sigma_table.csv"
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "generated_at",
        "artifact_sha",
        "cell_id",
        "distance",
        "resolution",
        "illumination",
        "sample_size",
        "B1_mean",
        "B1_std",
        "B1_outlier_rate",
        "B4_mean",
        "B4_std",
        "B4_outlier_rate",
        "bcr",
        "meets_min_samples",
        "notes",
    ]

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in table_rows:
            payload = {key: row.get(key, "") for key in fieldnames}
            payload["generated_at"] = cfg.generated_at
            payload["artifact_sha"] = cfg.artifact_sha
            writer.writerow(payload)

    return output_path


def run_sigma_probe(cfg: SigmaConfig) -> Dict[str, Path]:
    metadata_map = load_metadata(cfg.metadata_path)
    rep_records = load_rep_results(cfg.rep_results)
    sigma_table = compute_sigma_table(rep_records, metadata_map)

    if not sigma_table:
        raise ValueError("Sigma table is empty. Verify inputs.")

    csv_path = write_sigma_table(sigma_table, cfg)
    std_heatmap_path = cfg.output_dir / "fig_std_heatmap.png"
    bcr_heatmap_path = cfg.output_dir / "fig_bcr_heatmap.png"

    # Heatmaps: use max(B1_std, B4_std) to emphasize worst-case spread.
    for row in sigma_table:
        row["max_std"] = max(row["B1_std"], row["B4_std"])

    _make_heatmap(
        sigma_table,
        value_column="max_std",
        output_path=std_heatmap_path,
        title="Max(B1σ, B4σ) Heatmap",
        cmap="magma",
    )
    _make_heatmap(
        sigma_table,
        value_column="bcr",
        output_path=bcr_heatmap_path,
        title="BCR Heatmap",
        cmap="cividis",
    )

    summary_md = build_summary(sigma_table, cfg.artifact_sha, cfg.generated_at)
    summary_path = cfg.output_dir / "summary.md"
    summary_path.write_text(summary_md, encoding="utf-8")

    return {
        "sigma_table": csv_path,
        "std_heatmap": std_heatmap_path,
        "bcr_heatmap": bcr_heatmap_path,
        "summary": summary_path,
    }


def main(argv: Optional[Sequence[str]] = None) -> None:
    cfg = parse_args(argv)
    paths = run_sigma_probe(cfg)
    print("Generated artifacts:")
    for name, path in paths.items():
        print(f"- {name}: {path}")


if __name__ == "__main__":
    main()
