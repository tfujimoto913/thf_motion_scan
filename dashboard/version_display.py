"""
Purpose: Display thresholds.json version information in Streamlit dashboard
Responsibility: Version display UI and compatibility checking
Dependencies: streamlit, src.config, dashboard.i18n
Created: 2025-11-03
Decision Log: ADR-031 (thresholds.json compatibility checker UI integration)

CRITICAL: This module integrates compatibility checking into dashboard UI
"""

import json
import streamlit as st
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from src.config.loader import load_thresholds, get_versions
from src.config.compat import check_compat
from dashboard.i18n import t


def load_required_versions() -> Tuple[Dict[str, str], Dict[str, Any]]:
    """
    Load required versions from config file.

    What: Read required_versions.json
    Why: Separate configuration from code
    Design Decision: Fall back to empty dict if file missing

    Returns:
        Dict with required version fields

    CRITICAL: Must handle file not found gracefully
    """
    config_path = Path(__file__).parent.parent / "config" / "required_versions.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        st.warning(f"⚠️ Could not load required_versions.json: {t('retry')}")
        return {}, {}
    except json.JSONDecodeError as exc:
        st.warning(f"⚠️ required_versions.json parse error: {exc}")
        return {}, {}

    required = {
        k: v for k, v in data.items()
        if k in {"rules_version", "thresholds_version"}
    }
    metadata = {k: v for k, v in data.items() if k not in required}
    return required, metadata


def _summarize_details(details: Any, fallback_reason: Optional[str], limit: int = 3) -> List[str]:
    """Convert compatibility details dict into a concise bullet list."""
    summaries: List[str] = []

    if isinstance(fallback_reason, str) and fallback_reason.strip():
        summaries.append(fallback_reason.strip())

    if isinstance(details, dict):
        for field, detail in sorted(details.items()):
            if not isinstance(detail, dict):
                continue
            reason = detail.get("reason")
            if isinstance(reason, str) and reason.strip():
                summaries.append(f"{field}: {reason.strip()}")
            else:
                status = detail.get("status")
                current = detail.get("current") or detail.get("current_version")
                expected = detail.get("required") or detail.get("expected")
                parts = [str(part) for part in (status, current, expected) if part]
                if parts:
                    summaries.append(f"{field}: {' / '.join(parts)}")
            if len(summaries) >= limit:
                break

    return summaries[:limit]


def display_versions() -> None:
    """
    Display version information and perform compatibility check.

    What: Show thresholds.json versions in sidebar with compatibility validation
    Why: Inform users of current configuration and block incompatible versions
    Design Decision: Use sidebar for persistent visibility, session_state for override

    Flow:
    1. Load thresholds.json and required_versions.json
    2. Perform compatibility check
    3. Display versions in sidebar
    4. Show error/warning based on compatibility status
    5. Block execution if ERROR and no override

    CRITICAL: Must call st.stop() to block execution on ERROR
    """
    if 'force_override' not in st.session_state:
        st.session_state.force_override = False

    try:
        thresholds_path = Path(__file__).parent.parent / "config" / "thresholds.json"
        data = load_thresholds(str(thresholds_path))
        versions = get_versions(data) or {}
        metadata = data.get('metadata', {})

        required, required_meta = load_required_versions()
        if required:
            compat_result = check_compat(versions, required)
        else:
            compat_result = {
                'status': 'OK',
                'reason': 'No required versions specified',
                'details': {},
            }

        with st.sidebar:
            st.markdown(f"### 📊 {t('version_info')}")

            rules_version = versions.get('rules_version', 'N/A')
            thresholds_version = versions.get('thresholds_version', 'N/A')
            normalization_version = versions.get('normalization_version')

            st.text(f"{t('rules')}: {rules_version}")
            st.text(f"{t('thresholds')}: {thresholds_version}")
            if normalization_version not in (None, ""):
                st.text(f"{t('normalization')}: {normalization_version}")
            else:
                st.caption(f"ℹ️ {t('normalization_future')}")

            updated_at = metadata.get('updated_at', 'N/A')
            updated_at_display = updated_at[:10] if isinstance(updated_at, str) and updated_at else 'N/A'
            st.text(f"{t('updated')}: {updated_at_display}")

            artifact_sha = versions.get('artifact_sha', 'N/A')
            if isinstance(artifact_sha, str) and artifact_sha:
                display_sha = artifact_sha[:7]
                if st.button(f"📋 {t('build')}: {display_sha}"):
                    st.info(f"{t('copied')}: {artifact_sha}")
            else:
                st.text(f"{t('build')}: {artifact_sha}")

            if required_meta.get('notes'):
                st.caption(str(required_meta['notes']))

            if 'force_override_pending' not in st.session_state:
                st.session_state.force_override_pending = None

            st.markdown("---")

            status = (compat_result.get('status') or 'UNKNOWN').upper()
            reason = compat_result.get('reason')
            details = compat_result.get('details') or {}
            summary_lines = _summarize_details(details, reason)

            if status != 'ERROR':
                st.session_state.force_override = False
                st.session_state.pop('force_override_pending', None)

            if status == 'ERROR':
                st.error(f"⚠️ {t('compat_error')}")
                if summary_lines:
                    for line in summary_lines:
                        st.caption(f"• {line}")

                pending_summary = st.session_state.get('force_override_pending')

                if st.session_state.force_override:
                    st.warning(t('force_active'))
                elif pending_summary is None:
                    if st.button(t('force_proceed'), key="force_override_start"):
                        st.session_state.force_override_pending = summary_lines or [t('compat_error')]
                        st.experimental_rerun()
                    st.stop()
                else:
                    st.warning(t('force_override_prompt'))
                    if pending_summary:
                        st.markdown(f"**{t('force_override_reasons')}**")
                        for line in pending_summary:
                            st.markdown(f"- {line}")
                    confirm_col, cancel_col = st.columns(2)
                    with confirm_col:
                        if st.button(t('force_override_confirm'), key="force_override_confirm", use_container_width=True):
                            st.session_state.force_override = True
                            st.session_state.pop('force_override_pending', None)
                            st.experimental_rerun()
                    with cancel_col:
                        if st.button(t('force_override_cancel'), key="force_override_cancel", use_container_width=True):
                            st.session_state.pop('force_override_pending', None)
                            st.stop()
                    st.stop()

            elif status == 'WARN':
                st.warning(f"ℹ️ {t('compat_warning')}")
                if reason:
                    st.warning(reason)
            elif status == 'OK':
                st.success(f"✅ {t('compat_ok')}")
                if reason:
                    st.caption(reason)
            else:
                if reason:
                    st.info(reason)

            if details:
                with st.expander(t('compat_details')):
                    for field, detail in details.items():
                        detail_status = (detail.get('status') or '').lower()
                        status_label = {
                            'ok': t('status_ok'),
                            'warn': t('status_warn'),
                            'error': t('status_error'),
                        }.get(detail_status, detail.get('status', 'N/A'))
                        reason_text = detail.get('reason') or ''
                        st.markdown(f"- **{field}**: {status_label} — {reason_text}")

    except Exception as e:
        st.error(f"❌ {t('version_load_error')}: {e}")
        if st.button(t('retry')):
            st.rerun()
        st.stop()
