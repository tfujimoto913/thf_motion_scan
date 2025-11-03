"""
Utilities that support the upcoming Threshold Editor workflow.

The helpers here encapsulate the half-open band rules, preview analytics,
environment safeguards, and change-log structure so the UI layer can stay
thin.  Nothing in this module depends on Streamlit directly; pure functions
keep the logic testable and reusable by CLI or automation scripts.
"""

from .models import (
    Band,
    ThreeTierBands,
    MetricThreshold,
    ThresholdDocument,
    load_document_from_file,
    save_document_to_file,
    load_threshold_document,
    serialize_threshold_document,
)
from .preview import (
    classify_value,
    analyse_reclassification,
    RepresentativeSample,
    PreviewResult,
)
from .changelog import ChangeLogEntry
from .safeguards import (
    ensure_dev_environment,
    require_apply_confirmation,
    should_block_apply,
)
from .snapshots import snapshot_thresholds

__all__ = [
    "Band",
    "ThreeTierBands",
    "MetricThreshold",
    "ThresholdDocument",
    "load_document_from_file",
    "save_document_to_file",
    "load_threshold_document",
    "serialize_threshold_document",
    "classify_value",
    "analyse_reclassification",
    "RepresentativeSample",
    "PreviewResult",
    "ChangeLogEntry",
    "ensure_dev_environment",
    "require_apply_confirmation",
    "should_block_apply",
    "snapshot_thresholds",
]
