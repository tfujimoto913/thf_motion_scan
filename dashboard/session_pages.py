"""
Purpose: セッション一覧・詳細ページ（Phase 5 MVP）
Responsibility: 7種目をまとめた1セッション単位で表示
Dependencies: streamlit, session_dao
Created: 2025-11-01 by Claude Code
Decision Log: Phase 5 - Stage 2 (ADR-023)

CRITICAL:
  - 1セッション = athlete_id + session_id（7種目を集約）
  - 総合スコア = 7種目×80点 = 560点満点
  - is_complete=False の場合は「撮影途中」表示
"""
import streamlit as st
from typing import Dict, Any, List
from decimal import Decimal
from session_dao import get_latest_sessions


def session_list_page(dynamodb, resources, demo_mode=False):
    """
    What: セッション一覧ページ
    Why: 7種目をまとめた1セッション単位で表示
    Design Decision: カード形式、560点満点表示、最大12セッション（ADR-023）

    Args:
        dynamodb: DynamoDB resource
        resources: AWSリソース名
        demo_mode: デモモードフラグ

    CRITICAL:
      - 総合スコア = 7種目×80点 = 560点満点
      - 最大12セッションまで表示
    """
    st.header("📊 セッション一覧（560点満点）")

    # デモモード時の表示
    if demo_mode:
        st.info("🎭 **デモモード**: サンプルデータを表示中")
        from demo_data import get_demo_results
        items = get_demo_results()
    else:
        if not resources:
            st.error("❌ AWS設定エラー: AccountIdが取得できません")
            return

        try:
            table = dynamodb.Table(resources['table_name'])
            response = table.scan()
            items = response['Items']
        except Exception as e:
            st.error(f"❌ データ取得エラー: {str(e)}")
            return

    # データチェック
    if not items:
        st.warning("評価結果がありません。動画をアップロードしてください。")
        return

    try:
        # Decimal型をfloat型に変換
        def convert_decimals(obj):
            """DynamoDB Decimal型をfloatに再帰的に変換"""
            if isinstance(obj, list):
                return [convert_decimals(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: convert_decimals(value) for key, value in obj.items()}
            elif isinstance(obj, Decimal):
                return float(obj)
            return obj

        items_converted = [convert_decimals(item) for item in items]

        # メタデータ除外
        items_filtered = [
            item for item in items_converted
            if not str(item.get('video_id', '')).startswith('METADATA')
        ]

        if not items_filtered:
            st.warning("評価結果がありません。動画をアップロードしてください。")
            return

        # セッション単位にグルーピング
        sessions = get_latest_sessions(items_filtered, limit=12)

        if not sessions:
            st.warning("セッションデータがありません。")
            return

        st.markdown(f"**表示件数**: {len(sessions)}件（最大12件）")
        st.markdown("---")

        # カード形式で表示（2列レイアウト）
        for i in range(0, len(sessions), 2):
            col1, col2 = st.columns(2)

            # 左列のカード
            with col1:
                if i < len(sessions):
                    render_session_card(sessions[i])

            # 右列のカード
            with col2:
                if i + 1 < len(sessions):
                    render_session_card(sessions[i + 1])

    except Exception as e:
        st.error(f"❌ データ処理エラー: {str(e)}")
        import traceback
        with st.expander("詳細エラー情報"):
            st.code(traceback.format_exc())


def render_session_card(session: Dict[str, Any]):
    """
    What: セッションカードを描画
    Why: 各セッションの概要を視覚的に表示
    Design Decision: Streamlit containerとmetricsでカード風表示

    Args:
        session: セッションデータ（group_tests_by_sessionの出力）

    CRITICAL:
      - grand_total: 総合スコア
      - grand_max: 560点（最大スコア）
      - is_complete: 7種目完了か
      - rules_version: 'v2.1'または'mixed'
    """
    with st.container():
        # カード外枠（CSSスタイル）
        st.markdown(
            """
            <div style="
                border: 2px solid #e0e0e0;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 20px;
                background-color: #f9f9f9;">
            """,
            unsafe_allow_html=True
        )

        # カードヘッダー
        athlete_id = session.get('athlete_id', 'Unknown')
        session_id = session.get('session_id', 'Unknown')
        st.subheader(f"👤 {athlete_id}")
        st.caption(f"セッション: {session_id}")

        # スコア表示
        grand_total = session.get('grand_total', 0)
        grand_max = session.get('grand_max', 560)
        percentage = session.get('percentage', 0)

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("総合スコア", f"{grand_total:.1f}/{grand_max}")

        with col2:
            # 達成率に応じた色
            if percentage >= 80:
                color_emoji = "🟢"
            elif percentage >= 60:
                color_emoji = "🟡"
            else:
                color_emoji = "🔴"
            st.metric("達成率", f"{percentage:.1f}%", delta=color_emoji)

        with col3:
            # 完了状況
            is_complete = session.get('is_complete', False)
            if is_complete:
                st.metric("完了状況", "✅ 完了")
            else:
                test_count = len(session.get('tests', []))
                st.metric("完了状況", f"📝 {test_count}/7種目")

        # ルールバージョン
        rules_version = session.get('rules_version', 'unknown')
        has_mismatch = session.get('has_version_mismatch', False)

        if has_mismatch:
            st.warning(f"⚠️ ルールバージョン混在: {rules_version}")
        else:
            st.info(f"📋 ルールバージョン: {rules_version}")

        # 詳細ボタン
        if st.button(f"詳細を表示", key=f"session_{athlete_id}_{session_id}"):
            st.session_state['selected_session'] = {
                'athlete_id': athlete_id,
                'session_id': session_id
            }
            st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")
