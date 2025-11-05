"""
Unit tests for metrics_monitor.py SNS notification integration.

Purpose: Verify contract-compliant SNS notification payload generation
Scope: send_notification() logic, payload structure, contract validation
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add lambda/ and src/ to path
lambda_path = Path(__file__).parent.parent.parent / "lambda"
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(lambda_path))
sys.path.insert(0, str(src_path))

# Import from lambda/monitoring/metrics_monitor.py
sys.path.insert(0, str(lambda_path / "monitoring"))
import metrics_monitor
from metrics_monitor import MonitoringState, send_notification


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up environment variables for testing."""
    # Set environment variables
    monkeypatch.setenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:thf-alerts-dev")
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("RULES_VERSION", "v2.1")
    monkeypatch.setenv("DASHBOARD_URL", "https://streamlit.app/threshold_editor")

    # Also set module-level variables (metrics_monitor caches these at import time)
    metrics_monitor.SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:123456789012:thf-alerts-dev"
    metrics_monitor.ENVIRONMENT = "dev"
    metrics_monitor.RULES_VERSION = "v2.1"
    metrics_monitor.DASHBOARD_URL = "https://streamlit.app/threshold_editor"


@pytest.fixture
def sample_warn_state():
    """Create a sample WARN state."""
    return MonitoringState(
        metric_name="BCR",
        env_version="dev#v2.1",
        current_state="WARN",
        warn_count=15,
        fail_count=0,
        last_check_ts="2025-11-05T12:00:00.000Z",
        state_entered_ts="2025-11-05T11:45:00.000Z",
        ttl=0,
    )


@pytest.fixture
def sample_fail_state():
    """Create a sample FAIL state."""
    return MonitoringState(
        metric_name="Kappa",
        env_version="dev#v2.1",
        current_state="FAIL",
        warn_count=0,
        fail_count=5,
        last_check_ts="2025-11-05T12:00:00.000Z",
        state_entered_ts="2025-11-05T11:55:00.000Z",
        ttl=0,
    )


@pytest.fixture
def sample_ok_state():
    """Create a sample OK (recovery) state."""
    return MonitoringState(
        metric_name="OverrideRatio",
        env_version="dev#v2.1",
        current_state="OK",
        warn_count=0,
        fail_count=0,
        last_check_ts="2025-11-05T12:00:00.000Z",
        state_entered_ts="2025-11-05T12:00:00.000Z",
        ttl=0,
    )


# --- Test: Payload Generation ---


def test_warn_notification_payload_structure(mock_env_vars, sample_warn_state):
    """Test WARN notification generates correct payload structure."""
    with patch("metrics_monitor.sns_send_notification") as mock_sns:
        mock_sns.return_value = {"MessageId": "test-message-id-123"}

        send_notification("BCR", sample_warn_state, 0.48)

        # Verify sns_send_notification was called once
        assert mock_sns.call_count == 1

        # Extract payload from call
        call_kwargs = mock_sns.call_args.kwargs
        payload = call_kwargs["payload"]

        # Verify required keys (contract v1.0.0)
        assert "env" in payload
        assert "overall" in payload
        assert "source" in payload
        assert "reason" in payload
        assert "url" in payload

        # Verify values
        assert payload["env"] == "dev"
        assert payload["overall"] == "WARN"
        assert payload["source"] == "metrics_monitor"
        assert "BCR" in payload["reason"]
        assert "WARN state" in payload["reason"]
        assert "15" in payload["reason"]
        assert payload["url"] == "https://streamlit.app/threshold_editor"


def test_fail_notification_payload_structure(mock_env_vars, sample_fail_state):
    """Test FAIL notification generates correct payload structure."""
    with patch("metrics_monitor.sns_send_notification") as mock_sns:
        mock_sns.return_value = {"MessageId": "test-message-id-456"}

        send_notification("Kappa", sample_fail_state, 0.18)

        call_kwargs = mock_sns.call_args.kwargs
        payload = call_kwargs["payload"]

        # Verify FAIL-specific values
        assert payload["overall"] == "FAIL"
        assert payload["severity"] == "CRITICAL"
        assert "Kappa" in payload["reason"]
        assert "FAIL state" in payload["reason"]
        assert "5 consecutive minutes" in payload["reason"]


