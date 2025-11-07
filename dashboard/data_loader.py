"""Data loading helpers with caching and structured logging."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
import streamlit as st

from config import PERFORMANCE_LIMITS
from demo_data import get_demo_results
from utils import log_dashboard_event, record_error


@st.cache_data(ttl=PERFORMANCE_LIMITS["cache_ttl_seconds"], show_spinner=False)
def cached_scan_results(table_name: str) -> List[Dict[str, Any]]:
    """Scan the DynamoDB results table with caching and pagination handling."""

    table = boto3.resource('dynamodb').Table(table_name)
    items: List[Dict[str, Any]] = []

    response = table.scan()
    items.extend(response.get('Items', []))

    while response.get('LastEvaluatedKey'):
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    return items


def load_results_items(resources: Optional[Dict[str, Any]], demo_mode: bool = False) -> List[Dict[str, Any]]:
    """Load evaluation items with caching and structured logging."""

    if demo_mode:
        items = get_demo_results()
        log_dashboard_event(
            "data_fetch",
            source="demo",
            item_count=len(items),
            cache_hit=False,
        )
        return items

    if not resources:
        log_dashboard_event("data_fetch_error", level=40, reason="missing_resources")
        raise ValueError("Resources are required when demo_mode is False")

    table_name = resources['table_name']
    cache_key = f"dynamodb::{table_name}"
    ttl_seconds = PERFORMANCE_LIMITS['cache_ttl_seconds']
    cache_metadata = st.session_state.setdefault('cache_metadata', {})
    now = datetime.now(timezone.utc)

    last_fetched = cache_metadata.get(cache_key)
    cache_hit = False
    if isinstance(last_fetched, datetime):
        cache_hit = (now - last_fetched).total_seconds() < ttl_seconds

    try:
        items = cached_scan_results(table_name)
    except Exception as exc:
        cached_scan_results.clear()
        log_dashboard_event(
            "data_fetch_error",
            level=40,
            source="dynamodb",
            table=table_name,
            error=str(exc),
        )
        record_error("load_results_items", str(exc))
        raise

    cache_metadata[cache_key] = now

    log_dashboard_event(
        "data_fetch",
        source="dynamodb",
        table=table_name,
        item_count=len(items),
        cache_hit=cache_hit,
    )

    return items
