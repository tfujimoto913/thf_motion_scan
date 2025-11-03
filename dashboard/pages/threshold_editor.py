"""Threshold Editor MVP page."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Add src directory for thresholds_editor package
ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in os.sys.path:
    os.sys.path.insert(0, str(SRC_ROOT))

from thresholds_editor import (  # type: ignore[import]
    Band,
    ThreeTierBands,
    analyse_reclassification,
    load_document_from_file,
    save_document_to_file,
    snapshot_thresholds,
    ChangeLogEntry,
    ensure_dev_environment,
    require_apply_confirmation,
    should_block_apply,
)

THRESHOLD_PATH = ROOT / "config" / "thresholds" / "thresholds.json"
CHANGELOG_PATH = THRESHOLD_PATH.parent / "changelog.jsonl"
SNAPSHOT_DIR = THRESHOLD_PATH.parent
SAMPLE_DATA_ROOT = ROOT / "sample_dataset"

ENV = os.environ.get("ENV", "dev")


def load_threshold_document() -> Dict[str, object]:
    return load_document_from_file(THRESHOLD_PATH)


def get_metric_choices(doc) -> Dict[str, Dict[str, object]]:
    choices: Dict[str, Dict[str, object]] = {}
    for test_name, payload in doc.tests.items():
        metrics = {}
        for metric_key, metric in payload.items():
            metrics[metric_key] = metric
        choices[test_name] = metrics
    return choices


def format_bands(bands: ThreeTierBands) -> str:
    return f"OK: [{bands.ok.lower}, {bands.ok.upper})  ATTENTION: [{bands.attn.lower}, {bands.attn.upper})  NG: [{bands.ng.lower}, {bands.ng.upper})"


@st.cache_data(ttl=30)
def load_sample_dataset(test: str) -> pd.DataFrame:
    folder = SAMPLE_DATA_ROOT / test
    manifest_path = folder / "manifest.json"
    dataset_file = "data.csv"
    if manifest_path.exists():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            dataset_file = payload.get("dataset", dataset_file)
        except json.JSONDecodeError:
            pass
    dataset_path = folder / dataset_file
    if dataset_path.exists():
        return pd.read_csv(dataset_path)
    return pd.DataFrame(columns=["rep_id", "value"])


def compute_preview(records: pd.DataFrame, old_bands: ThreeTierBands, new_bands: ThreeTierBands):
    rows = records.to_dict(orient="records")
    preview = analyse_reclassification(rows, old_bands, new_bands)

    # Band breakdowns
    band_counts_before = {"OK": 0, "ATTN": 0, "NG": 0}
    band_counts_after = {"OK": 0, "ATTN": 0, "NG": 0}
    for row in rows:
        value = row.get("value")
        old_band = "NA" if value is None else classify_value(value, old_bands)
        new_band = "NA" if value is None else classify_value(value, new_bands)
        if old_band in band_counts_before:
            band_counts_before[old_band] += 1
        if new_band in band_counts_after:
            band_counts_after[new_band] += 1

    return preview, band_counts_before, band_counts_after


def classify_value(value: Optional[float], bands: ThreeTierBands) -> str:
    if value is None:
        return "NA"
    if bands.ok.contains(value):
        return "OK"
    if bands.attn.contains(value):
        return "ATTN"
    return "NG"


def render_barchart(before: Dict[str, int], after: Dict[str, int]) -> None:
    categories = ["OK", "ATTN", "NG"]
    fig = go.Figure()
    fig.add_bar(name="Before", x=categories, y=[before.get(cat, 0) for cat in categories])
    fig.add_bar(name="After", x=categories, y=[after.get(cat, 0) for cat in categories])
    fig.update_layout(barmode="group", title="Band Distribution (Before vs After)")
    st.plotly_chart(fig, use_container_width=True)


def append_changelog(entry: ChangeLogEntry) -> None:
    with CHANGELOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")


def load_changelog(n: int = 5) -> List[Dict[str, object]]:
    if not CHANGELOG_PATH.exists():
        return []
    lines = CHANGELOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    recent = [json.loads(line) for line in lines[-n:]] if lines else []
    return list(reversed(recent))


def purge_old_snapshots() -> None:
    snapshots = sorted(SNAPSHOT_DIR.glob("thresholds-*.json"))
    for obsolete in snapshots[:-1]:
        obsolete.unlink(missing_ok=True)


def undo_last_change(actor: str, env: str) -> bool:
    snapshots = sorted(SNAPSHOT_DIR.glob("thresholds-*.json"))
    if not snapshots:
        return False
    latest = snapshots[-1]
    previous_doc = load_document_from_file(latest)
    current_doc = load_document_from_file(THRESHOLD_PATH)
    save_document_to_file(previous_doc, THRESHOLD_PATH)
    entry = ChangeLogEntry(
        id=f"undo_{latest.stem}",
        actor=actor or "unknown",
        env=env,
        test="*",
        metric="*",
        prev={"ok": [0, 0], "attn": [0, 0], "ng": [0, 0]},
        next={"ok": [0, 0], "attn": [0, 0], "ng": [0, 0]},
        reclassified_rate=0.0,
        reclassified_count=0,
        sample_n=0,
        representatives={"upshift": [], "downshift": []},
        versions=current_doc.versions or {},
    )
    append_changelog(entry)
    latest.unlink(missing_ok=True)
    return True


def main() -> None:
    st.set_page_config(page_title="Threshold Editor")
    st.title("Threshold Editor (MVP)")

    actor = st.sidebar.text_input("Actor", value=os.environ.get("USER", ""))
    doc = load_threshold_document()
    metric_choices = get_metric_choices(doc)
    test_names = sorted(metric_choices.keys())
    selected_test = st.sidebar.selectbox("Test", test_names, index=test_names.index("SLS") if "SLS" in test_names else 0)

    metrics_for_test = metric_choices[selected_test]
    metric_keys = sorted(metrics_for_test.keys())
    selected_metric = st.sidebar.selectbox("Metric", metric_keys)

    metric = metrics_for_test[selected_metric]
    if metric.by_side:
        side_options = ["left", "right"]
        selected_side = st.sidebar.selectbox("Side", side_options)
    else:
        selected_side = "default"
        st.sidebar.info("Side selection not required for this metric")

    st.sidebar.markdown("---")
    st.sidebar.metric("ENV", ENV)

    st.subheader("Current Bands")
    current_bands = metric.get_bands(selected_side if metric.by_side else None)
    st.code(format_bands(current_bands))

    col1, col2 = st.columns(2)
    with col1:
        t1 = st.number_input("Threshold t1 (OK → ATTN)", value=float(current_bands.attn.lower), step=0.5)
    with col2:
        t2 = st.number_input("Threshold t2 (ATTN → NG)", value=float(current_bands.ng.lower), step=0.5)

    lower_bound = current_bands.ok.lower
    upper_bound = current_bands.ng.upper

    if t1 <= lower_bound or t2 <= t1 or t2 > upper_bound:
        st.warning("Ensure lower < t1 < t2 < upper.")

    sample_df = load_sample_dataset(selected_test)
    st.caption(f"Dry-run sample size: {len(sample_df)} reps")

    preview_container = st.container()
    admin_override = st.checkbox("Admin override (allow apply above 35% reclassification)", value=False)

    if st.button("Dry Run", type="primary"):
        if sample_df.empty:
            st.error("No sample dataset found for this test.")
        else:
            new_bands = ThreeTierBands(
                ok=Band(lower_bound, t1),
                attn=Band(t1, t2),
                ng=Band(t2, upper_bound),
            )
            preview, before_counts, after_counts = compute_preview(sample_df, current_bands, new_bands)
            st.session_state["preview_result"] = {
                "preview": preview,
                "before": before_counts,
                "after": after_counts,
                "new_bands": new_bands,
                "sample_n": len(sample_df),
            }

    preview_state = st.session_state.get("preview_result")
    if preview_state:
        preview = preview_state["preview"]
        st.markdown("### Dry-run Summary")
        st.metric("Reclassified count", preview.reclassified_count)
        st.metric("Reclassified rate", f"{preview.reclassified_rate * 100:.2f}%")
        render_barchart(preview_state["before"], preview_state["after"])
        st.markdown("#### Representative Samples")
        st.json({
            "upshift": [sample.rep_id for sample in preview.representatives["upshift"]],
            "downshift": [sample.rep_id for sample in preview.representatives["downshift"]],
        })

    st.markdown("---")
    confirm_text = st.text_input("Type APPLY to confirm", value="")
    apply_disabled = ENV != "dev" or not preview_state
    if ENV != "dev":
        st.warning("Apply is restricted to ENV=dev.")

    if st.button("Apply", disabled=apply_disabled):
        if not preview_state:
            st.error("Run a dry-run first.")
        else:
            preview = preview_state["preview"]
            try:
                ensure_dev_environment(ENV)
                blocked = should_block_apply(preview.reclassified_rate, admin_override=admin_override)
                if blocked:
                    st.error("Reclassified rate exceeds 35%. Override required.")
                    raise RuntimeError
                require_apply_confirmation(confirm_text)
            except RuntimeError:
                pass
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
            else:
                snapshot_path = snapshot_thresholds(THRESHOLD_PATH, SNAPSHOT_DIR)
                purge_old_snapshots()
                new_bands: ThreeTierBands = preview_state["new_bands"]
                metric.update_bands(new_bands, side=selected_side if metric.by_side else None)
                save_document_to_file(doc, THRESHOLD_PATH)
                entry = ChangeLogEntry.from_preview(
                    actor=actor or "unknown",
                    env=ENV,
                    test=selected_test,
                    metric=f"{selected_metric}.{selected_side}" if metric.by_side else selected_metric,
                    prev=current_bands.as_dict(),
                    nxt=new_bands.as_dict(),
                    sample_records=preview_state["sample_n"],
                    preview_representatives=preview.representatives,
                    reclassified_rate=preview.reclassified_rate,
                    reclassified_count=preview.reclassified_count,
                    versions=doc.versions or {},
                )
                append_changelog(entry)
                st.success(f"Applied. Snapshot saved at {snapshot_path.name}")
                st.session_state.pop("preview_result", None)
                st.experimental_rerun()

    if st.button("Undo last change"):
        success = undo_last_change(actor or "unknown", ENV)
        if success:
            st.success("Restored from last snapshot.")
            st.session_state.pop("preview_result", None)
            st.experimental_rerun()
        else:
            st.info("No snapshot found.")

    st.markdown("---")
    st.subheader("Recent Change Log")
    for entry in load_changelog():
        st.json(entry)


if __name__ == "__main__":
    main()
