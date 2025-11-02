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
        versions = get_versions(data)
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

            # Version fields
            st.text(f"{t('rules')}: {versions.get('rules_version', 'N/A')}")
            st.text(f"{t('normalization')}: {versions.get('normalization_version', 'N/A')}")

            # Updated date (format: YYYY-MM-DD)
            updated_at = metadata.get('updated_at', 'N/A')
            if updated_at != 'N/A' and len(updated_at) >= 10:
                updated_at = updated_at[:10]
            st.text(f"{t('updated')}: {updated_at}")

            # Build hash (first 7 chars)
            artifact_sha = versions.get('artifact_sha', 'N/A')
            if artifact_sha != 'N/A' and len(artifact_sha) >= 7:
                display_sha = artifact_sha[:7]
            else:
                display_sha = artifact_sha

            if st.button(f"📋 {t('build')}: {display_sha}"):
                st.write(f"✅ {artifact_sha}")

            st.markdown("---")

            # Compatibility status
            if compat_result['status'] == 'ERROR':
                st.error(f"⚠️ {t('compat_error')}")
                st.error(compat_result['reason'])

                if not st.session_state.force_override:
                    if st.button(t('force_proceed')):
                        st.session_state.force_override = True
                        st.rerun()
                    st.stop()  # Block execution
                else:
                    st.warning(t('force_active'))

            elif compat_result['status'] == 'WARN':
                st.warning(f"ℹ️ {t('compat_warning')}")
                st.warning(compat_result['reason'])

    except Exception as e:
        st.error(f"❌ {t('version_load_error')}: {e}")
        if st.button(t('retry')):
            st.rerun()
        st.stop()  # Block execution on error
