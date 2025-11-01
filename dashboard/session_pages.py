"""
Purpose: セッション一覧・詳細ページ（Phase 5 MVP）
Responsibility: 7種目をまとめた1セッション単位で表示
Dependencies: streamlit, session_dao, config
Created: 2025-11-01 by Claude Code
Decision Log: Phase 5 - Stage 2/3 (ADR-023)

CRITICAL:
  - 1セッション = athlete_id + session_id（7種目を集約）
  - 総合スコア = 7種目×80点 = 560点満点
  - is_complete=False の場合は「撮影途中」表示
"""
import streamlit as st
from typing import Dict, Any, List
from decimal import Decimal
from datetime import datetime, timezone
import plotly.graph_objects as go
from session_dao import get_latest_sessions, get_session_by_id
from data_loader import load_results_items
from config import TEST_TYPES, TEST_TYPE_DISPLAY, TEST_SHORT_MAP


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

    try:
        items = load_results_items(resources, demo_mode)
    except ValueError:
        st.error("❌ AWS設定エラー: AccountIdが取得できません")
        return
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


def session_detail_page(dynamodb, resources, demo_mode=False):
    """
    What: セッション詳細画面
    Why: 7種目のスコア内訳とレーダーチャートで詳細可視化
    Design Decision: Plotlyレーダーチャート、7種目テーブル、鮮度表示（ADR-023 Stage 3）

    Args:
        dynamodb: DynamoDB resource
        resources: AWSリソース名
        demo_mode: デモモードフラグ

    CRITICAL:
      - 総合スコア = 7種目×80点 = 560点満点
      - 欠測値（7種目未満）は0%表示またはグレーアウト
    """
    # session_state から選択セッションを取得
    selected_session = st.session_state.get('selected_session')

    if not selected_session:
        st.warning("セッションが選択されていません。一覧画面に戻ります。")
        if st.button("← 一覧に戻る"):
            st.session_state.pop('selected_session', None)
            st.rerun()
        return

    athlete_id = selected_session['athlete_id']
    session_id = selected_session['session_id']

    # データ取得
    if demo_mode:
        st.info("🎭 **デモモード**: サンプルデータを表示中")

    try:
        items = load_results_items(resources, demo_mode)
    except ValueError:
        st.error("❌ AWS設定エラー: AccountIdが取得できません")
        return
    except Exception as e:
        st.error(f"❌ データ取得エラー: {str(e)}")
        return

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

    # セッション取得
    session = get_session_by_id(items_filtered, athlete_id, session_id)

    if not session:
        st.error(f"❌ セッションが見つかりません: {athlete_id} / {session_id}")
        if st.button("← 一覧に戻る"):
            st.session_state.pop('selected_session', None)
            st.rerun()
        return

    # ========== ヘッダー部分 ==========
    st.header(f"📊 セッション詳細 - {athlete_id}")
    st.caption(f"セッションID: {session_id}")

    # 戻るボタン
    if st.button("← 一覧に戻る"):
        st.session_state.pop('selected_session', None)
        st.rerun()

    st.markdown("---")

    # 総合スコア表示
    grand_total = session.get('grand_total', 0)
    grand_max = session.get('grand_max', 560)
    percentage = session.get('percentage', 0)
    rules_version = session.get('rules_version', 'unknown')

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("総合スコア", f"{grand_total:.1f}/{grand_max}")

    with col2:
        st.metric("達成率", f"{percentage:.1f}%")

    with col3:
        st.metric("ルールバージョン", rules_version)

    with col4:
        # データ鮮度表示（"X日前"）
        processed_at = session.get('processed_at', '')
        if processed_at:
            freshness = _calculate_data_freshness(processed_at)
            st.metric("データ鮮度", freshness)
        else:
            st.metric("データ鮮度", "不明")

    st.markdown("---")

    # ========== 7種目スコアテーブル ==========
    st.subheader("📋 7種目スコア内訳")

    test_scores = _extract_test_scores(session)

    if test_scores:
        _render_test_scores_table(test_scores)
    else:
        st.warning("スコアデータがありません。")

    st.markdown("---")

    # ========== レーダーチャート ==========
    st.subheader("📈 レーダーチャート（達成率）")

    if test_scores:
        _render_radar_chart(test_scores)
    else:
        st.warning("レーダーチャート表示に必要なデータがありません。")


