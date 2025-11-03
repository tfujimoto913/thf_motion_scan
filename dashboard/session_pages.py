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
import json
from pathlib import Path

import streamlit as st
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import plotly.graph_objects as go
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from session_dao import get_latest_sessions, get_session_by_id, get_previous_sessions
from data_loader import load_results_items
from utils import record_error, emit_ui_metric, convert_decimals
from config import TEST_TYPES, TEST_TYPE_DISPLAY, TEST_SHORT_MAP
from i18n import t
from session_result_loader import (
    DEMO_FIXTURES,
    DEMO_FIXTURE_META,
    DEFAULT_FIXTURE,
    SessionResultLoadResult,
    load_session_result,
)
from validation_badge import render_validation_badge


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
        record_error("session_list_page", "missing resources")
        return
    except Exception as e:
        st.error(f"❌ データ取得エラー: {str(e)}")
        record_error("session_list_page", str(e))
        return

    # データチェック
    if not items:
        st.warning("評価結果がありません。動画をアップロードしてください。")
        return

    try:
        # CRITICAL: DynamoDB Decimal型をfloat型に変換（ADR-026）
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
        record_error("session_detail_page", "missing resources")
        return
    except Exception as e:
        st.error(f"❌ データ取得エラー: {str(e)}")
        record_error("session_detail_page", str(e))
        return

    # CRITICAL: DynamoDB Decimal型をfloat型に変換（ADR-026）
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

    default_fixture = (
        "invalid_bad_state" if session.get('has_version_mismatch') else DEFAULT_FIXTURE
    )
    fixture_name = None
    if demo_mode:
        fixture_name = _select_demo_session_result_fixture(default_fixture)
        if not fixture_name:
            fixture_name = default_fixture

    st.markdown("---")

    # 総合スコア表示
    grand_total = session.get('grand_total', 0)
    grand_max = session.get('grand_max', 560)
    percentage = session.get('percentage', 0)
    rules_version = session.get('rules_version', 'unknown')
    processed_at = session.get('processed_at', '')
    freshness = _calculate_data_freshness(processed_at) if processed_at else "不明"
    tests_count = len(session.get('tests', []))
    total_tests = len(TEST_TYPES)
    is_complete = session.get('is_complete', tests_count >= total_tests)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("総合スコア", f"{grand_total:.1f}/{grand_max}")

    with col2:
        st.metric("達成率", f"{percentage:.1f}%")

    with col3:
        st.metric("データ鮮度", freshness)

    with col4:
        if is_complete:
            st.metric("完了状況", "✅ 完了")
        else:
            st.metric("完了状況", f"📝 {tests_count}/{total_tests}種目")

    session_result_payload = load_session_result(
        athlete_id=athlete_id,
        session_id=session_id,
        resources=resources,
        demo_mode=demo_mode,
        fixture_name=fixture_name if demo_mode else None,
    )
    _store_session_result_state(athlete_id, session_id, session_result_payload)
    pdf_column = _render_session_result_summary(session_result_payload)
    if pdf_column and session_result_payload.available:
        _render_pdf_generation(pdf_column, session, session_result_payload.data or {})

    # ========== Validation State バッジ表示 ==========
    st.markdown("---")
    st.subheader("✅ Validation State")

    if session_result_payload.available and session_result_payload.data:
        validation = session_result_payload.data.get("validation")
        versions = session_result_payload.data.get("versions")
        render_validation_badge(validation, versions, show_legend=True)
    else:
        st.caption("ℹ️ session_result.json が利用できないため、Validation情報は表示できません。")
        if session_result_payload.error:
            st.caption(f"エラー: {session_result_payload.error}")

    st.markdown("---")

    # ========== Versions情報表示 ==========
    version_summary = _extract_session_versions(session)
    session_versions = (session_result_payload.data or {}).get('versions') or {}

    rules_display = session_versions.get('rules_version') or rules_version or "-"
    thresholds_display = session_versions.get('thresholds_version') or "-"
    artifact_sha = session_versions.get('artifact_sha') or version_summary.get('artifact_sha')

    vcol1, vcol2, vcol3 = st.columns(3)
    vcol1.metric("rules_version", rules_display)
    vcol2.metric("thresholds_version", thresholds_display)
    artifact_display = "-"
    if artifact_sha:
        artifact_display = artifact_sha if len(artifact_sha) <= 12 else f"{artifact_sha[:12]}…"
    vcol3.metric("artifact_sha", artifact_display)
    if artifact_sha and len(artifact_sha) > 12:
        vcol3.caption(artifact_sha)

    if not session_versions.get('normalization_version'):
        st.caption(f"ℹ️ {t('normalization_future')}")

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

    st.markdown("---")

    # ========== セッション比較（Stage 4） ==========
    st.subheader("📊 セッション比較")

    # 過去セッション一覧取得
    previous_sessions = get_previous_sessions(items_filtered, athlete_id, session_id, limit=12)

    if not previous_sessions:
        st.info("比較可能な過去セッションがありません。次回撮影後に比較できるようになります。")
    else:
        # セッションB選択用のドロップダウン
        session_options = {}
        for prev_session in previous_sessions:
            prev_id = prev_session['session_id']
            prev_total = prev_session['grand_total']
            prev_pct = prev_session['percentage']
            prev_processed = prev_session.get('processed_at', '')
            freshness_label = _calculate_data_freshness(prev_processed) if prev_processed else "不明"

            # ドロップダウン表示用ラベル
            label = f"{prev_id} | {prev_total:.1f}/560点 ({prev_pct:.1f}%) | {freshness_label}"
            session_options[label] = prev_session

        # セッションB選択（初期値: 直近セッション）
        if session_options:
            selected_label = st.selectbox(
                "比較対象セッションを選択",
                list(session_options.keys()),
                index=0,  # 直近セッションを初期選択
                help="同一選手の過去セッションから比較対象を選択できます"
            )

            session_b = session_options[selected_label]

            # rules_version整合性チェック
            rules_a = session.get('rules_version', 'unknown')
            rules_b = session_b.get('rules_version', 'unknown')

            if rules_a != rules_b:
                # 比較不可バッジ表示
                st.markdown(
                    """
                    <div style="
                        background-color: #dc3545;
                        color: white;
                        padding: 15px;
                        border-radius: 5px;
                        font-weight: bold;
                        text-align: center;
                        margin: 10px 0;">
                        ⚠️ 比較不可：異なるルールバージョン
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                st.info(f"セッションA（現在）: {rules_a}")
                st.info(f"セッションB（比較対象）: {rules_b}")
                st.caption("異なるルールバージョン間での比較は正確性を保証できないため、表示を無効化しています。")
            else:
                # 比較可能 - レーダーチャート重ね合わせと差分表示
                st.success(f"✅ 比較可能：同一ルールバージョン（{rules_a}）")

                # セッションBのスコアを抽出
                test_scores_b = _extract_test_scores(session_b)

                compare_key = (session_id, session_b.get('session_id'))
                last_compare_key = st.session_state.get('_last_compare_metric')
                if compare_key != last_compare_key:
                    emit_ui_metric(
                        "compare_run",
                        environment=st.session_state.get('selected_env'),
                        session_id=session_id,
                    )
                    st.session_state['_last_compare_metric'] = compare_key

                # レーダーチャート重ね合わせ
                st.markdown("### レーダーチャート重ね合わせ")
                _render_comparison_radar_chart(test_scores, test_scores_b)

                # 差分表示
                st.markdown("### スコア差分")
                _render_score_diff(session, session_b, test_scores, test_scores_b)


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

    except Exception:
        return "不明"


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

    # test_type → スコア情報のマッピング
    test_score_map: Dict[str, Dict[str, Any]] = {}
    for test in tests:
        test_type = test.get('test_type')
        if not isinstance(test_type, str):
            continue

        raw_score = test.get('score')
        if isinstance(raw_score, Decimal):
            score_value = float(raw_score)
        elif isinstance(raw_score, (int, float)):
            score_value = float(raw_score)
        else:
            score_value = None

        test_score_map[test_type] = {
            'score': score_value,
        }

    # 7種目分のスコアを生成
    result: List[Dict[str, Any]] = []
    max_score = 80
    for test_type in TEST_TYPES:
        entry = test_score_map.get(test_type)
        score_value = entry.get('score') if entry else None
        is_missing = score_value is None
        safe_score = float(score_value) if score_value is not None else 0.0
        percentage = (safe_score / max_score * 100) if max_score > 0 else 0

        result.append({
            'test_type': test_type,
            'test_name': TEST_TYPE_DISPLAY.get(test_type, test_type),
            'short_name': TEST_SHORT_MAP.get(test_type, test_type),
            'score': safe_score,
            'max_score': max_score,
            'percentage': percentage,
            'is_missing': is_missing,
        })

    return result


def _select_demo_session_result_fixture(default_fixture: Optional[str]) -> Optional[str]:
    """Render selectbox to choose demo session_result fixture."""
    if not DEMO_FIXTURES:
        return default_fixture

    options = sorted(
        DEMO_FIXTURES.keys(),
        key=lambda name: (0 if DEMO_FIXTURE_META.get(name) == "valid" else 1, name),
    )
    default_index = options.index(default_fixture) if default_fixture in options else 0

    def _format_option(key: str) -> str:
        category = DEMO_FIXTURE_META.get(key, "valid")
        category_label = t('fixture_category_valid') if category == 'valid' else t('fixture_category_invalid')
        friendly = key.replace('_', ' ')
        return f"{category_label}: {friendly}"

    return st.selectbox(
        "Session result fixture (demo)",
        options,
        index=default_index,
        format_func=_format_option,
        key="session_result_fixture",
        help="デモ専用: session_result.json のシナリオを切り替えます"
    )


def _store_session_result_state(
    athlete_id: str,
    session_id: str,
    payload: SessionResultLoadResult,
) -> None:
    """Persist current session_result payload in session_state for downstream actions."""
    st.session_state['session_result_context'] = {
        'athlete_id': athlete_id,
        'session_id': session_id,
        'data': payload.data,
        'versions': (payload.data or {}).get('versions', {}),
        'source': payload.source,
        'error': payload.error,
    }


def _render_session_result_summary(
    payload: SessionResultLoadResult,
) -> Optional[Any]:
    """
    Render QC pass count and validation state summary.

    Returns:
        Optional column container reserved for PDF actions.
    """
    container = st.container()

    with container:
        if not payload.available:
            if payload.error == "not_found":
                st.info("session_result.json がまだ生成されていません。処理が完了すると表示されます。")
            elif payload.error == "missing_resources":
                st.warning("session_result の取得には results バケットへのアクセスが必要です。")
            elif payload.error:
                st.error(f"session_result の読み込みに失敗しました: {payload.error}")
            else:
                st.info("session_result 情報は現在利用できません。")
            return None

        data = payload.data or {}
        qc_pass = data.get('qc_pass_count')
        total_reps = data.get('total_reps')
        validation = data.get('validation') or {}
        validation_state = validation.get('state')
        violations = validation.get('violations') or []

        col_valid, col_validation, col_pdf = st.columns([1.1, 1.0, 1.2])

        with col_valid:
            if isinstance(qc_pass, int) and isinstance(total_reps, int):
                st.metric(t('valid_reps'), f"{qc_pass}/{total_reps}", help=t('valid_reps_hint'))
            else:
                st.metric(t('valid_reps'), "N/A", help=t('valid_reps_hint'))

        with col_validation:
            st.markdown(f"**{t('validation_state')}**")
            _render_validation_badge(validation_state, violations)

        versions = data.get('versions') or {}
        if versions:
            rules_v = versions.get('rules_version', '-')
            thresholds_v = versions.get('thresholds_version', '-')
            artifact_sha = versions.get('artifact_sha', '-')
            st.caption(
                f"{t('pdf_versions_caption')}: "
                f"rules {rules_v} / thresholds {thresholds_v} / artifact {artifact_sha}"
            )

        if payload.source and payload.source.startswith(("fixture", "local")):
            st.caption(f"session_result source: {payload.source}")

    return col_pdf


def _render_validation_badge(state: Optional[str], violations: List[Dict[str, Any]]) -> None:
    """Display validation state with color-coded badge and optional violation details."""
    normalized = (state or "UNKNOWN").upper()
    config = {
        "OK": ("#218838", "✅", t('status_ok')),
        "WARN": ("#FFC107", "⚠️", t('status_warn')),
        "ERROR": ("#DC3545", "⛔️", t('status_error')),
    }
    color, icon, label = config.get(normalized, ("#6C757D", "ℹ️", normalized))

    st.markdown(
        f"""
        <div style="
            display: inline-flex;
            align-items: center;
            padding: 0.35rem 0.85rem;
            border-radius: 999px;
            background-color: {color};
            color: white;
            font-weight: 600;
            font-size: 0.95rem;
        ">
            <span style="margin-right: 0.4rem;">{icon}</span>{label}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if normalized != "OK":
        summaries = [
            summary for summary in (_format_violation_summary(v) for v in violations)
            if summary
        ]
        if summaries:
            st.caption(summaries[0])
            if len(summaries) > 1:
                with st.expander(t('compat_details')):
                    for summary in summaries[1:]:
                        st.markdown(f"- {summary}")


def _format_violation_summary(violation: Dict[str, Any]) -> Optional[str]:
    """Format validation violation dict into a concise summary string."""
    if not isinstance(violation, dict):
        return None

    parts: List[str] = []
    for key in ("severity", "category", "field", "status"):
        value = violation.get(key)
        if isinstance(value, str) and value:
            parts.append(value)

    message = violation.get("message") or violation.get("reason")
    if isinstance(message, str) and message:
        parts.append(message)
    else:
        expected = violation.get("expected")
        current = violation.get("current")
        if expected and current:
            parts.append(f"{current} → {expected}")

    details = violation.get("details")
    if isinstance(details, str) and details:
        parts.append(details)

    return " / ".join(parts) if parts else None


def _render_pdf_generation(
    column: Any,
    session: Dict[str, Any],
    session_result: Dict[str, Any],
) -> None:
    """Render manual PDF generation controls."""
    context_key = f"{session.get('athlete_id', 'unknown')}::{session.get('session_id', 'unknown')}"
    confirm_key = f"pdf_confirm::{context_key}"
    result_key = f"pdf_result::{context_key}"

    with column:
        st.markdown(f"**{t('pdf_generate')}**")

        result_state = st.session_state.get(result_key)
        if result_state:
            pdf_path = Path(result_state['path'])
            pdf_bytes = result_state.get('bytes')
            if pdf_bytes is None and pdf_path.exists():
                pdf_bytes = pdf_path.read_bytes()
                result_state['bytes'] = pdf_bytes

            st.success(t('pdf_generated'))
            if pdf_bytes:
                st.download_button(
                    t('pdf_download'),
                    data=pdf_bytes,
                    file_name=pdf_path.name,
                    mime="application/pdf",
                    key=f"pdf_download::{context_key}",
                    use_container_width=True,
                )

            versions_meta = result_state.get('versions') or session_result.get('versions') or {}
            if versions_meta:
                st.caption(
                    f"{t('pdf_versions_caption')}: "
                    f"rules {versions_meta.get('rules_version', '-')}, "
                    f"thresholds {versions_meta.get('thresholds_version', '-')}, "
                    f"artifact {versions_meta.get('artifact_sha', '-')}"
                )
            return

        if st.session_state.get(confirm_key):
            st.warning(t('pdf_confirm_message'))
            confirm_col, cancel_col = st.columns(2)

            with confirm_col:
                if st.button(t('pdf_confirm_yes'), key=f"pdf_yes::{context_key}", use_container_width=True):
                    try:
                        pdf_path, pdf_bytes = _generate_session_pdf(session, session_result)
                        st.session_state[result_key] = {
                            'path': str(pdf_path),
                            'bytes': pdf_bytes,
                            'versions': session_result.get('versions', {}),
                            'generated_at': datetime.now(timezone.utc).isoformat(),
                        }
                        st.session_state.pop(confirm_key, None)
                        emit_ui_metric(
                            "pdf_generated",
                            environment=st.session_state.get('selected_env'),
                            session_id=session.get('session_id'),
                        )
                        st.experimental_rerun()
                    except Exception as exc:
                        st.session_state.pop(confirm_key, None)
                        record_error("pdf_generation", str(exc))
                        st.error(f"{t('pdf_generation_failed')}: {exc}")

            with cancel_col:
                if st.button(t('pdf_confirm_no'), key=f"pdf_no::{context_key}", use_container_width=True):
                    st.session_state.pop(confirm_key, None)
        else:
            if st.button(t('pdf_generate'), key=f"pdf_trigger::{context_key}", type="primary", use_container_width=True):
                st.session_state[confirm_key] = True


def _generate_session_pdf(
    session: Dict[str, Any],
    session_result: Dict[str, Any],
) -> tuple[Path, bytes]:
    """Generate a lightweight PDF summary for the current session."""
    output_dir = Path("outputs") / "dashboard" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    athlete_slug = _slugify_for_filename(session.get('athlete_id', 'athlete'))
    session_slug = _slugify_for_filename(session.get('session_id', 'session'))
    pdf_path = output_dir / f"{athlete_slug}_{session_slug}_{timestamp}.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    page_width, page_height = A4
    margin = 48
    cursor_y = page_height - margin

    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, cursor_y, "THF Motion Scan Session Report")
    cursor_y -= 32

    c.setFont("Helvetica", 11)
    c.drawString(margin, cursor_y, f"Athlete: {session.get('athlete_id', '-')}")
    cursor_y -= 16
    c.drawString(margin, cursor_y, f"Session: {session.get('session_id', '-')}")
    cursor_y -= 16

    processed_at = session.get('processed_at') or session_result.get('processed_at') or "-"
    c.drawString(margin, cursor_y, f"Processed at: {processed_at}")
    cursor_y -= 16

    qc_pass = session_result.get('qc_pass_count', 'N/A')
    total_reps = session_result.get('total_reps', 'N/A')
    c.drawString(margin, cursor_y, f"QC pass count: {qc_pass}/{total_reps}")
    cursor_y -= 16

    validation_state = session_result.get('validation', {}).get('state', 'UNKNOWN')
    c.drawString(margin, cursor_y, f"Validation state: {validation_state}")
    cursor_y -= 24

    aggregates = session_result.get('aggregates') or {}
    if aggregates:
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, cursor_y, "Aggregates")
        cursor_y -= 18
        c.setFont("Helvetica", 10)
        aggregates_text = json.dumps(aggregates, ensure_ascii=False, indent=2)
        cursor_y = _draw_multiline_text(c, aggregates_text, margin, cursor_y, page_height, margin)
        cursor_y -= 18

    versions = session_result.get('versions') or {}
    if versions:
        if cursor_y < margin + 72:
            c.showPage()
            cursor_y = page_height - margin
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, cursor_y, "Versions")
        cursor_y -= 18
        c.setFont("Helvetica", 10)
        for key in ("rules_version", "thresholds_version", "artifact_sha"):
            value = versions.get(key, '-')
            c.drawString(margin, cursor_y, f"{key}: {value}")
            cursor_y -= 14
            if cursor_y < margin:
                c.showPage()
                cursor_y = page_height - margin
                c.setFont("Helvetica", 10)

    c.save()
    pdf_bytes = pdf_path.read_bytes()
    return pdf_path, pdf_bytes


