"""
Purpose: Validation State badge component for Streamlit Dashboard
Responsibility: Display validation state (OK/WARN/ERROR) with color-coded badges
Dependencies: streamlit
Created: 2025-11-03 by Claude Code
Decision Log: Task D - Streamlit v2.1統合

CRITICAL:
- 3状態の色分け: OK=緑、WARN=黄、ERROR=赤
- ツールチップでvalidation.reasons表示
- versions欠落時もクラッシュしない
"""

from __future__ import annotations

from typing import Dict, List, Optional

import streamlit as st


def render_validation_badge(
    validation: Optional[Dict],
    versions: Optional[Dict] = None,
    show_legend: bool = False,
) -> None:
    """
    What: Validation Stateバッジを表示
    Why: セッション詳細画面でOK/WARN/ERRORを可視化
    Design Decision: Streamlit native colorでシンプル実装

    Args:
        validation: validation.state + validation.reasons
        versions: versions.rules_version等（オプショナル）
        show_legend: ステート凡例を表示するか

    Side Effects:
        - st.markdown でバッジ表示
        - st.caption でversions表示（あれば）

    CRITICAL:
    - validation未取得時はバッジ非表示でフォールバック
    - state不正値は"UNKNOWN"扱い
    """
    # validationが存在しない場合はフォールバック
    if not validation:
        st.caption("ℹ️ Validation情報なし")
        return

    state = validation.get("state", "UNKNOWN")
    # reasonsまたはviolationsをサポート（両方の命名規則に対応）
    reasons = validation.get("reasons", [])
    violations = validation.get("violations", [])

    # violationsがある場合は、そこからメッセージを抽出
    if violations and not reasons:
        reasons = [v.get("message", str(v)) for v in violations if isinstance(v, dict)]

    # 状態ごとの色・アイコン・メッセージ定義
    state_config = {
        "OK": {
            "color": "green",
            "icon": "✅",
            "label": "OK",
            "message": "すべての評価が基準を満たしています",
        },
        "WARN": {
            "color": "orange",
            "icon": "⚠️",
            "label": "WARN",
            "message": "一部の評価が警告範囲です（続行可能）",
        },
        "ERROR": {
            "color": "red",
            "icon": "❌",
            "label": "ERROR",
            "message": "評価基準を満たしていません",
        },
        "UNKNOWN": {
            "color": "gray",
            "icon": "❓",
            "label": "UNKNOWN",
            "message": "Validation状態が不明です",
        },
    }

    config = state_config.get(state, state_config["UNKNOWN"])

    # バッジ表示（Streamlitネイティブスタイル）
    st.markdown(
        f":{config['color']}[{config['icon']} **{config['label']}**]"
    )

    # ツールチップ（reasonsがある場合）
    if reasons:
        with st.expander("📋 詳細理由を表示"):
            for reason in reasons:
                st.markdown(f"- {reason}")
    else:
        st.caption(config["message"])

    # versions情報表示（オプション）
    if versions:
        rules_version = versions.get("rules_version", "N/A")
        thresholds_version = versions.get("thresholds_version", "N/A")
        artifact_sha = versions.get("artifact_sha", "N/A")

        # artifact_shaは最初の7文字のみ表示
        if isinstance(artifact_sha, str) and len(artifact_sha) > 7:
            artifact_sha = artifact_sha[:7]

        st.caption(
            f"📌 Rules: `{rules_version}` | Thresholds: `{thresholds_version}` | Build: `{artifact_sha}`"
        )

    # 凡例表示（オプション）
    if show_legend:
        st.markdown("---")
        st.caption(
            "**凡例**: ✅ OK（基準内） | ⚠️ WARN（警告、続行可） | ❌ ERROR（基準外）"
        )


def render_validation_summary(
    validation: Optional[Dict],
    compact: bool = False,
) -> None:
    """
    What: Validation State サマリー表示（1行コンパクト版）
    Why: リスト表示等でコンパクトな表示が必要な場合
    Design Decision: アイコン + ラベルのみのシンプル表示

    Args:
        validation: validation.state + validation.reasons
        compact: Trueの場合はアイコンのみ

    Side Effects:
        - st.markdown で1行バッジ表示

    CRITICAL: validation未取得時は空文字列返却（クラッシュしない）
    """
    if not validation:
        st.caption("ℹ️ N/A")
        return

    state = validation.get("state", "UNKNOWN")

    state_config = {
        "OK": {"color": "green", "icon": "✅", "label": "OK"},
        "WARN": {"color": "orange", "icon": "⚠️", "label": "WARN"},
        "ERROR": {"color": "red", "icon": "❌", "label": "ERROR"},
        "UNKNOWN": {"color": "gray", "icon": "❓", "label": "UNKNOWN"},
    }

    config = state_config.get(state, state_config["UNKNOWN"])

    if compact:
        st.markdown(f":{config['color']}[{config['icon']}]")
    else:
        st.markdown(f":{config['color']}[{config['icon']} {config['label']}]")
