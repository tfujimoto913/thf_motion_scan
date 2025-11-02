"""
Purpose: THF Motion Scan ダッシュボード（Streamlit）
Responsibility:
  - 動画アップロード（S3）
  - 評価結果一覧（DynamoDB）
  - 詳細結果表示（JSON + グラフ）
Dependencies: streamlit, boto3, plotly, pandas
Created: 2025-10-26 by Claude
Decision Log: ADR-014（Phase 5: Dashboard実装）

CRITICAL: AWS認証情報は環境変数または~/.aws/credentialsから取得
"""
import logging
import time
import streamlit as st
import boto3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re
import uuid

# dashboard/config.py, demo_data.py をインポート
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DEFAULT_ENV,
    PERFORMANCE_LIMITS,
    TEST_TYPES,
    TEST_TYPE_DISPLAY,
    get_available_environments,
    get_resource_names,
)
from demo_data import get_demo_results
from data_loader import cached_scan_results, load_results_items
from utils import (  # type: ignore[import-untyped]
    VideoValidator,
    configure_structured_logging,
    execution_timer,
    record_error,
    log_dashboard_event,
    emit_ui_metric,
    convert_decimals,
)
from session_dao import group_tests_by_session, get_latest_sessions
from session_pages import session_list_page, session_detail_page


# 種目別評価原則マッピング（各種目で評価される原則番号）
TEST_PRINCIPLES_MAP = {
    "single_leg_squat": [1, 2, 4],      # P1, P2, P4
    "skater_lunge": [5, 3, 2],          # P5, P3, P2
    "stride_mimic": [3, 2, 4],          # P3, P2, P4
    "jump_landing": [2, 4, 1],          # P2, P4, P1
    "upper_body_swing": [7, 6, 4],      # P7, P6, P4
    "push_pull": [6, 7, 1],             # P6, P7, P1
    "cross_step": [7, 5, 3]             # P7, P5, P3
}

# 7原則名称（略称）
PRINCIPLE_NAMES = {
    1: "代償動作",
    2: "下肢安定",
    3: "3筋群連動",
    4: "骨盤水平",
    5: "骨盤シフト",
    6: "背面筋群",
    7: "上下分離"
}


def parse_semver(version_str: Optional[str]) -> Optional[Tuple[int, int, int]]:
    """
    What: vX.Y.Z 形式のバージョン文字列を解析
    Why: メジャーバージョン単位で互換性を判断するため
    """
    if not version_str or not isinstance(version_str, str):
        return None

    match = re.match(r'^v?(\d+)\.(\d+)\.(\d+)$', version_str.strip())
    if not match:
        return None

    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def check_rules_version_compatibility(current: Optional[str], target: Optional[str]) -> Dict[str, Any]:
    """
    What: rules_version 間の互換性判定
    Why: 比較やレーダーチャート表示の抑止に利用
    """
    if not current or not target:
        return {
            'status': 'unknown',
            'reason': 'バージョン情報が不足しています',
            'current': current,
            'target': target,
        }

    current_semver = parse_semver(current)
    target_semver = parse_semver(target)

    if not current_semver or not target_semver:
        return {
            'status': 'unknown',
            'reason': 'サポート外のバージョン形式です',
            'current': current,
            'target': target,
        }

    if current_semver[0] == target_semver[0]:
        return {
            'status': 'compatible',
            'reason': '同じmajor versionです',
            'current': current,
            'target': target,
        }

    return {
        'status': 'incompatible',
        'reason': 'major versionが異なります',
        'current': current,
        'target': target,
    }


