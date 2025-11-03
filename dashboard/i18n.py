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
        'thresholds': 'しきい値',
        'normalization': '正規化',
        'normalization_future': '正規化バージョンは将来の拡張で追加予定',
        'updated': '更新',
        'build': 'ビルド',
        'compat_error': '互換性エラー',
        'compat_warning': '警告',
        'compat_ok': '互換性は問題ありません',
        'compat_details': '互換性の詳細',
        'force_proceed': '強制的に続行（非推奨）',
        'force_override_prompt': '互換性エラーのため処理が停止しています。意図的に続行する場合は理由を確認してください。',
        'force_override_reasons': '主な理由',
        'force_override_confirm': '理由を理解した上で続行',
        'force_override_cancel': 'キャンセル',
        'force_active': '⚠️ 互換性エラーを無視して実行しています',
        'retry': '再試行',
        'copied': 'コピーしました',
        'version_load_error': 'バージョン情報を取得できません',
        'status_ok': 'OK',
        'status_warn': '警告',
        'status_error': 'エラー',
        'validation_state': 'Validationステータス',
        'valid_reps': '有効レップ数',
        'valid_reps_hint': 'QCを通過したレップ数 / 総レップ数',
        'fixture_category_valid': '有効データ',
        'fixture_category_invalid': '想定外データ',
        'pdf_generate': 'PDFレポートを生成',
        'pdf_confirm_title': 'PDFレポート生成の確認',
        'pdf_confirm_message': 'このセッションのPDFレポートを生成しますか？',
        'pdf_confirm_yes': '生成する',
        'pdf_confirm_no': 'キャンセル',
        'pdf_generated': 'PDFレポートを生成しました',
        'pdf_generation_failed': 'PDFレポートの生成に失敗しました',
        'pdf_download': 'PDFをダウンロード',
        'pdf_versions_caption': '生成時のバージョン'
    },
    'en': {
        'version_info': 'Version Info',
        'rules': 'Rules',
        'thresholds': 'Thresholds',
        'normalization': 'Normalization',
        'normalization_future': 'Normalization version will be added in a future update.',
        'updated': 'Updated',
        'build': 'Build',
        'compat_error': 'Compatibility Error',
        'compat_warning': 'Warning',
        'compat_ok': 'All versions compatible',
        'compat_details': 'Compatibility details',
        'force_proceed': 'Proceed anyway (not recommended)',
        'force_override_prompt': 'Processing is blocked due to incompatibility. Review the reasons before forcing execution.',
        'force_override_reasons': 'Primary reasons',
        'force_override_confirm': 'Continue despite the error',
        'force_override_cancel': 'Cancel',
        'force_active': '⚠️ Running with compatibility override enabled',
        'retry': 'Retry',
        'copied': 'Copied',
        'version_load_error': 'Failed to load version information',
        'status_ok': 'OK',
        'status_warn': 'Warning',
        'status_error': 'Error',
        'validation_state': 'Validation State',
        'valid_reps': 'Valid Reps',
        'valid_reps_hint': 'QC-passed reps / total reps',
        'fixture_category_valid': 'Valid sample',
        'fixture_category_invalid': 'Invalid sample',
        'pdf_generate': 'Generate PDF Report',
        'pdf_confirm_title': 'Confirm PDF generation',
        'pdf_confirm_message': 'Generate a PDF report for this session?',
        'pdf_confirm_yes': 'Generate',
        'pdf_confirm_no': 'Cancel',
        'pdf_generated': 'Generated PDF report',
        'pdf_generation_failed': 'Failed to generate PDF report',
        'pdf_download': 'Download PDF',
        'pdf_versions_caption': 'Versions at generation time'
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