def _calculate_data_freshness(processed_at: str) -> str:
    """
    What: データ鮮度を計算（"X日前"形式）
    Why: コーチがデータの新旧を判断するため
    Design Decision: ISO8601形式のタイムスタンプから計算

    Args:
        processed_at: ISO8601形式のタイムスタンプ（例: "2025-10-31T15:25:00"）

    Returns:
        str: "X日前"形式の文字列

    CRITICAL: タイムゾーン考慮（UTC基準）
    """
    try:
        # ISO8601形式をパース（タイムゾーンなしの場合はUTCと仮定）
        if 'T' in processed_at:
            dt = datetime.fromisoformat(processed_at.replace('Z', '+00:00'))
        else:
            # 日付のみの場合
            dt = datetime.fromisoformat(processed_at)

        # タイムゾーン未設定の場合はUTCと仮定
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        delta = now - dt

        days = delta.days

        if days == 0:
            return "今日"
        elif days == 1:
            return "1日前"
        else:
            return f"{days}日前"

    except Exception as e:
        return f"不明 ({str(e)[:20]})"


def _extract_test_scores(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    What: セッションから7種目のスコアを抽出
    Why: テーブル・レーダーチャート表示に必要
    Design Decision: test_type順序は TEST_TYPES に従う

    Args:
        session: セッションデータ

    Returns:
        List[Dict]: 7種目のスコアリスト
        [
            {
                'test_type': 'single_leg_squat',
                'test_name': '片脚スタンススクワット',
                'score': 72.5,
                'max_score': 80,
                'percentage': 90.6
            },
            ...
        ]

    CRITICAL:
      - 欠測値（7種目未満）は score=0, percentage=0 で埋める
      - TEST_TYPES の順序で整列
    """
    tests = session.get('tests', [])

    # test_type → スコアのマッピング
    test_score_map = {}
    for test in tests:
        test_type = test.get('test_type', 'unknown')
        score = test.get('score', 0)
        test_score_map[test_type] = score

    # 7種目分のスコアを生成
    result = []
    for test_type in TEST_TYPES:
        score = test_score_map.get(test_type, 0)
        max_score = 80
        percentage = (score / max_score * 100) if max_score > 0 else 0

        result.append({
            'test_type': test_type,
            'test_name': TEST_TYPE_DISPLAY.get(test_type, test_type),
            'score': score,
            'max_score': max_score,
            'percentage': percentage
        })

    return result


def _render_test_scores_table(test_scores: List[Dict[str, Any]]):
    """
    What: 7種目スコアテーブルを描画
    Why: 各種目の達成率を一覧表示
    Design Decision: Streamlit dataframe、ソート可能

    Args:
        test_scores: _extract_test_scores() の出力

    CRITICAL:
      - 2.0点未満の項目に⚠️マーク
      - ソート可能（達成率順、種目順）
    """
    # テーブルデータ作成
    table_data = []
    for item in test_scores:
        test_name = item['test_name']
        score = item['score']
        max_score = item['max_score']
        percentage = item['percentage']

        # 2.0点未満の場合は⚠️マーク
        warning = "⚠️" if score < 2.0 else ""

        table_data.append({
            '種目名': f"{warning} {test_name}",
            '実得点/満点': f"{score:.1f}/{max_score}",
            '達成率（%）': f"{percentage:.1f}"
        })

    # Streamlit dataframe表示
    st.dataframe(table_data, use_container_width=True)


def _render_radar_chart(test_scores: List[Dict[str, Any]]):
    """
    What: レーダーチャート（7軸）を描画
    Why: 7種目の達成率を視覚的に可視化
    Design Decision: Plotly使用、達成率0-100%表示

    Args:
        test_scores: _extract_test_scores() の出力

    CRITICAL:
      - 7軸レーダーチャート
      - 軸ラベル: TEST_SHORT_MAP の短縮名
      - ツールチップ: 種目名+達成率+実得点
    """
    # レーダーチャートデータ作成
    labels = []
    values = []

    for item in test_scores:
        test_type = item['test_type']
        short_name = TEST_SHORT_MAP.get(test_type, test_type)
        percentage = item['percentage']

        labels.append(short_name)
        values.append(percentage)

    # Plotlyレーダーチャート
    fig = go.Figure(data=go.Scatterpolar(
        r=values,
        theta=labels,
        fill='toself',
        fillcolor='rgba(0, 123, 255, 0.3)',
        line=dict(color='rgb(0, 123, 255)', width=2),
        hovertemplate='<b>%{theta}</b><br>達成率: %{r:.1f}%<extra></extra>'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                ticksuffix='%'
            )
        ),
        showlegend=False,
        title="7種目達成率（0-100%）",
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)
