"""Sidebar component for billing status and guardrail visibility."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import boto3
import streamlit as st
from botocore.exceptions import BotoCoreError, ClientError

LOGGER = logging.getLogger(__name__)

BILLING_REGION = "us-east-1"


@dataclass
class AlarmState:
    name: str
    state: str
    reason: Optional[str] = None


@st.cache_resource
def get_cloudwatch_client() -> boto3.client:  # type: ignore[override]
    """Initialise a cached CloudWatch client in the billing region."""
    return boto3.client("cloudwatch", region_name=BILLING_REGION)


def _describe_alarm(client: boto3.client, alarm_name: str) -> AlarmState:  # type: ignore[override]
    try:
        response = client.describe_alarms(AlarmNames=[alarm_name])
    except (ClientError, BotoCoreError) as exc:
        LOGGER.warning("Failed to describe alarm %s: %s", alarm_name, exc)
        return AlarmState(name=alarm_name, state="UNKNOWN", reason=str(exc))

    alarms = response.get("MetricAlarms") or []
    if not alarms:
        return AlarmState(name=alarm_name, state="MISSING", reason="Alarm not found")

    alarm = alarms[0]
    return AlarmState(
        name=alarm_name,
        state=alarm.get("StateValue", "UNKNOWN"),
        reason=alarm.get("StateReason"),
    )


def _render_state(label: str, alarm: AlarmState) -> None:
    st.sidebar.write(f"{label}: `{alarm.state}`")
    if alarm.reason and alarm.state == "ALARM":
        with st.sidebar.expander(f"詳細 ({label})", expanded=False):
            st.caption(alarm.reason)


def display_billing_status_sidebar(environment: str, *, disabled: bool = False) -> None:
    """Render billing guardrail status inside the Streamlit sidebar."""
    st.sidebar.header("💳 Billing Status")

    if disabled:
        st.sidebar.info("デモモードでは請求アラームを取得しません")
        return

    client = get_cloudwatch_client()
    warn_name = f"MotionScan-{environment}-Billing-Warn"
    fail_name = f"MotionScan-{environment}-Billing-Fail"

    warn_alarm = _describe_alarm(client, warn_name)
    fail_alarm = _describe_alarm(client, fail_name)

    if fail_alarm.state == "ALARM":
        st.sidebar.error("FAIL: 上限超過 (Billing Guard 発動済みを要確認)")
    elif warn_alarm.state == "ALARM":
        st.sidebar.warning("WARN: 予算の80%に到達")
    elif warn_alarm.state == "MISSING" or fail_alarm.state == "MISSING":
        st.sidebar.warning("⚠️ アラーム未検出。スタックが最新か確認してください")
    else:
        st.sidebar.success("OK: 請求は安全圏内です")

    _render_state("WARN", warn_alarm)
    _render_state("FAIL", fail_alarm)

    st.sidebar.caption("Billingメトリクスは us-east-1 固定。Billing GuardはFAIL時に自動停止を実行します。")
