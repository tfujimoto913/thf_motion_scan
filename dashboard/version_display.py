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
from typing import Dict, Any

from src.config.loader import load_thresholds, get_versions
from src.config.compat import check_compat
from dashboard.i18n import t


def load_required_versions() -> Dict[str, str]:
    """
    Load required versions from config file.

    What: Read required_versions.json
    Why: Separate configuration from code
    Design Decision: Fall back to empty dict if file missing

    Returns:
        Dict with required version fields

    CRITICAL: Must handle file not found gracefully
    """
    try:
        config_path = Path(__file__).parent.parent / "config" / "required_versions.json"
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {k: v for k, v in data.items() if k != 'notes'}
    except Exception as e:
        st.warning(f"⚠️ Could not load required_versions.json: {e}")
        return {}


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
    # Initialize session state
    if 'force_override' not in st.session_state:
        st.session_state.force_override = False

    try:
        # Load thresholds and required versions
        thresholds_path = Path(__file__).parent.parent / "config" / "thresholds.json"
        data = load_thresholds(str(thresholds_path))
        versions = get_versions(data) or {}
        metadata = data.get('metadata', {})

        required = load_required_versions()

        # Perform compatibility check
        if required:
            compat_result = check_compat(versions, required)
        else:
            # No required versions → assume OK
            compat_result = {
                'status': 'OK',
                'reason': 'No required versions specified',
                'details': {}
            }

        # Display in sidebar
        with st.sidebar:
            st.markdown(f"### 📊 {t('version_info')}")

            rules_version = versions.get('rules_version', 'N/A')
            thresholds_version = versions.get('thresholds_version', 'N/A')
            normalization_version = versions.get('normalization_version')

            st.text(f"{t('rules')}: {rules_version}")
            st.text(f"{t('thresholds')}: {thresholds_version}")
            if normalization_version is not None:
                st.text(f"{t('normalization')}: {normalization_version}")

            # Updated date (format: YYYY-MM-DD)
            updated_at = metadata.get('updated_at', 'N/A')
            if isinstance(updated_at, str) and updated_at and updated_at != 'N/A':
                updated_at_display = updated_at[:10]
            else:
                updated_at_display = 'N/A'
            st.text(f"{t('updated')}: {updated_at_display}")

            # Build hash (first 7 chars)
            artifact_sha = versions.get('artifact_sha', 'N/A')
            display_sha = artifact_sha
            if isinstance(artifact_sha, str) and len(artifact_sha) >= 7:
                display_sha = artifact_sha[:7]

            if isinstance(artifact_sha, str) and artifact_sha and artifact_sha != 'N/A':
                if st.button(f"📋 {t('build')}: {display_sha}"):
                    st.info(f"{t('copied')}: {artifact_sha}")
            else:
                st.text(f"{t('build')}: {artifact_sha}")

            st.markdown("---")

            status = compat_result.get('status', 'UNKNOWN')
            reason = compat_result.get('reason', '')

            if status == 'ERROR':
                st.error(f"⚠️ {t('compat_error')}")
                if reason:
                    st.error(reason)

                if not st.session_state.force_override:
                    if st.button(t('force_proceed')):
                        st.session_state.force_override = True
                        st.rerun()
                    st.stop()  # Block execution
                else:
                    st.warning(t('force_active'))

            elif status == 'WARN':
                st.warning(f"ℹ️ {t('compat_warning')}")
                if reason:
                    st.warning(reason)

            elif status == 'OK':
                st.success(f"✅ {t('compat_ok')}")
                if reason:
                    st.caption(reason)
            else:
                # Unknown status fallback
                if reason:
                    st.info(reason)

            details = compat_result.get('details') or {}
            if details:
                with st.expander(t('compat_details')):
                    for field, detail in details.items():
                        detail_status = (detail.get('status') or '').lower()
                        status_label = {
                            'ok': t('status_ok'),
                            'warn': t('status_warn'),
                            'error': t('status_error'),
                        }.get(detail_status, detail.get('status', 'N/A'))
                        reason_text = detail.get('reason', '')
                        st.markdown(f"- **{field}**: {status_label} — {reason_text}")

    except Exception as e:
        st.error(f"❌ {t('version_load_error')}: {e}")
        if st.button(t('retry')):
            st.rerun()
        st.stop()  # Block execution on error
