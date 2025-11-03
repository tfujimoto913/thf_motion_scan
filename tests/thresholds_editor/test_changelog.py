from datetime import datetime, timezone

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from thresholds_editor.changelog import ChangeLogEntry
from thresholds_editor.preview import RepresentativeSample


def test_changelog_entry_serialisation():
    ts = datetime(2025, 11, 4, 3, 12, 9, tzinfo=timezone.utc)
    samples = {
        "upshift": [
            RepresentativeSample(
                rep_id="rep-up-1",
                old_band="ATTN",
                new_band="OK",
                old_value=12.0,
                new_value=9.0,
                score_delta=-3.0,
            )
        ],
        "downshift": [],
    }
    entry = ChangeLogEntry.from_preview(
        actor="taka",
        env="dev",
        test="SLS",
        metric="B4.pelvis_drop_deg.left",
        prev={"ok": [0, 8], "attn": [8, 15], "ng": [15, 90]},
        nxt={"ok": [0, 10], "attn": [10, 18], "ng": [18, 90]},
        sample_records=41,
        preview_representatives=samples,
        reclassified_rate=0.27,
        reclassified_count=11,
        versions={
            "thresholds_json": "2.0.1",
            "scoring_engine": "1.6.3",
            "dashboard": "2.1.0",
        },
        timestamp=ts,
    )

    payload = entry.to_dict()
    assert payload["id"] == "chg_2025-11-04T03:12:09+00:00"
    assert payload["representatives"]["upshift"] == ["rep-up-1"]
    assert payload["reclassified_rate"] == 0.27