def evaluate_rules_compatibility(current_info: Dict[str, Any], target_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    What: extract_version_info の結果を受け取り互換性を評価
    Why: UI側での判定処理を簡潔にするため
    """
    return check_rules_version_compatibility(
        current_info.get('rules_version'),
        target_info.get('rules_version'),
    )


def extract_version_info(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    What: 評価レコードからバージョン情報を抽出
    Why: ルール/スコアリングのバージョン可視化
    Design Decision: top-level と metadata/evaluation 内を順番に参照
    """
    metadata = record.get('metadata') if isinstance(record.get('metadata'), dict) else {}
    evaluation = record.get('evaluation') if isinstance(record.get('evaluation'), dict) else {}

    rules_version = record.get('rules_version') if isinstance(record.get('rules_version'), str) else None
    if not rules_version and metadata:
        candidate = metadata.get('rules_version')
        rules_version = candidate if isinstance(candidate, str) else None

    explicit_scoring_version = record.get('scoring_version') if isinstance(record.get('scoring_version'), str) else None
    if not explicit_scoring_version and metadata:
        candidate = metadata.get('scoring_version')
        explicit_scoring_version = candidate if isinstance(candidate, str) else None

    candidate_eval_version = evaluation.get('version') if isinstance(evaluation, dict) else None
    evaluation_version = candidate_eval_version if isinstance(candidate_eval_version, str) else None

    scoring_version = explicit_scoring_version or evaluation_version
    mismatch = False

    if explicit_scoring_version and evaluation_version and explicit_scoring_version != evaluation_version:
        mismatch = True

    rules_semver = parse_semver(rules_version)
    scoring_semver = parse_semver(scoring_version)

    return {
        'rules_version': rules_version,
        'scoring_version': scoring_version,
        'evaluation_version': evaluation_version,
        'mismatch': mismatch,
        'rules_semver': rules_semver,
        'rules_major': rules_semver[0] if rules_semver else None,
        'scoring_semver': scoring_semver,
    }


def format_version_label(version_info: Dict[str, Any]) -> str:
    """
    What: バージョン表示用文字列を整形
    Why: 一覧・詳細で統一したフォーマットを使用
    """
    rules = version_info.get('rules_version') or '-'  # type: ignore[arg-type]
    scoring = version_info.get('scoring_version') or '-'  # type: ignore[arg-type]
    return f"rules: {rules} / scoring: {scoring}"


def compute_quality_status(health: Any) -> Dict[str, str]:
    """
    What: Health Check 情報から品質ステータスを決定
    Why: 一覧・詳細で同じ基準を適用する
    Design Decision: is_valid を最優先、次に検出率と警告を考慮
    """
    default = {
        'label': '⚠️ 情報なし',
        'status': 'warning',
        'reason': 'Health Check 情報が欠落しています',
        'detection_rate': None,
    }

    if not isinstance(health, dict):
        return default

    detection_rate = health.get('detection_rate')
    warnings = health.get('warnings') if isinstance(health.get('warnings'), list) else []
    is_valid = health.get('is_valid')

    if is_valid is False:
        return {
            'label': '❌ エラー',
            'status': 'error',
            'reason': 'データ品質: 問題あり',
            'detection_rate': detection_rate,
        }

    # 検出率が低い場合は警告（しきい値: 0.9）
    low_detection = isinstance(detection_rate, (int, float)) and detection_rate < 0.9

    if warnings or low_detection:
        return {
            'label': '⚠️ 警告',
            'status': 'warning',
            'reason': 'データ品質: 注意が必要',
            'detection_rate': detection_rate,
        }

    if is_valid is True:
        return {
            'label': '✅ 正常',
            'status': 'success',
            'reason': 'データ品質: 良好',
            'detection_rate': detection_rate,
        }

    # is_valid が None など曖昧な場合
    return {
        'label': '⚠️ 警告',
        'status': 'warning',
        'reason': 'データ品質: 判定不可 (手動確認推奨)',
        'detection_rate': detection_rate,
    }


def to_float(value: Any) -> Optional[float]:
    """
    What: 安全に数値へ変換
    Why: DynamoDBやJSON由来の値が文字列/Decimalの場合がある
    """
    if isinstance(value, bool) or value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def format_score_display(value: Any) -> str:
    """
    What: スコア表示用の文字列を生成
    Why: 欠損時に「データ未取得」を明示
    """
    number = to_float(value)
    return f"{number:.1f}" if number is not None else "データ未取得"


def format_timestamp_display(value: Any) -> str:
    """
    What: 日時表示を整形
    Why: 欠損データでもユーザーに状況を伝える
    """
    if isinstance(value, pd.Timestamp):
        return value.strftime('%Y-%m-%d %H:%M:%S')

    if isinstance(value, datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')

    if isinstance(value, str) and value.strip():
        return value

    return "データ未取得"


def summarize_scores(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    What: スコア情報の集計と欠損判定
    Why: 一覧・詳細表示で一貫したフォールバックを提供
    """
    evaluation = record.get('evaluation') if isinstance(record.get('evaluation'), dict) else {}
    base_score = to_float(record.get('score'))

    summary: Dict[str, Any] = {
        'total_score': None,
        'execution_score': None,
        'principles_score': None,
        'max_score': None,
        'available': False,
        'message': 'スコアがまだ利用できません（処理中の可能性があります）',
        'version': evaluation.get('version') if isinstance(evaluation, dict) else None,
    }

    if evaluation:
        version = evaluation.get('version')
        if version == 'v2.1':
            total = to_float(evaluation.get('total_score'))
            execution = to_float(evaluation.get('A_execution_score'))
            principles = to_float(evaluation.get('B_total'))

            summary.update({
                'total_score': total,
                'execution_score': execution,
                'principles_score': principles,
                'max_score': 80.0,
                'available': total is not None,
                'message': 'v2.1 スコアが計算中です' if total is None else '',
            })
        else:
            execution = to_float(evaluation.get('execution', {}).get('total') if isinstance(evaluation.get('execution'), dict) else None)
            principles = to_float(evaluation.get('principles', {}).get('total') if isinstance(evaluation.get('principles'), dict) else None)
            total = None
            available = execution is not None or principles is not None
            if available:
                total = (execution or 0.0) + (principles or 0.0)

            summary.update({
                'total_score': total,
                'execution_score': execution,
                'principles_score': principles,
                'max_score': 12.0,
                'available': available,
                'message': '' if available else '旧システムのスコア情報が不足しています',
            })

    elif base_score is not None:
        # デモデータ用フォールバック
        total = base_score * (80.0 / 3.0)
        execution = total * (20.0 / 80.0)
        principles = total - execution

        summary.update({
            'total_score': total,
            'execution_score': execution,
            'principles_score': principles,
            'max_score': 80.0,
            'available': True,
            'message': '',
        })

    return summary

def extract_principle_radar_scores(evaluation: Dict[str, Any]) -> Dict[int, float]:
    """
    What: v2.1評価のB_principlesから原則単位のスコアを抽出
    Why: レーダーチャートに利用し、欠損時は空を返す
    """
    if not isinstance(evaluation, dict):
        return {}

    b_principles = evaluation.get('B_principles')
    if not isinstance(b_principles, dict):
        return {}

    principle_scores: Dict[int, List[float]] = {}

    for phase in ('eccentric', 'concentric'):
        phase_scores = b_principles.get(phase, {})
        if not isinstance(phase_scores, dict):
            continue

        for key, value in phase_scores.items():
            if not isinstance(value, (int, float)):
                continue
            if not key.startswith('B'):
                continue

            principle_code = key.split('_')[0].replace('B', '')
            try:
                principle_id = int(principle_code)
            except ValueError:
                continue

            principle_scores.setdefault(principle_id, []).append(float(value))

    aggregated: Dict[int, float] = {}
    for pid, values in principle_scores.items():
        if values:
            aggregated[pid] = sum(values) / len(values)

    return aggregated


def perform_health_checks(s3_client, dynamodb, resources: Optional[Dict[str, Any]], demo_mode: bool = False) -> List[Dict[str, Any]]:
    """Run lightweight health checks for dependent services."""

    if demo_mode or not resources:
        return []

    results: List[Dict[str, Any]] = []

    try:
        start = time.perf_counter()
        dynamodb.meta.client.describe_table(TableName=resources['table_name'])
        duration_ms = (time.perf_counter() - start) * 1000
        results.append({
            'name': 'DynamoDB',
            'status': 'ok',
            'duration_ms': round(duration_ms, 2),
            'resource': resources['table_name'],
        })
    except Exception as exc:
        record_error("health_check_dynamodb", str(exc))
        results.append({
            'name': 'DynamoDB',
            'status': 'error',
            'message': str(exc),
            'resource': resources.get('table_name'),
        })

    bucket_name = resources.get('results_bucket')
    if bucket_name:
        try:
            start = time.perf_counter()
            s3_client.head_bucket(Bucket=bucket_name)
            duration_ms = (time.perf_counter() - start) * 1000
            results.append({
                'name': 'S3',
                'status': 'ok',
                'duration_ms': round(duration_ms, 2),
                'resource': bucket_name,
            })
        except Exception as exc:
            record_error("health_check_s3", str(exc))
            results.append({
                'name': 'S3',
                'status': 'error',
                'message': str(exc),
                'resource': bucket_name,
            })

    log_dashboard_event("health_check", checks=results)

    return results


def parse_client_id(video_id: str) -> Optional[Dict[str, str]]:
    """
    What: video_idからクライアントID情報を抽出
    Why: FirstLast-yymmdd形式のクライアントIDを表示用に変換
    Design Decision: 正規表現でクライアントIDパターンを検出（ADR-015予定）

    Args:
        video_id: S3パス形式のvideo_id (例: "bucket/videos/test_type/TaroYamada-100315.mp4")

    Returns:
        Dict with 'raw', 'first_name', 'last_name', 'birth_date' or None

    CRITICAL: FirstLast-yymmdd形式のみ対応（例: TaroYamada-100315）
    """
    # video_idからファイル名部分を抽出
    filename = video_id.split('/')[-1].replace('.mp4', '')

    # FirstLast-yymmdd パターンマッチ（例: TaroYamada-100315）
    pattern = r'^([A-Z][a-z]+)([A-Z][a-z]+)-(\d{6})$'
    match = re.match(pattern, filename)

    if match:
        first_name = match.group(1)
        last_name = match.group(2)
        birth_date_short = match.group(3)  # yymmdd

        # yymmdd を yyyy-mm-dd に変換
        yy = birth_date_short[:2]
        mm = birth_date_short[2:4]
        dd = birth_date_short[4:6]

        # 2000年代か1900年代か判定（00-30は2000年代、31-99は1900年代）
        yyyy = f"20{yy}" if int(yy) <= 30 else f"19{yy}"
        birth_date = f"{yyyy}-{mm}-{dd}"

        return {
            'raw': filename,
            'first_name': first_name,
            'last_name': last_name,
            'birth_date': birth_date
        }

    return None


def format_client_id_display(video_id: str) -> str:
    """
    What: クライアントIDを表示用にフォーマット
    Why: FirstLast-yymmdd → "Taro Yamada (2010-03-15生)" に変換
    Design Decision: ユーザーフレンドリーな日本語表示（ADR-015予定）

    Args:
        video_id: S3パス形式のvideo_id

    Returns:
        str: フォーマット済み表示文字列

    CRITICAL: パース失敗時は元のvideo_idを返す
    """
    parsed = parse_client_id(video_id)

    if parsed:
        return f"{parsed['first_name']} {parsed['last_name']} ({parsed['birth_date']}生)"

    # パース失敗時は元のvideo_idを返す
    return video_id

# AWS クライアント初期化
@st.cache_resource
def get_aws_clients(selected_env: str):
    """
    What: AWS クライアント初期化（S3, DynamoDB）
    Why: Streamlit再実行時の再初期化防止
    Design Decision: st.cache_resource でシングルトン化（ADR-014）

    CRITICAL: AWS認証情報は環境変数または~/.aws/credentialsから取得
    """
    s3_client = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')
    resources = get_resource_names(selected_env)
    return s3_client, dynamodb, resources


def upload_video_page(s3_client, resources, demo_mode=False):
    """
    What: 動画アップロードページ（ウィザード形式）
    Why: 7種目を順番にアップロードする流れを提供
    Design Decision: st.session_stateでウィザードフロー管理（Stage 4改善）

    Args:
        s3_client: S3クライアント
        resources: AWSリソース名
        demo_mode: デモモードフラグ

    ウィザードフロー:
    Step 1: ランディング（アップロード開始ボタン）
    Step 2: 選手情報入力（名前+生年月日→athlete_id生成）
    Step 3: セッション選択（新規/既存）
    Step 4-10: 種目①-⑦アップロード
    Step 11: 完了画面

    CRITICAL: session_stateでathlete_id, session_id, uploaded_testsを管理
    """
    # セッション状態の初期化
    if 'wizard_step' not in st.session_state:
        st.session_state.wizard_step = 1
    if 'athlete_name' not in st.session_state:
        st.session_state.athlete_name = None
    if 'birth_date' not in st.session_state:
        st.session_state.birth_date = None
    if 'athlete_id' not in st.session_state:
        st.session_state.athlete_id = None
    if 'session_id' not in st.session_state:
        st.session_state.session_id = None
    if 'uploaded_tests' not in st.session_state:
        st.session_state.uploaded_tests = []

    # ステップごとの画面表示
    if st.session_state.wizard_step == 1:
        render_landing_page(demo_mode)
    elif st.session_state.wizard_step == 2:
        render_athlete_info_page()
    elif st.session_state.wizard_step == 3:
        render_session_select_page(resources, demo_mode)
    elif 4 <= st.session_state.wizard_step <= 10:
        test_index = st.session_state.wizard_step - 4
        render_test_upload_page(s3_client, resources, test_index, demo_mode)
    elif st.session_state.wizard_step == 11:
        render_completion_page()


def render_landing_page(demo_mode):
    """Step 1: ランディングページ"""
    st.header("📤 動画アップロード")

    # デモモード時の表示
    if demo_mode:
        st.info("🎭 **デモモード**: 動画アップロードは無効です")
        st.success("✅ デモデータは「📊 評価結果一覧」ページで確認できます")
        return

    st.markdown("""
    ### 7種目アップロードウィザード

    このウィザードでは、以下の流れで7種目の動画をアップロードします：

    1. **選手情報入力** - 名前と生年月日を入力
    2. **セッション選択** - 新規セッションまたは既存セッション
    3. **種目アップロード** - 7種目を順番にアップロード

    途中で中断しても、既存セッションに追加することで続きからアップロードできます。
    """)

    st.markdown("---")

    if st.button("📋 アップロード開始", type="primary", use_container_width=True):
        st.session_state.wizard_step = 2
        st.rerun()


def render_athlete_info_page():
    """Step 2: 選手情報入力ページ"""
    st.header("📝 選手情報入力")

    st.markdown("### Step 1/3: 選手情報")

    col1, col2 = st.columns(2)

    with col1:
        athlete_name = st.text_input(
            "選手名（英語表記）",
            value=st.session_state.athlete_name or "",
            placeholder="例: Taro Yamada",
            help="名前と苗字をスペース区切りで入力（例: Taro Yamada）"
        )

    with col2:
        birth_date = st.date_input(
            "生年月日",
            value=st.session_state.birth_date,
            help="選手の生年月日を選択してください"
        )

    # athlete_id自動生成
    if athlete_name and birth_date:
        # "Taro Yamada" → "TaroYamada"
        name_camel = athlete_name.replace(" ", "").replace("-", "")
        # 生年月日 → "100315" (2010-03-15 → 100315)
        birth_str = birth_date.strftime('%y%m%d')
        athlete_id = f"{name_camel}-{birth_str}"

        st.info(f"📋 生成された選手ID: **{athlete_id}**")
        st.caption("この選手IDは自動生成されます。セッション比較機能で使用されます。")

        col_btn1, col_btn2 = st.columns(2)

        with col_btn1:
            if st.button("← 戻る", use_container_width=True):
                st.session_state.wizard_step = 1
                st.rerun()

        with col_btn2:
            if st.button("次へ →", type="primary", use_container_width=True):
                st.session_state.athlete_name = athlete_name
                st.session_state.birth_date = birth_date
                st.session_state.athlete_id = athlete_id
                st.session_state.wizard_step = 3
                st.rerun()
    else:
        st.warning("⚠️ 選手名と生年月日を入力してください")


def render_session_select_page(resources, demo_mode):
    """Step 3: セッション選択ページ"""
    st.header("📋 セッション選択")

    st.markdown("### Step 2/3: セッション選択")

    st.info(f"選手ID: **{st.session_state.athlete_id}**")

    session_mode = st.radio(
        "セッションを選択してください",
        ["新規セッションを開始", "既存セッションに追加"],
        help="7種目を同じセッションにまとめるには「既存セッションに追加」を選択してください"
    )

    session_id = None

    if session_mode == "新規セッションを開始":
        # 新規session_id自動生成
        new_session_id = datetime.now().strftime('%Y%m%d-%H%M')
        st.success(f"📋 新規セッションID: **{new_session_id}**")
        st.caption("このセッションIDで7種目をまとめて管理します")
        session_id = new_session_id

    else:  # 既存セッションに追加
        try:
            items = load_results_items(resources, demo_mode=False)
            from session_dao import get_latest_sessions
            items_converted = [convert_decimals(item) for item in items]
            items_filtered = [
                item for item in items_converted
                if not str(item.get('video_id', '')).startswith('METADATA')
            ]
            sessions = get_latest_sessions(items_filtered, limit=20)
            athlete_sessions = [s for s in sessions if s.get('athlete_id') == st.session_state.athlete_id]

            if athlete_sessions:
                session_options = {}
                for s in athlete_sessions:
                    sid = s['session_id']
                    test_count = len(s.get('tests', []))
                    is_complete = s.get('is_complete', False)

                    # 未完了セッションを視覚的に区別
                    if is_complete:
                        label = f"{sid} ({test_count}/7種目 完了✅)"
                    else:
                        label = f"{sid} ({test_count}/7種目 未完了⚠️)"

                    session_options[label] = sid

                selected_label = st.selectbox(
                    "既存セッションを選択",
                    list(session_options.keys()),
                    help="過去20セッションから選択できます。未完了⚠️セッションに追加して続きからアップロードできます。"
                )
                session_id = session_options[selected_label]

                # 選択したセッションの情報を表示
                selected_session = next((s for s in athlete_sessions if s['session_id'] == session_id), None)
                if selected_session:
                    selected_test_count = len(selected_session.get('tests', []))
                    if selected_session.get('is_complete'):
                        st.success(f"✅ セッション「{session_id}」に追加します（完了済み7種目）")
                    else:
                        st.info(f"📋 セッション「{session_id}」に追加します（未完了 {selected_test_count}/7種目）\n続きからアップロードできます。")
            else:
                st.warning(f"⚠️ 選手ID「{st.session_state.athlete_id}」の過去セッションが見つかりません")
                st.info("「新規セッションを開始」を選択してください")
                session_id = None

        except ValueError as e:
            # AWS認証・設定エラー
            st.error("❌ AWS設定エラー: DynamoDBに接続できません")
            st.info("💡 **対処法**:\n- AWS認証情報を確認してください\n- DynamoDBテーブルが存在するか確認してください")
            record_error("wizard_step3_session_mode", f"ValueError: {str(e)}")
            session_id = None
        except Exception as e:
            # その他のエラー（データ形式、ネットワーク等）
            error_msg = str(e)
            st.error(f"❌ 過去セッション取得エラー: {error_msg}")
            st.info("💡 **対処法**:\n- 「新規セッションを開始」を選択してください\n- 問題が続く場合は管理者に連絡してください")
            record_error("wizard_step3_session_mode", f"Exception: {error_msg}")
            session_id = None

    st.markdown("---")

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if st.button("← 戻る", use_container_width=True):
            st.session_state.wizard_step = 2
            st.rerun()

    with col_btn2:
        if session_id and st.button("アップロード開始 →", type="primary", use_container_width=True):
            st.session_state.session_id = session_id

            # CRITICAL: 既存セッションの場合、アップロード済み種目をスキップ
            # 未アップロード種目から開始する（ADR-026）
            next_step = 4  # デフォルトは種目①から
            uploaded_tests = []  # 既存セッションのアップロード済み種目

            if session_mode == "既存セッションに追加":
                try:
                    # 既存セッションのアップロード済み種目を確認
                    items = load_results_items(resources, demo_mode=False)
                    items_converted = [convert_decimals(item) for item in items]
                    items_filtered = [
                        item for item in items_converted
                        if not str(item.get('video_id', '')).startswith('METADATA')
                    ]

                    # 選択したセッションのテスト一覧を取得
                    from session_dao import get_session_by_id
                    session_data = get_session_by_id(items_filtered, st.session_state.athlete_id, session_id)

                    if session_data:
                        uploaded_test_types = set(test.get('test_type') for test in session_data.get('tests', []))
                        uploaded_tests = list(uploaded_test_types)

                        # 未アップロードの最初の種目を見つける
                        for i, test_type in enumerate(TEST_TYPES):
                            if test_type not in uploaded_test_types:
                                next_step = 4 + i  # wizard_step = 4 + test_index
                                break
                        else:
                            # 全種目アップロード済みの場合、最後の種目（⑦）へ
                            next_step = 10

                except Exception as e:
                    # エラー時はデフォルト（種目①）から開始
                    record_error("wizard_find_next_test", str(e))
                    next_step = 4

            # uploaded_testsを初期化（既存セッションの場合は既存データを含む）
            st.session_state.uploaded_tests = uploaded_tests
            st.session_state.wizard_step = next_step
            st.rerun()


def render_test_upload_page(s3_client, resources, test_index, demo_mode):
    """Step 4-10: 種目別アップロードページ"""
    test_type = TEST_TYPES[test_index]
    test_name = TEST_TYPE_DISPLAY.get(test_type, test_type)

    st.header(f"📹 種目{test_index + 1}: {test_name}")

    # 進捗バー
    progress = len(st.session_state.uploaded_tests) / 7
    st.progress(progress, text=f"進捗: {len(st.session_state.uploaded_tests)}/7種目完了")

    st.info(f"選手ID: **{st.session_state.athlete_id}** | セッションID: **{st.session_state.session_id}**")

    # 既にアップロード済みの種目の場合は通知
    if test_type in st.session_state.uploaded_tests:
        st.warning(f"⚠️ この種目（{test_name}）は既にアップロード済みです。\n上書きする場合は再度アップロードしてください。")

    # アップロード済みチェックリスト
    with st.expander("📋 アップロード状況"):
        for i, tt in enumerate(TEST_TYPES):
            status = "✅" if tt in st.session_state.uploaded_tests else "⬜"
            st.write(f"{status} 種目{i+1}: {TEST_TYPE_DISPLAY.get(tt, tt)}")

    st.markdown("---")

    # 動画ファイルアップロード
    uploaded_file = st.file_uploader(
        f"種目{test_index + 1}の動画を選択（MP4形式）",
        type=['mp4'],
        key=f"upload_{test_type}",
        help="S3にアップロードされ、自動的に処理が開始されます"
    )

    if uploaded_file is not None:
        # バリデーション機能
        col_val, col_skip = st.columns(2)

        with col_val:
            if st.button("種目チェック（推奨）", type="secondary", use_container_width=True):
                with st.spinner("動画を解析中... (10-30秒程度かかります)"):
                    import tempfile
                    import os
                    from utils.video_validator import VideoValidator

                    # 一時ファイルに保存
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
                        tmp_file.write(uploaded_file.read())
                        tmp_path = tmp_file.name

                    # バリデーション実行
                    validator = VideoValidator()
                    is_valid, message, details = validator.validate(tmp_path, test_type)

                    # 結果を保存
                    st.session_state.validation_result = {
                        'is_valid': is_valid,
                        'message': message,
                        'details': details
                    }

                    # 一時ファイル削除
                    os.unlink(tmp_path)

        with col_skip:
            if st.button("スキップしてアップロード", use_container_width=True):
                st.session_state.validation_result = {'is_valid': True, 'message': 'スキップ', 'details': {}}

        # バリデーション結果の表示
        if 'validation_result' in st.session_state and st.session_state.validation_result:
            result = st.session_state.validation_result

            if result['is_valid']:
                st.success(result['message'])
                if result.get('details'):
                    with st.expander("📊 詳細情報"):
                        st.json(result['details'])
            else:
                st.warning(result['message'])
                if result.get('details'):
                    with st.expander("📊 詳細情報"):
                        st.json(result['details'])

        # アップロードボタン
        if 'validation_result' in st.session_state and st.session_state.validation_result:
            if st.button("✅ アップロード実行", type="primary", use_container_width=True):
                with st.spinner("アップロード中..."):
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    s3_key = f"videos/{test_type}/{st.session_state.athlete_id}_{st.session_state.session_id}_{test_type}_{timestamp}.mp4"

                    try:
                        uploaded_file.seek(0)
                        s3_client.upload_fileobj(
                            uploaded_file,
                            resources['videos_bucket'],
                            s3_key,
                            ExtraArgs={
                                'Metadata': {
                                    'athlete-id': st.session_state.athlete_id,
                                    'session-id': st.session_state.session_id,
                                    'test-type': test_type
                                }
                            }
                        )

                        st.success(f"✅ アップロード成功: 種目{test_index + 1}")
                        st.session_state.uploaded_tests.append(test_type)
                        st.session_state.validation_result = None

                        # ページトップにスクロール（ステータスバーを表示）
                        st.session_state.scroll_to_top = True

                        # 次の種目へ
                        if test_index < 6:  # まだ種目が残っている
                            st.session_state.wizard_step += 1
                            st.rerun()
                        else:  # 全種目完了
                            st.session_state.wizard_step = 11
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ アップロードに失敗しました: {str(e)}")

    st.markdown("---")

    col_btn1, col_btn2 = st.columns(2)

    with col_btn1:
        if test_index > 0:
            if st.button("← 前の種目", use_container_width=True):
                st.session_state.wizard_step -= 1
                st.rerun()

    with col_btn2:
        if test_index < 6 and test_type in st.session_state.uploaded_tests:
            if st.button("次の種目 →", use_container_width=True):
                st.session_state.wizard_step += 1
                st.rerun()


def render_completion_page():
    """Step 11: 完了ページ"""
    st.header("🎉 アップロード完了！")

    st.balloons()

    st.success(f"7種目すべてのアップロードが完了しました！")

    st.info(f"選手ID: **{st.session_state.athlete_id}**\nセッションID: **{st.session_state.session_id}**")

    st.markdown("### アップロードした種目")
    for i, test_type in enumerate(TEST_TYPES):
        status = "✅" if test_type in st.session_state.uploaded_tests else "⬜"
        st.write(f"{status} 種目{i+1}: {TEST_TYPE_DISPLAY.get(test_type, test_type)}")

    st.markdown("---")

    st.markdown("""
    ### 次のステップ

    1. **評価結果を確認** - 「📋 評価結果一覧」ページで各種目の評価を確認
    2. **セッション詳細を表示** - 「📊 セッション一覧」ページでセッション全体を確認
    3. **セッション比較** - セッション詳細ページで過去セッションと比較
    """)

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📊 セッション一覧を見る", type="primary", use_container_width=True):
            # セッション状態をクリア
            st.session_state.wizard_step = 1
            st.session_state.athlete_name = None
            st.session_state.birth_date = None
            st.session_state.athlete_id = None
            st.session_state.session_id = None
            st.session_state.uploaded_tests = []
            st.session_state.validation_result = None
            # ページ切り替え（実装はmain()で処理）
            st.info("サイドバーから「📊 セッション一覧」を選択してください")

    with col2:
        if st.button("🔄 新しいセッションを開始", use_container_width=True):
            # セッション状態をクリア
            st.session_state.wizard_step = 1
            st.session_state.athlete_name = None
            st.session_state.birth_date = None
            st.session_state.athlete_id = None
            st.session_state.session_id = None
            st.session_state.uploaded_tests = []
            st.session_state.validation_result = None
            st.rerun()


def results_list_page(dynamodb, resources, demo_mode=False, coach_mode=False):
    """
    What: 評価結果一覧ページ
    Why: DynamoDBから評価結果を取得して一覧表示
    Design Decision: pandas DataFrameで表形式表示（ADR-014）

    Args:
        dynamodb: DynamoDB resource
        resources: AWSリソース名
        demo_mode: デモモードフラグ

    CRITICAL: DynamoDB Scanは項目数が多い場合にコスト増加
    """
    st.header("📊 評価結果一覧")

    if demo_mode:
        st.info("🎭 **デモモード**: サンプルデータを表示中")

    try:
        items = load_results_items(resources, demo_mode)
    except ValueError:
        st.error("❌ AWS設定エラー: AccountIdが取得できません")
        return
    except Exception as e:
        st.error("❌ 評価結果を取得できませんでした")
        st.caption("ネットワークやAWS権限を確認し、ページを再読み込みしてください")
        with st.expander("技術情報 (サポート向け)"):
            st.code(str(e))
        return

    # 共通処理（デモモード・通常モード両対応）
    try:

        if not items:
            st.warning("評価結果がありません。動画をアップロードしてください。")
            return

        # CRITICAL: DynamoDBのDecimal型をfloatに変換（DataFrame作成前）
        # convert_decimals は dashboard/utils/dynamo_helpers.py で定義（ADR-026）
        items_converted = [convert_decimals(item) for item in items]

        # DataFrame変換
        df = pd.DataFrame(items_converted)

        # メタデータ/必須列のチェック
        required_columns = {'video_id', 'test_type'}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            st.error("❌ 必須データが不足しているため、評価結果を表示できません")
            with st.expander("不足している項目"):
                st.write(sorted(missing_columns))
            return

        if 'processed_at' not in df.columns:
            df['processed_at'] = None
        if 'score' not in df.columns:
            df['score'] = None

        # メタデータ行を除外しつつ、欠損データは保持
        df = df[
            df['video_id'].notna() &
            ~df['video_id'].astype(str).str.startswith('METADATA') &
            df['test_type'].notna()
        ].copy()

        if df.empty:
            st.warning("評価結果がありません。動画をアップロードしてください。")
            return

        # processed_atの変換（欠損は末尾へソート）
        try:
            df['processed_at_dt'] = pd.to_datetime(df['processed_at'], errors='coerce')
            df = df.sort_values('processed_at_dt', ascending=False, na_position='last')
        except Exception as e:
            st.warning(f"⚠️ 日時データの解析に失敗しました: {str(e)}")
            df['processed_at_dt'] = pd.NaT

        max_months = st.session_state.get('max_months', PERFORMANCE_LIMITS['max_months'])
        max_records = st.session_state.get('max_records', PERFORMANCE_LIMITS['max_records'])

        try:
            # CRITICAL: タイムゾーンなしのTimestampで比較（processed_at_dtはdatetime64[ns]）
            cutoff = pd.Timestamp.now() - pd.DateOffset(months=int(max_months))
            # タイムゾーン情報を除去して比較
            if cutoff.tz is not None:
                cutoff = cutoff.tz_localize(None)
            df = df[df['processed_at_dt'].isna() | (df['processed_at_dt'] >= cutoff)]
        except Exception as e:
            st.warning(f"⚠️ 期間フィルタ適用に失敗しました: {str(e)}")

        if len(df) > max_records:
            st.info(f"最新 {max_records}件のみ表示しています。サイドバーで上限を調整できます。")
            df = df.head(int(max_records))

        # 追加情報の抽出
        version_info_series = df.apply(lambda row: extract_version_info(row.to_dict()), axis=1)
        df['version_label'] = version_info_series.apply(format_version_label)
        df['version_warning'] = version_info_series.apply(
            lambda info: "⚠️ バージョン不整合" if info.get('mismatch') else ""
        )

        # CRITICAL: version_warningカラム作成後に集計（順序重要）
        stats_total = int(len(df))
        stats_mismatch = int((df['version_warning'] != "").sum()) if not df.empty else 0
        st.session_state['version_mismatch_stats'] = {
            'total': stats_total,
            'mismatch': stats_mismatch,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        df['client_display'] = df['video_id'].apply(format_client_id_display)
        df['rules_version_raw'] = version_info_series.apply(lambda info: info.get('rules_version'))

        quality_info_series = df.apply(lambda row: compute_quality_status(row.get('health_check')), axis=1)
        df['quality_label'] = quality_info_series.apply(lambda info: info['label'])
        df['quality_status'] = quality_info_series.apply(lambda info: info['status'])
        df['score_display'] = df['score'].apply(format_score_display)
        df['processed_at_display'] = df['processed_at_dt'].apply(
            lambda ts: format_timestamp_display(ts) if pd.notna(ts) else "データ未取得"
        )

        # 表示用に列を構築
        df_display = df[[
            'client_display',
            'test_type',
            'score_display',
            'processed_at_display',
            'version_label',
            'version_warning',
            'quality_label',
            'video_id'
        ]].copy()

        df_display['rules_version_raw'] = df['rules_version_raw'].values

        df_display.rename(
            columns={
                'client_display': 'client',
                'test_type': 'test_type',  # フィルタ用に原名維持
                'score_display': 'スコア',
                'processed_at_display': '計測日時',
                'version_label': 'バージョン',
                'version_warning': 'バージョン警告',
                'quality_label': '品質',
            },
            inplace=True,
        )

        # テストタイプフィルタ
        test_filter = st.multiselect(
            "テストタイプでフィルタ",
            TEST_TYPES,
            default=TEST_TYPES
        )
        df_filtered = df_display[df_display['test_type'].isin(test_filter)].copy()

        if df_filtered.empty:
            st.info("選択された条件に一致する評価結果はありません")
            return

        # テーブル表示（video_idカラムは非表示）
        st.dataframe(
            df_filtered[['client', 'test_type', 'スコア', '計測日時', 'バージョン', 'バージョン警告', '品質']],
            use_container_width=True,
            hide_index=True
        )

        rules_versions = {
            rv for rv in df_filtered['rules_version_raw'].dropna().unique()
            if isinstance(rv, str)
        }
        dominant_rules_version = None
        if len(rules_versions) == 1:
            dominant_rules_version = next(iter(rules_versions))
        elif len(rules_versions) > 1:
            dominant_rules_version = 'mixed'

        log_dashboard_event(
            "view_list",
            rules_version=dominant_rules_version,
            displayed_count=int(len(df_filtered)),
            filters={'test_types': test_filter},
            max_records=max_records,
            max_months=max_months,
        )

        # 詳細表示用の選択
        st.subheader("詳細結果")

        # クライアント選択用のマッピング作成
        client_to_video_id = dict(zip(df_filtered['client'], df_filtered['video_id']))

        selected_client = st.selectbox(
            "クライアントを選択",
            df_filtered['client'].tolist()
        )

        if selected_client:
            selected_video = client_to_video_id[selected_client]
            detail_row = df[df['video_id'] == selected_video]
            selected_test_type = detail_row['test_type'].iloc[0] if not detail_row.empty else None
            with execution_timer(
                "view_detail_processing",
                video_id=selected_video,
                test_type=selected_test_type,
            ) as detail_stats:
                show_result_detail(df, selected_video, coach_mode)
            if st.session_state.get('debug_mode') and detail_stats.duration_ms is not None:
                st.caption(f"⏱ 詳細表示処理時間: {detail_stats.duration_ms:.0f} ms")

    except Exception as e:
        st.error("❌ 評価結果の表示中に予期せぬエラーが発生しました")
        st.caption("時間をおいて再度アクセスするか、サポートチームへご連絡ください")
        with st.expander("技術情報 (サポート向け)"):
            st.code(str(e))
        record_error("results_list_page", str(e))


def get_previous_result(df: pd.DataFrame, video_id: str, test_type: str) -> Optional[Dict]:
    """
    What: 同じクライアント・種目の前回結果を取得
    Why: 前回比較表示に使用
    Design Decision: 同じクライアントIDの過去データを時系列検索

    Args:
        df: 全データのDataFrame
        video_id: 現在のvideo_id
        test_type: テストタイプ

    Returns:
        前回の結果データ（Dict）または None
    """
    # 現在のクライアントID抽出
    current_client = format_client_id_display(video_id)

    # 同じクライアント・同じテストタイプでフィルタ
    df_same_client = df[
        (df['video_id'].apply(format_client_id_display) == current_client) &
        (df['test_type'] == test_type) &
        (df['video_id'] != video_id)  # 現在のデータを除外
    ].copy()

    if df_same_client.empty:
        return None

    # processed_at で降順ソート（最新の過去データ）
    try:
        df_same_client['processed_at'] = pd.to_datetime(df_same_client['processed_at'])
        df_same_client = df_same_client.sort_values('processed_at', ascending=False)
    except Exception:
        # datetime変換失敗時はソートせずそのまま使用
        pass

    # 最新の過去データを返す
    return df_same_client.iloc[0].to_dict()


def show_result_detail(df: pd.DataFrame, video_id: str, coach_mode: bool = False):
    """
    What: 詳細結果表示（v2.1: 80点満点対応版）
    Why: 選択された動画の評価結果詳細を表示
    Design Decision: v2.1システム（80点満点 = Section A 20点 + Section B 60点）

    CRITICAL: evaluation フィールドの構造に依存（v2.1形式）
    """
    # 該当行取得
    row = df[df['video_id'] == video_id].iloc[0]
    record = row.to_dict()
    test_type = record.get('test_type')
    test_name = TEST_TYPE_DISPLAY.get(test_type, test_type)

    evaluation_dict = record.get('evaluation') if isinstance(record.get('evaluation'), dict) else {}
    evaluation_version = evaluation_dict.get('version') if isinstance(evaluation_dict.get('version'), str) else None
    version_info = extract_version_info(record)
    score_summary = summarize_scores(record)

    # 種目名表示
    st.markdown(f"## {test_name}")
    st.markdown("---")

    # バージョン表示
    st.caption(f"📘 {format_version_label(version_info)}")
    if version_info.get('mismatch'):
        st.warning("⚠️ バージョン不整合: scoring_version と evaluation.version が一致していません")

    if not score_summary['available'] and score_summary.get('message'):
        st.info(f"ℹ️ {score_summary['message']}")

    log_dashboard_event(
        "view_detail",
        rules_version=version_info.get('rules_version'),
        video_id=video_id,
        test_type=test_type,
    )

    max_score = score_summary.get('max_score')
    total_score = score_summary.get('total_score')
    execution_score = score_summary.get('execution_score')
    principles_score = score_summary.get('principles_score')

    percentage = None
    if score_summary['available'] and total_score is not None and max_score:
        try:
            percentage = (total_score / max_score) * 100
        except ZeroDivisionError:
            percentage = None

    total_denominator = str(int(max_score)) if isinstance(max_score, (int, float)) and max_score else "-"
    total_display = f"{total_score:.1f}/{total_denominator}" if total_score is not None and max_score else "N/A"
    percentage_display = f"{percentage:.0f}%" if percentage is not None else "N/A"

    if percentage is None:
        color_emoji = "⚪️"
        status_text = "評価待ち"
    elif percentage >= 80:
        color_emoji = "🟢"
        status_text = "優秀"
    elif percentage >= 60:
        color_emoji = "🟡"
        status_text = "良好"
    else:
        color_emoji = "🔴"
        status_text = "要改善"

    total_help = "Section A(20点) + Section B(60点)" if max_score == 80.0 else (
        "旧システム（12点満点）" if max_score == 12.0 else "スコア情報が未確定です"
    )
    rate_help = f"総合スコア / {total_denominator}点満点" if max_score else "スコア情報が未確定です"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("総合スコア", total_display, help=total_help)
    with col2:
        st.metric("達成率", percentage_display, help=rate_help)
    with col3:
        st.metric("評価", f"{color_emoji} {status_text}")

    def ratio_display(value: Optional[float], denominator: str) -> str:
        return f"{value:.1f}/{denominator}" if value is not None else "N/A"

    st.markdown("")
    if max_score == 80.0:
        st.write(f"📐 **Section A（実施可否）**: {ratio_display(execution_score, '20.0')}")
        st.write(f"🎯 **Section B（8原則）**: {ratio_display(principles_score, '60.0')}")
    elif max_score == 12.0:
        st.write(f"📐 **完全性**: {ratio_display(execution_score, '3.0')}")
        st.write(f"🎯 **7原則**: {ratio_display(principles_score, '9.0')}")
    else:
        st.write("📐 スコア情報が不足しています（計算完了をお待ちください）")

    # === 評価される原則のみ表示 ===
    st.markdown("---")
    st.subheader("📊 評価原則の詳細")

    def render_phase_scores(title: str, scores: Dict[str, Any]) -> None:
        if not isinstance(scores, dict):
            st.info(f"{title} の詳細スコアは未取得です")
            return

        numeric_items = [(key, value) for key, value in scores.items() if isinstance(value, (int, float))]
        if not numeric_items:
            st.info(f"{title} の詳細スコアは未取得です")
            return

        st.markdown(title)
        for key, value in numeric_items:
            principle_num = key.split('_')[0].replace('B', '')
            principle_full_name = key.replace(f'B{principle_num}_', '').replace('_', ' ').title()
            warning = " ⚠️" if value < 2.0 else ""

            max_principle_score = 15.0
            progress = min(value / max_principle_score, 1.0) if max_principle_score else 0.0

            st.write(f"**B{principle_num} {principle_full_name}**: {value:.1f}点{warning}")
            st.progress(progress)

            details_key = f'{key.split("_")[0]}_details'
            details = scores.get(details_key)
            if isinstance(details, dict):
                reason = details.get('reason', '')
                severity = details.get('severity', 'low')

                if severity == 'high':
                    st.error(f"🔴 {reason}")
                elif severity == 'medium':
                    st.warning(f"🟡 {reason}")
                elif reason and not reason.startswith('✅'):
                    st.info(f"ℹ️ {reason}")
                elif reason.startswith('✅'):
                    st.success(reason)

                if coach_mode and 'coach_details' in details:
                    st.markdown("**📊 コーチ詳細情報:**")
                    coach = details['coach_details']
                    for detail_key, detail_value in coach.items():
                        if detail_key == 'deductions' and isinstance(detail_value, list):
                            st.write("**減点内訳:**")
                            for deduction in detail_value:
                                st.write(f"  - {deduction}")
                        elif detail_key.startswith('threshold'):
                            st.write(f"**{detail_key}**: {detail_value}")
                        elif detail_value is not None:
                            st.write(f"**{detail_key}**: {detail_value}")

            st.write("")

    if evaluation_version == 'v2.1' and score_summary['available']:
        b_principles = evaluation_dict.get('B_principles', {}) if isinstance(evaluation_dict, dict) else {}
        ecc_scores = b_principles.get('eccentric', {}) if isinstance(b_principles, dict) else {}
        con_scores = b_principles.get('concentric', {}) if isinstance(b_principles, dict) else {}

        render_phase_scores("### 下降局面（Eccentric）", ecc_scores)
        render_phase_scores("### 上昇局面（Concentric）", con_scores)
    elif score_summary['available'] and principles_score is not None:
        principles_to_show = TEST_PRINCIPLES_MAP.get(test_type, [])

        if principles_to_show:
            st.write("")
            for principle_num in principles_to_show:
                if principles_score is None or len(principles_to_show) == 0:
                    continue

                if max_score == 80.0:
                    score = principles_score / len(principles_to_show)
                    max_principle_score = 60.0 / len(principles_to_show)
                elif max_score == 12.0:
                    score = principles_score / len(principles_to_show)
                    max_principle_score = 9.0 / len(principles_to_show)
                else:
                    score = None
                    max_principle_score = 0

                principle_name = PRINCIPLE_NAMES.get(principle_num, f"P{principle_num}")

                if score is None or max_principle_score == 0:
                    st.write(f"**P{principle_num} {principle_name}**: N/A")
                    continue

                warning = " ⚠️" if score < 2.0 else ""
                progress = min(score / max_principle_score, 1.0) if max_principle_score > 0 else 0
                st.write(f"**P{principle_num} {principle_name}**: {score:.1f}/{max_principle_score:.1f}点{warning}")
                st.progress(progress)
                st.write("")
        else:
            st.info("この種目の評価原則マッピングが未定義です")
    else:
        st.info("詳細な原則スコアはまだ利用できません")

    # === 動作フレーム表示（ピーク・ベスト・ワースト） ===
    st.markdown("---")
    st.subheader("📸 動作フレーム（ピーク・ベスト・ワースト）")

    # Phase 2.5で実装予定: S3から3枚画像を取得して骨格線付きで表示
    # s3://{bucket}/{user_id}/{test_type}/{timestamp}/frames/peak.jpg
    # s3://{bucket}/{user_id}/{test_type}/{timestamp}/frames/best.jpg
    # s3://{bucket}/{user_id}/{test_type}/{timestamp}/frames/worst.jpg
    peak_frame_url = None  # TODO: Phase 2.5で実装
    best_frame_url = None  # TODO: Phase 2.5で実装
    worst_frame_url = None  # TODO: Phase 2.5で実装

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**🎯 ピークフレーム**")
        if peak_frame_url:
            st.image(peak_frame_url, caption="動作完遂度（最大屈曲時）")
        else:
            st.info("Phase 2.5で実装予定\n\n動作のピーク時点（最大屈曲）の骨格線付き画像を表示します")

    with col2:
        st.markdown("**✅ ベストフレーム**")
        if best_frame_url:
            st.image(best_frame_url, caption="フォーム総合評価最高点")
        else:
            st.info("Phase 2.5で実装予定\n\nフォームが最も優れているフレームの骨格線付き画像を表示します")

    with col3:
        st.markdown("**⚠️ ワーストフレーム**")
        if worst_frame_url:
            st.image(worst_frame_url, caption="改善ポイント")
        else:
            st.info("Phase 2.5で実装予定\n\n改善が必要なフレームの骨格線付き画像を表示します")

    # === 前回との比較セクション（常時表示） ===
    st.markdown("---")
    st.subheader("📈 前回との比較")

    prev_summary = None
    prev_version_info = None
    compatibility = None
    previous = get_previous_result(df, video_id, test_type)

    if previous is None:
        # 初回時の表示
        st.info("""
        これが初回評価です。

        次回の評価で、今回との比較がここに表示されます。

        定期的な評価で成長を可視化しましょう。
        """)
    else:
        # 2回目以降の表示（欠損データを考慮）
        prev_version_info = extract_version_info(previous)
        compatibility = evaluate_rules_compatibility(version_info, prev_version_info)
        prev_summary = summarize_scores(previous)
        prev_total = prev_summary.get('total_score')
        prev_max_score = prev_summary.get('max_score')

        comparison_allowed = True
        override_key = f"compare_override_{video_id}_{compatibility['status']}"

        if compatibility['status'] == 'incompatible':
            st.warning(f"⚠️ 互換性なし: {compatibility['reason']} ({compatibility['current']} vs {compatibility['target']})")
            comparison_allowed = st.checkbox(
                "リスクを理解した上で比較を表示する",
                value=False,
                key=override_key,
            )
        elif compatibility['status'] == 'unknown':
            st.info(f"ℹ️ バージョン不明: {compatibility['reason']}")
            comparison_allowed = st.checkbox(
                "不明なバージョンを含めて比較を表示する",
                value=False,
                key=override_key,
            )

        if not comparison_allowed:
            st.caption("比較は非表示です。チェックボックスをONにすると表示できます。")
            log_dashboard_event(
                "compare_blocked",
                rules_version=version_info.get('rules_version'),
                previous_rules_version=prev_version_info.get('rules_version') if prev_version_info else None,
                status=compatibility['status'],
            )
        elif percentage is None or total_score is None or not max_score:
            st.info("今回のスコアが確定していないため、比較は表示されません")
        elif not prev_summary['available'] or prev_total is None or not prev_max_score:
            st.warning("前回スコアが未取得のため比較できません")
            if prev_summary.get('message'):
                st.caption(f"ℹ️ {prev_summary['message']}")
        else:
            with execution_timer(
                "compare_processing",
                rules_version=version_info.get('rules_version'),
                previous_rules_version=prev_version_info.get('rules_version') if prev_version_info else None,
            ) as compare_stats:
                curr_pct = percentage
                try:
                    prev_pct = (prev_total / prev_max_score) * 100
                except ZeroDivisionError:
                    prev_pct = None

                if curr_pct is None or prev_pct is None:
                    st.info("達成率が算出できなかったため比較をスキップします")
                else:
                    diff = total_score - prev_total
                    pct_diff = curr_pct - prev_pct
                    use_percentage_only = prev_max_score != max_score

                    col1, col2 = st.columns(2)
                    with col1:
                        if use_percentage_only:
                            st.metric("達成率（今回）", f"{curr_pct:.0f}%", f"{pct_diff:+.0f}%")
                        else:
                            st.metric("総合スコア", f"{total_score:.1f}/{int(max_score)}", f"{diff:+.1f}")
                    with col2:
                        if use_percentage_only:
                            st.info(f"前回システム: {int(prev_max_score)}点満点、今回: {int(max_score)}点満点")
                        else:
                            st.metric("達成率", f"{curr_pct:.0f}%", f"{pct_diff:+.0f}%")

                    st.write("")

                    if pct_diff > 5:
                        st.success(f"✅ **{pct_diff:.1f}% 改善しました！**")
                    elif pct_diff < -5:
                        st.warning(f"⚠️ **{abs(pct_diff):.1f}% 低下しています**")
                    else:
                        st.info("📊 前回とほぼ同じ水準です")

                    if use_percentage_only:
                        st.caption("ℹ️ スコアシステムが異なるため、達成率での比較を表示しています")

                    log_dashboard_event(
                        "compare",
                        rules_version=version_info.get('rules_version'),
                        previous_rules_version=prev_version_info.get('rules_version') if prev_version_info else None,
                        pct_diff=pct_diff,
                        use_percentage_only=use_percentage_only,
                    )

            if st.session_state.get('debug_mode') and compare_stats.duration_ms is not None:
                st.caption(f"⏱ 比較処理時間: {compare_stats.duration_ms:.0f} ms")

    # === レーダーチャート ===
    st.markdown("---")
    st.subheader("🕸️ レーダーチャート")

    current_radar_scores = extract_principle_radar_scores(evaluation_dict) if evaluation_version == 'v2.1' else {}

    if not current_radar_scores:
        st.info("v2.1形式の原則スコアが不足しているため、レーダーチャートを表示できません")
        log_dashboard_event(
            "radar_chart_unavailable",
            rules_version=version_info.get('rules_version'),
            reason="missing_current_scores",
        )
    else:
        with execution_timer(
            "radar_chart_processing",
            rules_version=version_info.get('rules_version'),
        ) as radar_stats:
            previous_radar_scores: Dict[int, float] = {}
            overlay_previous = False
            radar_compatibility = compatibility

            if previous and isinstance(previous.get('evaluation'), dict):
                prev_eval = previous['evaluation']
                if prev_eval.get('version') == 'v2.1':
                    previous_radar_scores = extract_principle_radar_scores(prev_eval)
                    if previous_radar_scores:
                        if radar_compatibility is None:
                            prev_version_info = extract_version_info(previous)
                            radar_compatibility = evaluate_rules_compatibility(version_info, prev_version_info)

                        override_key = f"radar_override_{video_id}_{radar_compatibility['status']}"
                        if radar_compatibility['status'] == 'incompatible':
                            st.warning(f"⚠️ レーダーチャート比較無効: {radar_compatibility['reason']}")
                            overlay_previous = st.checkbox(
                                "リスクを理解した上で前回データを重ねて表示する",
                                value=False,
                                key=override_key,
                            )
                        elif radar_compatibility['status'] == 'unknown':
                            st.info(f"ℹ️ レーダーチャート比較: {radar_compatibility['reason']}")
                            overlay_previous = st.checkbox(
                                "不明なバージョンを含めてレーダーチャートを重ねる",
                                value=False,
                                key=override_key,
                            )
                        else:
                            overlay_previous = True

                        if not overlay_previous:
                            previous_radar_scores = {}
                else:
                    st.caption("ℹ️ 前回データがv2.1形式ではないためレーダーチャートの比較対象になりません")

            combined_principles = sorted(set(current_radar_scores.keys()) | set(previous_radar_scores.keys()))

            if not combined_principles:
                st.info("レーダーチャートに必要な原則スコアが取得できませんでした")
                log_dashboard_event(
                    "radar_chart_unavailable",
                    rules_version=version_info.get('rules_version'),
                    reason="missing_principle_scores",
                )
            else:
                categories = [f"B{pid} {PRINCIPLE_NAMES.get(pid, '')}".strip() for pid in combined_principles]
                current_values = [current_radar_scores.get(pid, 0.0) for pid in combined_principles]
                current_values.append(current_values[0])
                categories_closed = categories + [categories[0]]

                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=current_values,
                    theta=categories_closed,
                    fill='toself',
                    name='今回',
                    line=dict(color='#1f77b4'),
                    fillcolor='rgba(31, 119, 180, 0.3)'
                ))

                if overlay_previous and previous_radar_scores:
                    previous_values = [previous_radar_scores.get(pid, 0.0) for pid in combined_principles]
                    previous_values.append(previous_values[0])
                    fig.add_trace(go.Scatterpolar(
                        r=previous_values,
                        theta=categories_closed,
                        fill='toself',
                        name='前回',
                        line=dict(color='#ff7f0e'),
                        fillcolor='rgba(255, 127, 14, 0.3)'
                    ))

                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 15])
                    ),
                    showlegend=True,
                    margin=dict(l=60, r=60, t=40, b=40)
                )

                st.plotly_chart(fig, use_container_width=True)

                log_dashboard_event(
                    "radar_chart",
                    rules_version=version_info.get('rules_version'),
                    overlay_previous=overlay_previous,
                    principle_count=len(combined_principles),
                )

        if st.session_state.get('debug_mode') and radar_stats.duration_ms is not None:
            st.caption(f"⏱ レーダーチャート処理時間: {radar_stats.duration_ms:.0f} ms")

    # === Health Check ===
    st.markdown("---")
    with st.expander("🏥 Health Check"):
        health = row.get('health_check')
        quality = compute_quality_status(health)
        label = quality['label']
        message = quality['reason']
        status = quality['status']

        if status == 'error':
            st.error(f"{label} {message}")
        elif status == 'warning':
            st.warning(f"{label} {message}")
        else:
            st.success(f"{label} {message}")

        if isinstance(health, dict):
            if 'detection_rate' in health and isinstance(health['detection_rate'], (int, float)):
                st.metric("検出率", f"{health['detection_rate']*100:.1f}%")

            if 'warnings' in health and health['warnings']:
                st.warning("⚠️ 警告:")
                for warning in health['warnings']:
                    st.write(f"- {warning}")

            st.json(health)
        else:
            st.info("Health Check データが利用できません")

    # === JSON詳細 ===
    with st.expander("🔍 JSON詳細（デバッグ用）"):
        st.json(row.to_dict())


def incomplete_sessions_management_page(s3_client, dynamodb, resources, demo_mode):
    """
    What: 未完了セッション管理ページ
    Why: 途中で中断したセッションの削除または再開をサポート
    Design Decision: セッション単位で削除、S3+DynamoDB両方から削除
    """
    st.header("🗑️ 未完了セッション管理")

    if demo_mode:
        st.info("🎭 **デモモード**: 削除機能は無効です")
        return

    st.markdown("""
    ### 未完了セッション（7種目未満）の管理

    途中で中断したセッションを表示・削除できます：
    - ✅ **継続したい場合**: 「📤 動画アップロード」→「既存セッションに追加」から再開
    - ❌ **不要な場合**: 以下のリストから選択して削除

    **注意**: 削除すると、DynamoDB の処理結果が削除されます。
    """)

    st.markdown("---")

    # 未完了セッション一覧を取得
    try:
        items = load_results_items(resources, demo_mode=False)
        from session_dao import group_tests_by_session
        items_converted = [convert_decimals(item) for item in items]
        items_filtered = [
            item for item in items_converted
            if not str(item.get('video_id', '')).startswith('METADATA')
        ]
        sessions = group_tests_by_session(items_filtered)

        # 未完了セッションのみフィルタ
        incomplete_sessions = [s for s in sessions if not s.get('is_complete', False)]

        if not incomplete_sessions:
            st.success("✅ 未完了セッションはありません！")
            st.info("すべてのセッションが7種目完了しています。")
            return

        st.warning(f"⚠️ 未完了セッション: {len(incomplete_sessions)}件")

        # 未完了セッション一覧を表示
        for session in incomplete_sessions:
            athlete_id = session.get('athlete_id', 'Unknown')
            session_id = session.get('session_id', 'Unknown')
            test_count = len(session.get('tests', []))
            grand_total = session.get('grand_total', 0)
            percentage = session.get('percentage', 0)
            processed_at = session.get('processed_at', 'Unknown')

            with st.expander(f"📋 {athlete_id} - {session_id} ({test_count}/7種目)", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("完了種目数", f"{test_count}/7")
                with col2:
                    st.metric("総合スコア", f"{grand_total:.1f}/560")
                with col3:
                    st.metric("達成率", f"{percentage:.1f}%")

                st.caption(f"最終更新: {processed_at}")

                # 種目一覧を表示
                st.markdown("**アップロード済み種目:**")
                for test in session.get('tests', []):
                    test_type = test.get('test_type', 'Unknown')
                    score = test.get('score', 0)
                    st.write(f"- {TEST_TYPE_DISPLAY.get(test_type, test_type)}: {score:.1f}点")

                st.markdown("---")

                # 削除ボタン
                delete_key = f"delete_{athlete_id}_{session_id}"
                if st.button(f"🗑️ このセッションを削除", key=delete_key, type="secondary"):
                    with st.spinner("削除中..."):
                        try:
                            # DynamoDBからレコード削除
                            table = dynamodb.Table(resources['table_name'])
                            deleted_count = 0

                            for test in session.get('tests', []):
                                video_id = test.get('video_id')
                                processed_at_val = test.get('processed_at')

                                if video_id and processed_at_val:
                                    table.delete_item(
                                        Key={
                                            'video_id': video_id,
                                            'processed_at': processed_at_val
                                        }
                                    )
                                    deleted_count += 1

                            st.success(f"✅ {deleted_count}件のレコードを削除しました")
                            st.info("ページをリロードして最新状態を確認してください")
                            time.sleep(2)
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ 削除に失敗しました: {str(e)}")
                            record_error("incomplete_sessions_delete", str(e))

    except Exception as e:
        st.error(f"❌ セッション一覧の取得に失敗しました: {str(e)}")
        record_error("incomplete_sessions_load", str(e))


def debug_info_page(dynamodb, resources, demo_mode):
    """
    What: デバッグ情報ページ（DynamoDBデータ状況確認）
    Why: データ保存状況を可視化し、トラブルシューティングを支援
    Design Decision: デバッグモード時のみ表示（ADR-026）

    CRITICAL: 本番環境では個人情報に注意
    """
    st.header("🔧 デバッグ情報")
    st.caption("DynamoDBのデータ状況を確認")

    if demo_mode:
        st.warning("🎭 デモモードではDynamoDBデータは表示されません")
        return

    try:
        items = load_results_items(resources, demo_mode=False)
    except ValueError:
        st.error("❌ AWS設定エラー: AccountIdが取得できません")
        st.info("💡 AWS認証情報を確認してください")
        return
    except Exception as e:
        st.error(f"❌ データ取得エラー: {str(e)}")
        st.info("💡 DynamoDBテーブルが存在するか確認してください")
        return

    # データ存在確認
    if not items:
        st.warning("⚠️ データが1件も見つかりませんでした")
        st.info("💡 対処法:\n- 動画をアップロードしてデータを作成してください\n- 別の環境（dev/prod）を確認してください")
        return

    # Decimal変換
    items_converted = [convert_decimals(item) for item in items]

    # メタデータとテストデータを分類
    metadata_items = [
        item for item in items_converted
        if str(item.get('video_id', '')).startswith('METADATA')
    ]
    test_items = [
        item for item in items_converted
        if not str(item.get('video_id', '')).startswith('METADATA')
    ]

    # サマリー表示
    st.subheader("📊 データサマリー")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("総件数", f"{len(items_converted)}件")
    with col2:
        st.metric("メタデータ", f"{len(metadata_items)}件")
    with col3:
        st.metric("テスト結果", f"{len(test_items)}件")

    # セッション統計
    if test_items:
        st.subheader("📈 セッション統計")

        athletes = set()
        sessions = set()
        test_types = set()

        for item in test_items:
            athlete_id = item.get('athlete_id')
            session_id = item.get('session_id')
            test_type = item.get('test_type')

            if athlete_id:
                athletes.add(athlete_id)
            if session_id:
                sessions.add((athlete_id, session_id))
            if test_type:
                test_types.add(test_type)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("選手数", f"{len(athletes)}人")
        with col2:
            st.metric("セッション数", f"{len(sessions)}件")
        with col3:
            st.metric("種目種類", f"{len(test_types)}種類")

        # 選手別セッション数
        st.subheader("👤 選手別セッション数")
        athlete_data = []
        for athlete in sorted(athletes):
            athlete_sessions = [s for s in sessions if s[0] == athlete]
            athlete_data.append({
                "選手ID": athlete,
                "セッション数": len(athlete_sessions)
            })
        st.dataframe(athlete_data, use_container_width=True)

        # 種目別件数
        st.subheader("🏋️ 種目別件数")
        test_type_data = []
        for test_type in sorted(test_types):
            count = sum(1 for item in test_items if item.get('test_type') == test_type)
            test_type_data.append({
                "種目": test_type,
                "件数": count
            })
        st.dataframe(test_type_data, use_container_width=True)

        # 最新5件
        st.subheader("📋 最新5件")
        sorted_items = sorted(
            test_items,
            key=lambda x: x.get('uploaded_at', ''),
            reverse=True
        )[:5]

        for i, item in enumerate(sorted_items, 1):
            with st.expander(f"{i}. {item.get('athlete_id', 'N/A')} / {item.get('session_id', 'N/A')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**種目**: {item.get('test_type', 'N/A')}")
                    st.write(f"**スコア**: {item.get('grand_total', 'N/A')}")
                with col2:
                    st.write(f"**アップロード日時**: {item.get('uploaded_at', 'N/A')}")
                    st.write(f"**video_id**: {item.get('video_id', 'N/A')}")

        # 生データJSON表示
        with st.expander("🔍 生データ（JSON）"):
            st.json(sorted_items[:3])  # 最新3件のみ


def main():
    """
    What: Streamlitアプリのメインエントリーポイント
    Why: ページルーティングとレイアウト構築
    Design Decision: サイドバーでページ切り替え（ADR-014）

    CRITICAL: AWS認証情報が設定されていることを前提
    """
    st.set_page_config(
        page_title="THF Motion Scan Dashboard",
        page_icon="🏒",
        layout="wide"
    )

    configure_structured_logging()

    if 'request_id' not in st.session_state:
        st.session_state['request_id'] = str(uuid.uuid4())

    if not st.session_state.get('page_load_logged'):
        log_dashboard_event("page_load")
        st.session_state['page_load_logged'] = True

    # ヘッダーリンク無効化CSS
    st.markdown("""
    <style>
    .stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

    # ページトップへのスクロール処理（アップロード完了時）
    if st.session_state.get('scroll_to_top', False):
        st.markdown("""
        <script>
            window.parent.document.querySelector('section.main').scrollTo(0, 0);
        </script>
        """, unsafe_allow_html=True)
        st.session_state.scroll_to_top = False

    # タイトル
    st.title("🏒 THF Motion Scan Dashboard")
    st.markdown("---")

    # サイドバー: 環境セレクタ
    env_options = get_available_environments()
    if "selected_env" not in st.session_state:
        st.session_state.selected_env = DEFAULT_ENV

    active_env = st.session_state.selected_env if st.session_state.selected_env in env_options else DEFAULT_ENV
    env_index = env_options.index(active_env)

    st.sidebar.markdown("---")
    selected_env = st.sidebar.selectbox(
        "環境",
        env_options,
        index=env_index,
        help="現在は本番環境のみ利用可能（将来的にdev/stagingを追加予定）",
    )

    if selected_env != st.session_state.selected_env:
        st.session_state.selected_env = selected_env
        log_dashboard_event("environment_change", new_environment=selected_env)
        emit_ui_metric("env_switch", environment=selected_env)

    # AWS クライアント初期化
    try:
        s3_client, dynamodb, resources = get_aws_clients(selected_env)
    except Exception as e:
        st.error(f"❌ AWS接続エラー: {str(e)}")
        st.info("AWS認証情報を確認してください（~/.aws/credentials または環境変数）")
        log_dashboard_event("aws_connection_error", level=logging.ERROR, error=str(e))
        record_error("aws_connection", str(e))
        return

    # デモモードトグル
    st.sidebar.markdown("---")
    demo_mode = st.sidebar.toggle(
        "🎭 デモモード",
        value=False,
        help="AWS環境なしでUIを確認できます。サンプルデータを表示します。"
    )

    if demo_mode:
        st.sidebar.warning("🎭 デモモード ON")
        st.sidebar.info("サンプルデータ（5件）を表示中")
        log_dashboard_event("demo_mode", enabled=True)
    else:
        # AWS Account ID表示
        if resources:
            st.sidebar.success(f"✅ AWS Account: {resources['account_id']}")
            st.sidebar.info(f"🏗️ 使用中の環境: {resources['environment']}")
        log_dashboard_event("demo_mode", enabled=False)

    # コーチモードチェックボックス（Phase 2.5a）
    st.sidebar.markdown("---")
    coach_mode = st.sidebar.checkbox(
        "🎓 コーチモード",
        value=False,
        help="技術詳細情報（測定値、閾値、減点内訳）を表示します"
    )

    if coach_mode:
        st.sidebar.info("📊 技術詳細表示 ON")

    # パフォーマンス制限設定
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ⚙️ パフォーマンス制限")
    default_max_records = PERFORMANCE_LIMITS["max_records"]
    default_max_months = PERFORMANCE_LIMITS["max_months"]

    previous_records = st.session_state.get('max_records', default_max_records)
    previous_months = st.session_state.get('max_months', default_max_months)

    max_records = int(
        st.sidebar.number_input(
            "最大表示件数",
            min_value=10,
            max_value=200,
            step=10,
            value=int(previous_records if 10 <= previous_records <= 200 else default_max_records),
            help="一覧で同時に表示するレコード件数の上限",
        )
    )
    max_months = int(
        st.sidebar.slider(
            "表示期間の上限（月）",
            min_value=1,
            max_value=24,
            value=int(previous_months if 1 <= previous_months <= 24 else default_max_months),
            help="最新から指定した月数までのデータを対象にします",
        )
    )

    st.sidebar.caption(
        f"デフォルト: {default_max_records}件 / 過去{default_max_months}ヶ月"
    )

    st.session_state['max_records'] = max_records
    st.session_state['max_months'] = max_months

    if max_records != previous_records or max_months != previous_months:
        log_dashboard_event(
            "performance_limits_update",
            max_records=max_records,
            max_months=max_months,
        )

    if st.sidebar.button("キャッシュをクリア", help="保存済みのデータキャッシュを手動で削除します"):
        cached_scan_results.clear()
        st.session_state.pop('cache_metadata', None)
        log_dashboard_event("cache_clear", scope="all")
        emit_ui_metric("cache_clear", environment=selected_env)
        st.sidebar.success("キャッシュをクリアしました")

    st.sidebar.markdown("---")
    debug_mode = st.sidebar.checkbox(
        "デバッグモード",
        value=st.session_state.get('debug_mode', False),
        help="オンにすると主要操作の実行時間を画面に表示します",
    )
    st.session_state['debug_mode'] = debug_mode
    if debug_mode:
        st.sidebar.info("⏱ 実行時間が画面下部に表示されます")

    st.sidebar.markdown("---")
    admin_mode = st.sidebar.checkbox(
        "管理者モード",
        value=st.session_state.get('admin_mode', False),
        help="接続ヘルス情報とエラーログを表示します",
    )
    st.session_state['admin_mode'] = admin_mode
    log_dashboard_event("admin_mode", enabled=admin_mode)

    if admin_mode:
        health_results = perform_health_checks(s3_client, dynamodb, resources, demo_mode)
        with st.sidebar.expander("システム状態", expanded=True):
            if not health_results:
                st.write("デモモードのためヘルスチェックはスキップされました")
            else:
                for result in health_results:
                    status_icon = "✅" if result['status'] == 'ok' else "⚠️"
                    label = result['name']
                    if result['status'] == 'ok':
                        st.write(f"{status_icon} {label} ({result.get('duration_ms', 0):.0f} ms)")
                    else:
                        st.write(f"{status_icon} {label}: {result.get('message', '詳細不明')}")

        mismatch_stats = st.session_state.get('version_mismatch_stats')
        if mismatch_stats and mismatch_stats.get('total'):
            mismatch_rate = mismatch_stats['mismatch'] / mismatch_stats['total'] * 100
            st.sidebar.info(
                f"バージョン不整合率: {mismatch_stats['mismatch']}/{mismatch_stats['total']} ({mismatch_rate:.1f}%)"
            )

        error_log = st.session_state.get('error_log', [])
        if error_log:
            with st.sidebar.expander("エラーログ (最新5件)"):
                for entry in error_log[-5:][::-1]:
                    st.write(f"{entry['timestamp']}\n{entry['context']}: {entry['error']}")

    # サイドバーでページ選択
    st.sidebar.markdown("---")

    # デバッグモード時はデバッグページを追加
    page_options = ["📤 動画アップロード", "📊 セッション一覧（560点満点）", "📋 評価結果一覧（種目別）", "🗑️ 未完了セッション管理"]
    if st.session_state.get('debug_mode'):
        page_options.append("🔧 デバッグ情報")

    page = st.sidebar.radio(
        "ページ選択",
        page_options
    )

    log_dashboard_event(
        "navigate",
        page=page,
        demo_mode=demo_mode,
        coach_mode=coach_mode,
    )

    # ページ表示
    if page == "📤 動画アップロード":
        with execution_timer("upload_page_render") as stats:
            upload_video_page(s3_client, resources, demo_mode)
        if st.session_state.get('debug_mode') and stats.duration_ms is not None:
            st.caption(f"⏱ アップロード画面処理時間: {stats.duration_ms:.0f} ms")
    elif page == "📊 セッション一覧（560点満点）":
        if 'selected_session' in st.session_state:
            selected = st.session_state['selected_session']
            with execution_timer(
                "session_detail_processing",
                athlete_id=selected.get('athlete_id'),
                session_id=selected.get('session_id'),
            ) as stats:
                session_detail_page(dynamodb, resources, demo_mode)
            if st.session_state.get('debug_mode') and stats.duration_ms is not None:
                st.caption(f"⏱ セッション詳細処理時間: {stats.duration_ms:.0f} ms")
        else:
            with execution_timer("session_list_processing") as stats:
                session_list_page(dynamodb, resources, demo_mode)
            if st.session_state.get('debug_mode') and stats.duration_ms is not None:
                st.caption(f"⏱ セッション一覧処理時間: {stats.duration_ms:.0f} ms")
    elif page == "📋 評価結果一覧（種目別）":
        with execution_timer("view_list_processing") as stats:
            results_list_page(dynamodb, resources, demo_mode, coach_mode)
        if st.session_state.get('debug_mode') and stats.duration_ms is not None:
            st.caption(f"⏱ 評価結果一覧処理時間: {stats.duration_ms:.0f} ms")
    elif page == "🗑️ 未完了セッション管理":
        with execution_timer("incomplete_sessions_management") as stats:
            incomplete_sessions_management_page(s3_client, dynamodb, resources, demo_mode)
        if st.session_state.get('debug_mode') and stats.duration_ms is not None:
            st.caption(f"⏱ 未完了セッション管理処理時間: {stats.duration_ms:.0f} ms")
    elif page == "🔧 デバッグ情報":
        with execution_timer("debug_info_page") as stats:
            debug_info_page(dynamodb, resources, demo_mode)
        if st.session_state.get('debug_mode') and stats.duration_ms is not None:
            st.caption(f"⏱ デバッグ情報処理時間: {stats.duration_ms:.0f} ms")


if __name__ == "__main__":
    main()
