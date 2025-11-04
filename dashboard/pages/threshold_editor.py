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
from thresholds_editor.change_logger import get_logger  # type: ignore[import]

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
    """
    What: 閾値変更ログを記録
    Why: Apply操作の監査証跡を残すため

    Design Decision:
    - 新しいchange_loggerを使用（idempotency保証、dry-runガード）
    - 旧changelog.jsonlとの互換性のため、両方に記録

    CRITICAL: DRY_RUN=true時は新ログには記録しない
    """
    # 新ロガー（idempotency保証あり）
    logger = get_logger(base_dir=ROOT / "logs" / "change_log")
    logger.log_apply(entry)

    # 旧形式との互換性のため、従来のログも残す
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
    """
    What: 直前の閾値変更をロールバック
    Why: 誤操作時の迅速な復旧のため

    Design Decision:
    - 新しいchange_loggerでlog_undo()を記録
    - 旧形式との互換性のため、従来のログも残す

    CRITICAL: DRY_RUN=true時は新ログには記録しない
    """
    snapshots = sorted(SNAPSHOT_DIR.glob("thresholds-*.json"))
    if not snapshots:
        return False
    latest = snapshots[-1]
    previous_doc = load_document_from_file(latest)
    current_doc = load_document_from_file(THRESHOLD_PATH)
    save_document_to_file(previous_doc, THRESHOLD_PATH)

    # 新ロガー（idempotency保証あり）
    logger = get_logger(base_dir=ROOT / "logs" / "change_log")
    logger.log_undo(
        actor=actor or "unknown",
        env=env,
        rollback_of_id=f"snapshot_{latest.stem}",
        reverted_snapshot_path=str(latest),
        versions=current_doc.versions or {},
    )

    # 旧形式との互換性のため、従来のログも残す
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
    with CHANGELOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    latest.unlink(missing_ok=True)
    return True


