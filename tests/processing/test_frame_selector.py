"""
Purpose: Unit tests for processing.frame_selector helpers
Responsibility: Validate frame selection, naming, and upload helpers
Dependencies: pytest, pathlib
Created: 2025-11-06 by Codex
Decision Log: Task E - Static frame selection
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from processing.frame_selector import (
    FRAME_TYPES,
    build_frame_filename,
    build_s3_key,
    select_rep_frame_triplet,
    summarise_session_frames,
    upload_frame_image,
)


class TestSelectRepFrameTriplet:
    def test_returns_defaults_for_empty_input(self):
        result = select_rep_frame_triplet([])
        for frame_type in FRAME_TYPES:
            assert result[frame_type]["frame_idx"] == 0
            assert result[frame_type]["score"] == 0.0

    def test_chooses_best_worst_and_repr(self):
        frames = [
            {"frame_idx": 0, "score": 10.0, "angle_score": 0.8, "stability_score": 0.9},
            {"frame_idx": 1, "score": 60.0, "angle_score": 0.9, "stability_score": 0.5},
            {"frame_idx": 2, "score": 90.0, "angle_score": 0.6, "stability_score": 0.4},
            {"frame_idx": 3, "score": 45.0, "angle_score": 0.7, "stability_score": 0.6},
        ]

        result = select_rep_frame_triplet(frames, session_mean=50.0)

        assert result["best"]["frame_idx"] == 2
        assert result["worst"]["frame_idx"] == 0
        assert result["repr"]["frame_idx"] == 3  # score 45 is closest to mean 50


class TestNamingHelpers:
    def test_build_frame_filename_sanitises_values(self):
        name = build_frame_filename("sess 01", "rep#02", "best")
        assert name == "sess-01_rep-02_best.jpg"

    def test_build_s3_key_applies_prefix(self):
        key = build_s3_key("sess", "rep", "worst", prefix="frames")
        assert key == "frames/sess/rep/worst.jpg"


class TestUploadFrameImage:
    class FakeS3:
        def __init__(self):
            self.calls = []

        def upload_file(self, filename, bucket, key, ExtraArgs=None):
            self.calls.append(
                {"filename": filename, "bucket": bucket, "key": key, "extra": ExtraArgs}
            )

    def test_upload_frame_image_invokes_client(self, tmp_path):
        fake = self.FakeS3()
        bucket = "thf-motion-scan-frames"
        image_path = tmp_path / "frame.jpg"
        image_path.write_bytes(b"fake-image")

        key = upload_frame_image(
            fake,
            bucket,
            "session-id",
            "rep-id",
            "repr",
            image_path,
            metadata={"score": 72.5},
        )

        assert key == "session-id/rep-id/repr.jpg"
        assert fake.calls
        call = fake.calls[0]
        assert call["bucket"] == bucket
        assert call["extra"]["ContentType"] == "image/jpeg"
        assert call["extra"]["Metadata"]["score"] == "72.5"


class TestSummariseSessionFrames:
    def test_returns_session_level_selection(self):
        rep_selections = {
            "rep-1": {
                "best": {"frame_idx": 10, "score": 82.0},
                "worst": {"frame_idx": 2, "score": 60.0},
                "repr": {"frame_idx": 5, "score": 78.0},
            },
            "rep-2": {
                "best": {"frame_idx": 12, "score": 85.0},
                "worst": {"frame_idx": 3, "score": 58.0},
                "repr": {"frame_idx": 6, "score": 79.0},
            },
        }

        summary = summarise_session_frames(rep_selections)

        assert summary["best"]["rep_id"] == "rep-2"
        assert summary["worst"]["rep_id"] == "rep-2"
        assert summary["repr"]["rep_id"] in {"rep-1", "rep-2"}