def test_ok_notification_payload_structure(mock_env_vars, sample_ok_state):
    """Test OK (recovery) notification generates correct payload structure."""
    with patch("metrics_monitor.sns_send_notification") as mock_sns:
        mock_sns.return_value = {"MessageId": "test-message-id-789"}

        send_notification("OverrideRatio", sample_ok_state, 25.0)

        call_kwargs = mock_sns.call_args.kwargs
        payload = call_kwargs["payload"]

        # Verify OK-specific values
        assert payload["overall"] == "OK"
        assert payload["severity"] == "INFO"
        assert "recovered to normal" in payload["reason"]


# --- Test: Severity Mapping ---


def test_severity_mapping(mock_env_vars):
    """Test state → severity mapping."""
    test_cases = [
        ("OK", "INFO"),
        ("WARN", "WARN"),
        ("FAIL", "CRITICAL"),
    ]

    for state_value, expected_severity in test_cases:
        state = MonitoringState(
            metric_name="TestMetric",
            env_version="dev#v2.1",
            current_state=state_value,
            warn_count=0,
            fail_count=0,
            last_check_ts="2025-11-05T12:00:00.000Z",
            state_entered_ts="2025-11-05T12:00:00.000Z",
            ttl=0,
        )

        with patch("metrics_monitor.sns_send_notification") as mock_sns:
            mock_sns.return_value = {"MessageId": "test-id"}

            send_notification("TestMetric", state, 0.5)

            payload = mock_sns.call_args.kwargs["payload"]
            assert payload["severity"] == expected_severity, f"Expected {expected_severity} for {state_value}"


# --- Test: Metadata Structure ---


def test_metadata_contents(mock_env_vars, sample_warn_state):
    """Test metadata contains required fields."""
    with patch("metrics_monitor.sns_send_notification") as mock_sns:
        mock_sns.return_value = {"MessageId": "test-id"}

        send_notification("BCR", sample_warn_state, 0.48)

        payload = mock_sns.call_args.kwargs["payload"]
        metadata = payload["metadata"]

        # Verify metadata keys
        assert "metric_name" in metadata
        assert "current_value" in metadata
        assert "warn_count" in metadata
        assert "fail_count" in metadata
        assert "warn_debounce_threshold" in metadata
        assert "fail_debounce_threshold" in metadata
        assert "state_entered_ts" in metadata
        assert "rules_version" in metadata

        # Verify values
        assert metadata["metric_name"] == "BCR"
        assert metadata["current_value"] == 0.48
        assert metadata["warn_count"] == 15
        assert metadata["warn_debounce_threshold"] == 15
        assert metadata["fail_debounce_threshold"] == 5
        assert metadata["rules_version"] == "v2.1"


# --- Test: Subject Line ---


def test_subject_line_format(mock_env_vars, sample_warn_state):
    """Test SNS subject line format."""
    with patch("metrics_monitor.sns_send_notification") as mock_sns:
        mock_sns.return_value = {"MessageId": "test-id"}

        send_notification("BCR", sample_warn_state, 0.48)

        subject = mock_sns.call_args.kwargs["subject"]

        # Verify subject format: "[STATE] MetricName Alert - env"
        assert "[WARN]" in subject
        assert "BCR" in subject
        assert "Alert" in subject
        assert "dev" in subject


# --- Test: Error Handling ---


