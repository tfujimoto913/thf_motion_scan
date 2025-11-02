"""
Purpose: Internationalization support for Streamlit dashboard
Responsibility: Translation dictionary and helper functions
Dependencies: streamlit
Created: 2025-11-03
Decision Log: ADR-031 (thresholds.json compatibility checker UI integration)

CRITICAL: This module provides i18n infrastructure for dashboard
"""

import streamlit as st
from typing import Dict


# Translation dictionary
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    'ja': {
        'version_info': 'バージョン情報',
        'rules': 'ルール',
        'normalization': '正規化',
        'updated': '更新',
        'build': 'ビルド',
        'compat_error': '互換性エラー',
        'compat_warning': '警告',
        'force_proceed': '強制的に続行（非推奨）',
        'force_active': '⚠️ 互換性エラーを無視して実行中',
        'retry': '再試行',
        'copied': 'コピーしました',
        'version_load_error': 'バージョン情報を取得できません'
    },
    'en': {
        'version_info': 'Version Info',
        'rules': 'Rules',
        'normalization': 'Normalization',
        'updated': 'Updated',
        'build': 'Build',
        'compat_error': 'Compatibility Error',
        'compat_warning': 'Warning',
        'force_proceed': 'Proceed anyway (not recommended)',
        'force_active': '⚠️ Running with compatibility error override',
        'retry': 'Retry',
        'copied': 'Copied',
        'version_load_error': 'Failed to load version information'
    }
}


def get_lang() -> str:
    """
    Get current language from session state.

    What: Retrieve language preference from Streamlit session
    Why: Support user language preference persistence
    Design Decision: Default to 'ja' for Japanese users

    Returns:
        str: Language code ('ja' or 'en')

    CRITICAL: Must initialize session_state if not present
    """
    if 'lang' not in st.session_state:
        st.session_state.lang = 'ja'
    return st.session_state.lang


def set_lang(lang: str) -> None:
    """
    Set language in session state.

    What: Update language preference
    Why: Allow user to switch language
    Design Decision: Validate language code before setting

    Args:
        lang: Language code ('ja' or 'en')

    CRITICAL: Only accept valid language codes
    """
    if lang in TRANSLATIONS:
        st.session_state.lang = lang
    else:
        raise ValueError(f"Unsupported language: {lang}")


def t(key: str) -> str:
    """
    Translate key to current language.

    What: Lookup translation for given key
    Why: Provide convenient translation access throughout dashboard
    Design Decision: Return key itself if translation not found (fail gracefully)

    Args:
        key: Translation key

    Returns:
        str: Translated string or key if not found

    CRITICAL: Must not raise exception if key missing (graceful degradation)
    """
    lang = get_lang()
    return TRANSLATIONS.get(lang, {}).get(key, key)


def toggle_lang() -> None:
    """
    Toggle between Japanese and English.

    What: Switch language between ja and en
    Why: Provide quick language switching for users
    Design Decision: Binary toggle (ja <-> en)

    CRITICAL: Must trigger Streamlit rerun to update UI
    """
    current = get_lang()
    new_lang = 'en' if current == 'ja' else 'ja'
    set_lang(new_lang)
