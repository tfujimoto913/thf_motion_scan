from pathlib import Path

import math

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2] / "src"))

from thresholds_editor.models import Band, ThreeTierBands
from thresholds_editor.preview import analyse_reclassification, classify_value


def test_classify_value_half_open():
    bands = ThreeTierBands(
        ok=Band(0, 10),
        attn=Band(10, 18),
        ng=Band(18, 90),
    )
    assert classify_value(9.99, bands) == "OK"
    assert classify_value(10, bands) == "ATTN"
    assert classify_value(17.999, bands) == "ATTN"
    assert classify_value(18, bands) == "NG"
    assert classify_value(None, bands) == "NA"
    assert classify_value(math.nan, bands) == "NA"


def test_analyse_reclassification_produces_rate_and_samples():
    old_bands = ThreeTierBands(
        ok=Band(0, 8),
        attn=Band(8, 15),
        ng=Band(15, 90),
    )
    new_bands = ThreeTierBands(
        ok=Band(0, 10),
        attn=Band(10, 18),
        ng=Band(18, 90),
    )

    records = [
        {"rep_id": "rep-1", "old_value": 7.5, "new_value": 9.5},
        {"rep_id": "rep-2", "old_value": 9.0, "new_value": 11.0},
        {"rep_id": "rep-3", "old_value": 16.0, "new_value": 17.0},
        {"rep_id": "rep-4", "old_value": 19.0, "new_value": 21.0},
    ]

    preview = analyse_reclassification(records, old_bands, new_bands)

    assert preview.reclassified_count == 1
    assert preview.reclassified_rate == 0.25
    assert preview.impact_count == 1
    assert len(preview.representatives["upshift"]) == 1
    assert len(preview.representatives["downshift"]) == 0