def render_threshold_editor_page() -> None:
    """
    What: Threshold editor page for integration into app.py
    Why: app.py calls st.set_page_config() once, so this function omits it
    Design Decision: Separate render function for multi-page app integration

    CRITICAL: Do not call st.set_page_config() here - app.py handles it
    """
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
    render_batch_dryrun_panel()

    st.markdown("---")
    st.subheader("📜 Recent Changes (Last 10)")

    # Load from new change_logger (idempotency-protected)
    logger = get_logger(base_dir=ROOT / "logs" / "change_log")
    recent_logs = logger.load_recent_logs(n=10)

    if recent_logs:
        # Format for table display
        table_data = []
        for log in recent_logs:
            table_data.append({
                "Timestamp": log.get("timestamp", "N/A"),
                "Action": log.get("action", "N/A"),
                "Test": log.get("test", "N/A"),
                "Metric": log.get("metric", "N/A"),
                "Actor": log.get("actor", "N/A"),
            })

        df = pd.DataFrame(table_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No recent changes recorded.")


def render_batch_dryrun_panel():
    """
    What: Batch dry-run UI panel for multiple metrics
    Why: Allow operators to assess combined impact of threshold changes
    Design Decision: Simple JSON input for MVP, form UI for future enhancement

    CRITICAL:
    - Performance display: execution time and overall reclassified rate
    - Top3 metrics highlighted
    - Representative examples (max 3)
    """
    import sys
    from pathlib import Path

    # Add tools directory to path
    tools_path = ROOT / "tools"
    if str(tools_path) not in sys.path:
        sys.path.insert(0, str(tools_path))

    from threshold_dryrun import run_batch_dryrun  # type: ignore[import]

    st.subheader("🔄 Batch Dry-run (Multiple Metrics)")

    with st.expander("ℹ️ How to use Batch Dry-run", expanded=False):
        st.markdown("""
        **Purpose**: Evaluate impact of threshold changes across multiple metrics simultaneously.

        **Steps**:
        1. Prepare sample data (CSV with columns for each metric)
        2. Define metrics config (JSON format below)
        3. Click "Run Batch Dry-run"
        4. Review: overall rate, Top3 metrics, representative examples

        **Metrics Config Format**:
        ```json
        {
          "SLS:B1:trunk_lean_deg": {
            "new_bands": [
              {"label": "OK", "max": 12.0},
              {"label": "WARN", "max": 22.0},
              {"label": "NG", "max": null}
            ],
            "old_bands": [
              {"label": "OK", "max": 10.0},
              {"label": "WARN", "max": 20.0},
              {"label": "NG", "max": null}
            ],
            "value_column": "trunk_lean_deg"
          }
        }
        ```
        """)

    # Input: Sample data upload
    st.markdown("### Step 1: Sample Data")
    uploaded_file = st.file_uploader(
        "Upload CSV with sample data",
        type=["csv"],
        help="CSV must contain 'sample_id' column and columns for each metric"
    )

    if uploaded_file:
        samples_df = pd.read_csv(uploaded_file)
        st.success(f"✅ Loaded {len(samples_df)} samples")
        st.dataframe(samples_df.head(5), use_container_width=True)
    else:
        # Use demo data from sample_dataset
        demo_path = SAMPLE_DATA_ROOT / "multi_metric_samples.csv"
        if demo_path.exists():
            samples_df = pd.read_csv(demo_path)
            st.info(f"Using demo data: {len(samples_df)} samples (multi-metric)")
        else:
            samples_df = None
            st.warning("No sample data. Upload CSV or generate demo data via: `python tools/generate_multi_metric_samples.py --output sample_dataset/multi_metric_samples.csv`")

    # Input: Metrics config
    st.markdown("### Step 2: Metrics Configuration")

    default_config = {
        "SLS:B1:trunk_lean_deg": {
            "new_bands": [
                {"label": "OK", "max": 12.0},
                {"label": "WARN", "max": 22.0},
                {"label": "NG", "max": None}
            ],
            "old_bands": [
                {"label": "OK", "max": 10.0},
                {"label": "WARN", "max": 20.0},
                {"label": "NG", "max": None}
            ],
            "value_column": "trunk_lean_deg"
        },
        "SLS:B2:knee_valgus_deg": {
            "new_bands": [
                {"label": "OK", "max": 8.0},
                {"label": "WARN", "max": 12.0},
                {"label": "NG", "max": None}
            ],
            "old_bands": [
                {"label": "OK", "max": 5.0},
                {"label": "WARN", "max": 10.0},
                {"label": "NG", "max": None}
            ],
            "value_column": "knee_valgus_deg"
        }
    }

    import json
    metrics_config_json = st.text_area(
        "Metrics Config (JSON)",
        value=json.dumps(default_config, indent=2),
        height=300,
        help="Define threshold bands for each metric"
    )

    seed = st.number_input("Random Seed", value=42, min_value=1, help="Fixed seed for reproducibility")

    # Execution
    if st.button("🚀 Run Batch Dry-run", type="primary"):
        if samples_df is None or samples_df.empty:
            st.error("❌ No sample data available. Upload CSV first.")
            return

        try:
            metrics_config = json.loads(metrics_config_json)
        except json.JSONDecodeError as e:
            st.error(f"❌ Invalid JSON format: {e}")
            return

        if not metrics_config:
            st.error("❌ Metrics config is empty.")
            return

        # Validate columns exist
        missing_columns = []
        for metric_id, config in metrics_config.items():
            value_column = config.get("value_column")
            if value_column not in samples_df.columns:
                missing_columns.append(value_column)

        if missing_columns:
            st.error(f"❌ Missing columns in sample data: {missing_columns}")
            return

        # Run batch dry-run
        with st.spinner("Running batch dry-run..."):
            try:
                result = run_batch_dryrun(
                    metrics_config=metrics_config,
                    samples_df=samples_df,
                    seed=int(seed),
                )

                st.session_state["batch_dryrun_result"] = result

            except Exception as e:
                st.error(f"❌ Batch dry-run failed: {e}")
                return

    # Display results
    batch_result = st.session_state.get("batch_dryrun_result")
    if batch_result:
        st.markdown("### 📊 Results")

        # Overall metrics
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "Overall Reclassified Rate",
                f"{batch_result['overall_reclassified_rate']:.1%}",
                help="Weighted average across all metrics"
            )
        with col2:
            st.metric(
                "Execution Time",
                f"{batch_result['execution_time_ms']}ms",
                help="Total processing time"
            )

        # Summary table
        st.markdown("#### Summary by Metric")
        summary_df = batch_result["summary_df"].copy()
        summary_df["reclassified_rate"] = summary_df["reclassified_rate"].apply(lambda x: f"{x:.1%}")
        st.dataframe(summary_df, use_container_width=True)

        # Top3 metrics
        st.markdown("#### 🔝 Top 3 Metrics (by impact)")
        top3 = batch_result["top3_metrics"]
        for i, metric_id in enumerate(top3, 1):
            metric_row = summary_df[summary_df["metric_id"] == metric_id].iloc[0]
            st.info(f"**{i}. {metric_id}**: {metric_row['affected_count']} affected ({metric_row['reclassified_rate']})")

        # Representative examples
        st.markdown("#### 📍 Representative Examples")
        examples = batch_result["representative_examples"]
        if examples:
            for ex in examples:
                category_emoji = {"best": "✨", "worst": "⚠️", "neutral": "📍"}.get(ex["category"], "•")
                st.markdown(f"{category_emoji} **{ex['category'].upper()}** ({ex['metric_id']})")
                st.json({
                    "sample_id": ex["sample_id"],
                    "old_label": ex["old_label"],
                    "new_label": ex["new_label"],
                    "value": round(ex["metric_value"], 2)
                })
        else:
            st.info("No examples available")


def main() -> None:
    """
    What: Standalone entry point for threshold editor
    Why: Allows running threshold_editor.py directly with `streamlit run`
    """
    st.set_page_config(page_title="Threshold Editor")
    render_threshold_editor_page()


if __name__ == "__main__":
    main()
