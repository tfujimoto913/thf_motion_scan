import importlib.util
import sys
import types
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root))


if "boto3" not in sys.modules:
    sys.modules["boto3"] = types.SimpleNamespace(
        client=lambda *args, **kwargs: types.SimpleNamespace(put_object=lambda **k: None)
    )

module_path = root / "lambda" / "rep_rescore" / "diff_reporter.py"
spec = importlib.util.spec_from_file_location("lambda.rep_rescore.diff_reporter", module_path)
diff_reporter = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(diff_reporter)


def test_diff_reporter_summary_includes_reclassified_rate(tmp_path, monkeypatch):
    events = {
        "execution_id": "exec-1",
        "threshold_version": "2.0.1",
        "artifact_sha": "abc123",
        "rules_version": "0.3.0",
        "results": [
            {
                "status": "SUCCESS",
                "rep_id": "rep-1",
                "old_validation_state": "WARN",
                "new_validation_state": "OK",
                "old_score": 12.0,
                "new_score": 9.5,
                "score_delta": -2.5,
            },
            {
                "status": "SUCCESS",
                "rep_id": "rep-2",
                "old_validation_state": "OK",
                "new_validation_state": "OK",
                "old_score": 8.0,
                "new_score": 8.0,
                "score_delta": 0.0,
            },
        ],
    }

    # Capture S3 put_object calls
    captured = []

    class FakeS3:
        def put_object(self, Bucket, Key, Body, ContentType):
            captured.append((Key, Body, ContentType))

    monkeypatch.setattr(diff_reporter, "_s3", FakeS3())
    monkeypatch.setattr(diff_reporter, "BUCKET", "unit-test-bucket")
    summary = diff_reporter.handler(events, None)

    assert summary["reclassified_count"] == 1
    assert summary["impact_count"] == 1
    assert summary["reclassified_rate"] == 0.5
    assert summary["representatives"]["upshift"][0]["rep_id"] == "rep-1"

    keys = [key for key, *_ in captured]
    assert any(key.endswith("summary.json") for key in keys)