def _draw_multiline_text(
    canvas_obj: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    page_height: float,
    margin: float,
    font: str = "Helvetica",
    size: int = 10,
) -> float:
    """Render multi-line text with automatic page breaks."""
    text_obj = canvas_obj.beginText(x, y)
    text_obj.setFont(font, size)

    for line in text.splitlines():
        if text_obj.getY() < margin:
            canvas_obj.drawText(text_obj)
            canvas_obj.showPage()
            text_obj = canvas_obj.beginText(x, page_height - margin)
            text_obj.setFont(font, size)
        text_obj.textLine(line)

    canvas_obj.drawText(text_obj)
    return text_obj.getY()


def _slugify_for_filename(value: Any) -> str:
    """Convert arbitrary text into a filesystem-safe slug."""
    text = str(value or "value")
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in text)
    safe = safe.strip("-") or "value"
    return safe[:64]


def _extract_session_versions(session: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    What: セッションレベルのバージョン情報を抽出
    Why: ヘッダー表示用に normalization_version / artifact_sha を取得
    """

    normalization_values: List[str] = []
    artifact_values: List[str] = []

    def collect(source: Any) -> None:
        if not isinstance(source, dict):
            return
        normalization = source.get('normalization_version')
        if isinstance(normalization, str) and normalization:
            normalization_values.append(normalization)
        artifact = source.get('artifact_sha') or source.get('artifactSha')
        if isinstance(artifact, str) and artifact:
            artifact_values.append(artifact)

    collect(session)
    collect(session.get('metadata'))

    for test in session.get('tests', []):
        collect(test)
        collect(test.get('metadata'))
        evaluation = test.get('evaluation')
        collect(evaluation)
        if isinstance(evaluation, dict):
            collect(evaluation.get('metadata'))

    def pick(values: List[str]) -> Optional[str]:
        unique = list(dict.fromkeys(values))
        if not unique:
            return None
        return unique[0] if len(unique) == 1 else "mixed"

    return {
        'normalization_version': pick(normalization_values),
        'artifact_sha': pick(artifact_values),
    }


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
        is_missing = item.get('is_missing', False)

        if is_missing:
            score_display = "N/A"
            percentage_display = "N/A"
            warning = "⚠️"
        else:
            score_display = f"{score:.1f}/{max_score}"
            percentage_display = f"{percentage:.1f}"
            warning = "⚠️" if score < 2.0 else ""

        table_data.append({
            '種目名': f"{warning} {test_name}".strip(),
            '実得点/満点': score_display,
            '達成率（%）': percentage_display
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
    labels: List[str] = []
    values: List[float] = []
    hover_text: List[str] = []
    missing_labels: List[str] = []
    missing_hover: List[str] = []

    for item in test_scores:
        test_type = item['test_type']
        short_name = item.get('short_name') or TEST_SHORT_MAP.get(test_type, test_type)
        display_name = item['test_name']
        labels.append(short_name)

        if item.get('is_missing'):
            values.append(0)
            hover_text.append(f"{display_name}: N/A")
            missing_labels.append(short_name)
            missing_hover.append(f"{display_name}: N/A")
        else:
            percentage = item['percentage']
            score = item['score']
            max_score = item['max_score']
            values.append(percentage)
            hover_text.append(
                f"{display_name}: {percentage:.1f}% ({score:.1f}/{max_score})"
            )

    fig = go.Figure()
    fig.add_trace(
        go.Scatterpolar(
            r=values,
            theta=labels,
            fill='toself',
            fillcolor='rgba(0, 123, 255, 0.3)',
            line=dict(color='rgb(0, 123, 255)', width=2),
            customdata=hover_text,
            hovertemplate='%{customdata}<extra></extra>',
            name='達成率',
        )
    )

    if missing_labels:
        fig.add_trace(
            go.Scatterpolar(
                r=[5] * len(missing_labels),
                theta=missing_labels,
                mode='lines+markers+text',
                line=dict(color='rgba(108,117,125,0.7)', dash='dot'),
                marker=dict(color='rgba(108,117,125,0.9)', size=8, symbol='circle-open'),
                text=['N/A'] * len(missing_labels),
                textposition='top center',
                hovertext=missing_hover,
                hoverinfo='text',
                name='欠測',
                showlegend=False,
            )
        )

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


def _render_comparison_radar_chart(
    test_scores_a: List[Dict[str, Any]],
    test_scores_b: List[Dict[str, Any]]
):
    """
    What: 2セッション重ね合わせレーダーチャートを描画
    Why: セッション比較機能（Stage 4）で進捗を可視化
    Design Decision: Plotly使用、セッションA（青）とセッションB（オレンジ）を重ね表示

    Args:
        test_scores_a: セッションA（現在）のスコア
        test_scores_b: セッションB（比較対象）のスコア

    CRITICAL:
      - セッションA: 青色（rgba 0,123,255）、透明度0.5
      - セッションB: オレンジ色（rgba 255,165,0）、透明度0.25
      - 欠測種目: グレー点線 + "N/A" ラベル
      - ツールチップ: 種目名 + 達成率 + 実得点（欠測はN/A）
    """
    labels: List[str] = []
    values_a: List[float] = []
    values_b: List[float] = []
    hover_text_a: List[str] = []
    hover_text_b: List[str] = []
    missing_a_labels: List[str] = []
    missing_b_labels: List[str] = []
    missing_a_hover: List[str] = []
    missing_b_hover: List[str] = []

    for item_a, item_b in zip(test_scores_a, test_scores_b):
        test_type = item_a['test_type']
        short_name = item_a.get('short_name') or TEST_SHORT_MAP.get(test_type, test_type)
        display_name = TEST_TYPE_DISPLAY.get(test_type, test_type)

        labels.append(short_name)

        if item_a.get('is_missing'):
            values_a.append(0)
            hover_text_a.append(f"{display_name}: N/A")
            missing_a_labels.append(short_name)
            missing_a_hover.append(f"{display_name}: N/A")
        else:
            percentage_a = item_a['percentage']
            score_a = item_a['score']
            values_a.append(percentage_a)
            hover_text_a.append(
                f"{display_name}: {percentage_a:.1f}% ({score_a:.1f}/{item_a['max_score']})"
            )

        if item_b.get('is_missing'):
            values_b.append(0)
            hover_text_b.append(f"{display_name}: N/A")
            missing_b_labels.append(short_name)
            missing_b_hover.append(f"{display_name}: N/A")
        else:
            percentage_b = item_b['percentage']
            score_b = item_b['score']
            values_b.append(percentage_b)
            hover_text_b.append(
                f"{display_name}: {percentage_b:.1f}% ({score_b:.1f}/{item_b['max_score']})"
            )

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=values_a,
            theta=labels,
            fill='toself',
            fillcolor='rgba(0, 123, 255, 0.5)',
            line=dict(color='rgb(0, 123, 255)', width=2),
            name='セッションA（現在）',
            customdata=hover_text_a,
            hovertemplate='%{customdata}<extra></extra>',
        )
    )

    fig.add_trace(
        go.Scatterpolar(
            r=values_b,
            theta=labels,
            fill='toself',
            fillcolor='rgba(255, 165, 0, 0.25)',
            line=dict(color='rgb(255, 165, 0)', width=2),
            name='セッションB（比較対象）',
            customdata=hover_text_b,
            hovertemplate='%{customdata}<extra></extra>',
        )
    )

    if missing_a_labels:
        fig.add_trace(
            go.Scatterpolar(
                r=[5] * len(missing_a_labels),
                theta=missing_a_labels,
                mode='lines+markers+text',
                line=dict(color='rgba(0, 123, 255, 0.6)', dash='dot'),
                marker=dict(color='rgba(0, 123, 255, 0.8)', size=8, symbol='triangle-up'),
                text=['N/A'] * len(missing_a_labels),
                textposition='top center',
                hovertext=missing_a_hover,
                hoverinfo='text',
                showlegend=False,
            )
        )

    if missing_b_labels:
        fig.add_trace(
            go.Scatterpolar(
                r=[5] * len(missing_b_labels),
                theta=missing_b_labels,
                mode='lines+markers+text',
                line=dict(color='rgba(255, 165, 0, 0.6)', dash='dot'),
                marker=dict(color='rgba(255, 165, 0, 0.8)', size=8, symbol='triangle-down'),
                text=['N/A'] * len(missing_b_labels),
                textposition='top center',
                hovertext=missing_b_hover,
                hoverinfo='text',
                showlegend=False,
            )
        )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                ticksuffix='%'
            )
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5
        ),
        title="2セッション重ね合わせ（0-100%）",
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_score_diff(
    session_a: Dict[str, Any],
    session_b: Dict[str, Any],
    test_scores_a: List[Dict[str, Any]],
    test_scores_b: List[Dict[str, Any]]
):
    """
    What: 2セッション間のスコア差分を表示
    Why: セッション比較機能（Stage 4）で進捗を定量評価
    Design Decision: 総合スコア差のバッジ + 種目別差分テーブル（色分け）

    Args:
        session_a: セッションA（現在）のデータ
        session_b: セッションB（比較対象）のデータ
        test_scores_a: セッションAのスコア
        test_scores_b: セッションBのスコア

    CRITICAL:
      - 差分プラス: 緑色表示
      - 差分マイナス: 赤色表示
      - 差分±0: 灰色表示
    """
    # 総合スコア差
    grand_total_a = session_a.get('grand_total', 0)
    grand_total_b = session_b.get('grand_total', 0)
    grand_diff = grand_total_a - grand_total_b

    percentage_a = session_a.get('percentage', 0)
    percentage_b = session_b.get('percentage', 0)
    percentage_diff = percentage_a - percentage_b

    # 総合スコア差のバッジ
    if grand_diff > 0:
        badge_color = "#28a745"  # 緑
        badge_icon = "📈"
        badge_text = f"{badge_icon} 総合スコア: +{grand_diff:.1f}点 (+{percentage_diff:.1f}%)"
    elif grand_diff < 0:
        badge_color = "#dc3545"  # 赤
        badge_icon = "📉"
        badge_text = f"{badge_icon} 総合スコア: {grand_diff:.1f}点 ({percentage_diff:.1f}%)"
    else:
        badge_color = "#6c757d"  # 灰色
        badge_icon = "➖"
        badge_text = f"{badge_icon} 総合スコア: ±0点 (変化なし)"

    st.markdown(
        f"""
        <div style="
            background-color: {badge_color};
            color: white;
            padding: 20px;
            border-radius: 10px;
            font-size: 24px;
            font-weight: bold;
            text-align: center;
            margin: 20px 0;">
            {badge_text}
        </div>
        """,
        unsafe_allow_html=True
    )

    # 種目別差分テーブル
    st.markdown("#### 種目別差分")

    table_data = []
    for item_a, item_b in zip(test_scores_a, test_scores_b):
        test_name = item_a['test_name']
        score_a = item_a['score']
        score_b = item_b['score']
        pct_a = item_a['percentage']
        pct_b = item_b['percentage']
        missing_a = item_a.get('is_missing', False)
        missing_b = item_b.get('is_missing', False)

        if missing_a:
            session_a_display = "N/A"
        else:
            session_a_display = f"{score_a:.1f}点 ({pct_a:.1f}%)"

        if missing_b:
            session_b_display = "N/A"
        else:
            session_b_display = f"{score_b:.1f}点 ({pct_b:.1f}%)"

        if missing_a or missing_b:
            diff_display = "⚪ N/A"
            score_diff_display = "N/A"
        else:
            score_diff = score_a - score_b
            pct_diff = pct_a - pct_b
            if pct_diff > 0:
                diff_display = f"🟢 +{pct_diff:.1f}%"
            elif pct_diff < 0:
                diff_display = f"🔴 {pct_diff:.1f}%"
            else:
                diff_display = "⚪ ±0%"
            score_diff_display = f"{score_diff:+.1f}点"

        table_data.append({
            '種目名': test_name,
            'セッションA': session_a_display,
            'セッションB': session_b_display,
            '差分': diff_display,
            '実得点差': score_diff_display
        })

    # Streamlit dataframe表示
    st.dataframe(table_data, use_container_width=True)
