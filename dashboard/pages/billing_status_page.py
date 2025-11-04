"""
Purpose: Billing Status ページ（メインタブ）
Responsibility: Billing状態の可視化、アラート表示
Created: 2025-11-04 by Claude Code
Decision Log: ADR-TBD（Billing Status UI実装）

CRITICAL:
- Step 1: スタブ実装（固定値、開発用切替）
- Step 2: CloudWatch実値取得（予定）
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import streamlit as st


def get_billing_status() -> dict:
    """
    What: Billing状態取得（スタブ）
    Why: Step 2でCloudWatch連携時にI/F変更なし

    Design Decision:
    - 戻り値構造を先に定義し、実装切替を容易に
    - Step 2でCloudWatch APIと差し替え

    Returns:
        dict: {
            "status": "OK|WARN|FAIL",
            "current_cost": float,
            "threshold_warn": float,
            "threshold_fail": float,
            "last_updated": Optional[datetime]
        }

    CRITICAL: Step 1ではスタブ固定値を返す
    """
    return {
        "status": "OK",
        "current_cost": 0.0,
        "threshold_warn": 80.0,
        "threshold_fail": 100.0,
        "last_updated": None,
    }


def render_billing_status_page() -> None:
    """
    What: Billing Status ページのレンダリング
    Why: Billing状態を独立したタブで可視化

    Design Decision:
    - サイドバー表示（billing_status.py）とは別に、メインタブで詳細表示
    - 開発用切替ボタンで3状態を確認可能（本番では削除予定）

    CRITICAL: Step 1ではスタブ値を表示、Step 2で実値連携
    """
    st.title("💳 Billing Status")

    # 開発用：状態切替
    st.markdown("### 🔧 開発用コントロール")
    dev_status = st.radio(
        "状態を切り替えてUIを確認",
        ["OK", "WARN", "FAIL"],
        horizontal=True,
        help="本番環境ではCloudWatchから自動取得（このコントロールは削除予定）",
    )

    # スタブデータ取得
    billing_data = get_billing_status()
    billing_data["status"] = dev_status  # 開発用上書き

    st.markdown("---")
    st.markdown("### 📊 現在の状態")

    # 状態バッジ表示
    if billing_data["status"] == "OK":
        st.success("✅ **OK**: 請求は安全圏内です")
        st.info("**アクション不要** - システムは正常に動作しています")
    elif billing_data["status"] == "WARN":
        st.warning("⚠️ **WARN**: 予算の80%に到達")
        st.info(
            "**注意推奨** - コストが予算の80%に達しました。不要なリソースがないか確認してください"
        )
    else:
        st.error("🚨 **FAIL**: 上限超過 (Billing Guard 発動済みを要確認)")
        st.warning(
            "**即座対応必要** - 自動停止が発動している可能性があります。AWSコンソールで状態を確認してください"
        )

    # 詳細情報（スタブ値）
    st.markdown("---")
    st.markdown("### 📈 コスト詳細")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "現在のコスト",
            f"${billing_data['current_cost']:.2f}",
            help="当月の累積コスト（スタブ値：$0.00）",
        )
    with col2:
        st.metric(
            "WARN閾値",
            f"${billing_data['threshold_warn']:.2f}",
            help="この金額に達するとWARNアラートが発動（スタブ値：$80.00）",
        )
    with col3:
        st.metric(
            "FAIL閾値",
            f"${billing_data['threshold_fail']:.2f}",
            help="この金額に達するとFAILアラートと自動停止が発動（スタブ値：$100.00）",
        )

    # 更新時刻
    if billing_data["last_updated"]:
        st.caption(f"最終更新: {billing_data['last_updated'].strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        st.caption("最終更新: N/A（スタブモード）")

    # Step 2への注意書き
    st.markdown("---")
    with st.expander("📝 実装ステータス"):
        st.markdown("""
        **Step 1（現在）**: スタブ実装
        - 固定値を表示
        - 開発用切替ボタンでUI確認

        **Step 2（予定）**: CloudWatch実値取得
        - CloudWatchアラーム状態を取得
        - 実際のコストデータを表示
        - 自動更新機能追加
        """)

    st.caption("※ 現在はスタブ実装。Step 2でCloudWatch実値取得を実装予定")