def test_sns_topic_arn_not_configured(mock_env_vars, sample_warn_state, monkeypatch):
    """Test graceful handling when SNS_TOPIC_ARN is not set."""
    monkeypatch.delenv("SNS_TOPIC_ARN", raising=False)
    metrics_monitor.SNS_TOPIC_ARN = None

    with patch("metrics_monitor.sns_send_notification") as mock_sns:
        send_notification("BCR", sample_warn_state, 0.48)

        # Should not call sns_send_notification
        assert mock_sns.call_count == 0


def test_sns_notifier_import_failure_fallback(mock_env_vars, sample_warn_state):
    """Test fallback to legacy notification when sns_notifier import fails."""
    # Simulate import failure
    original_sns = metrics_monitor.sns_send_notification
    metrics_monitor.sns_send_notification = None

    with patch("metrics_monitor._get_sns") as mock_get_sns:
        mock_sns_client = MagicMock()
        mock_sns_client.publish.return_value = {"MessageId": "legacy-id"}
        mock_get_sns.return_value = mock_sns_client

        send_notification("BCR", sample_warn_state, 0.48)

        # Verify legacy SNS publish was called
        assert mock_sns_client.publish.call_count == 1

        # Verify legacy message format (plain text)
        call_args = mock_sns_client.publish.call_args.kwargs
        assert "Message" in call_args
        assert "Metrics Monitoring Alert" in call_args["Message"]

    # Restore
    metrics_monitor.sns_send_notification = original_sns


def test_sns_notification_exception_handling(mock_env_vars, sample_warn_state):
    """Test exception handling during notification."""
    with patch("metrics_monitor.sns_send_notification") as mock_sns:
        from monitoring.sns_notifier import SNSNotificationError
        mock_sns.side_effect = SNSNotificationError("SNS publish failed: AccessDenied")

        # Should not raise exception, just log
        send_notification("BCR", sample_warn_state, 0.48)

        # Verify it attempted to send
        assert mock_sns.call_count == 1


# --- Test: Value Formatting ---


def test_value_formatting_with_none(mock_env_vars, sample_warn_state):
    """Test metric value formatting when value is None."""
    with patch("metrics_monitor.sns_send_notification") as mock_sns:
        mock_sns.return_value = {"MessageId": "test-id"}

        send_notification("BCR", sample_warn_state, None)

        payload = mock_sns.call_args.kwargs["payload"]
        reason = payload["reason"]

        # Should show "N/A" for None value
        assert "N/A" in reason
        assert payload["metadata"]["current_value"] is None


def test_value_formatting_with_float(mock_env_vars, sample_warn_state):
    """Test metric value formatting with float."""
    with patch("metrics_monitor.sns_send_notification") as mock_sns:
        mock_sns.return_value = {"MessageId": "test-id"}

        send_notification("BCR", sample_warn_state, 0.48765)

        payload = mock_sns.call_args.kwargs["payload"]
        reason = payload["reason"]

        # Should format to 3 decimal places
        assert "0.488" in reason
        assert payload["metadata"]["current_value"] == 0.48765


# --- Test: CloudWatch Logs Event ---


def test_cloudwatch_logs_notification_event(mock_env_vars, sample_warn_state, capsys):
    """Test CloudWatch Logs notification event is emitted."""
    with patch("metrics_monitor.sns_send_notification") as mock_sns:
        mock_sns.return_value = {"MessageId": "test-message-id-123"}

        send_notification("BCR", sample_warn_state, 0.48)

        # Capture stdout
        captured = capsys.readouterr()

        # Verify notification event log was printed (JSON format)
        assert "metrics_monitor_notification" in captured.out
        assert "test-message-id-123" in captured.out

        # Parse as JSON to verify structure
        log_lines = [line for line in captured.out.split("\n") if "metrics_monitor_notification" in line]
        assert len(log_lines) > 0

        log_event = json.loads(log_lines[0])
        assert log_event["event"] == "metrics_monitor_notification"
        assert log_event["metric_name"] == "BCR"
        assert log_event["state"] == "WARN"
        assert log_event["severity"] == "WARN"
        assert log_event["message_id"] == "test-message-id-123"
