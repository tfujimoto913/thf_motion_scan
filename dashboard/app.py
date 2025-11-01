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
import streamlit as st
import boto3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

# dashboard/config.py, demo_data.py をインポート
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    DEFAULT_ENV,
    TEST_TYPES,
    TEST_TYPE_DISPLAY,
    get_available_environments,
    get_resource_names,
)
from demo_data import get_demo_results
from utils.video_validator import VideoValidator
from session_dao import group_tests_by_session, get_latest_sessions
from session_pages import session_list_page


# 種目名マッピング（内部コード→日本語名）
TEST_NAMES = {
    "single_leg_squat": "片脚スタンススクワット",
    "skater_lunge": "スケーターランジ",
    "stride_mimic": "スケートストライド模倣",
    "jump_landing": "ミニジャンプ＆着地",
    "upper_body_swing": "上体スイング",
    "push_pull": "プッシュプル動作",
    "cross_step": "クロスステップ模倣"
}

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

    return {
        'rules_version': rules_version,
        'scoring_version': scoring_version,
        'evaluation_version': evaluation_version,
        'mismatch': mismatch,
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
    What: 動画アップロードページ
    Why: S3 VideosBucketへの動画アップロード機能
    Design Decision: Streamlit file_uploader使用（ADR-014）

    Args:
        s3_client: S3クライアント
        resources: AWSリソース名
        demo_mode: デモモードフラグ

    CRITICAL: videos/{test_type}/ パス構造でアップロード
    """
    st.header("📤 動画アップロード")

    # デモモード時の表示
    if demo_mode:
        st.info("🎭 **デモモード**: 動画アップロードは無効です")
        st.success("✅ デモデータは「📊 評価結果一覧」ページで確認できます")
        st.markdown("---")
        st.markdown("""
        ### デモモードについて
        - AWS環境なしでUIを確認できます
        - サンプルデータ（5件）を表示します
        - 実際のアップロードを行うには、デモモードをOFFにしてください
        """)
        return

    if not resources:
        st.error("❌ AWS設定エラー: AccountIdが取得できません")
        return

    # テストタイプ選択
    test_type = st.selectbox(
        "テストタイプを選択",
        TEST_TYPES,
        format_func=lambda x: TEST_TYPE_DISPLAY.get(x, x)
    )

    # 動画ファイルアップロード
    uploaded_file = st.file_uploader(
        "動画ファイルを選択（MP4形式）",
        type=['mp4'],
        help="S3にアップロードされ、自動的に処理が開始されます"
    )

    if uploaded_file is not None:
        # セッション状態の初期化
        if 'validation_result' not in st.session_state:
            st.session_state.validation_result = None
        if 'validated_file' not in st.session_state:
            st.session_state.validated_file = None

        # バリデーションボタン
        if st.button("種目チェック（推奨）", type="secondary"):
            with st.spinner("動画を解析中... (10-30秒程度かかります)"):
                import tempfile
                import os

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
                st.session_state.validated_file = uploaded_file

                # 一時ファイル削除
                os.unlink(tmp_path)

        # バリデーション結果の表示
        if st.session_state.validation_result:
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

        # アップロードボタン（バリデーション結果に応じてラベル変更）
        if st.session_state.validation_result and not st.session_state.validation_result['is_valid']:
            upload_button_label = "⚠️ 無視してアップロード"
            upload_button_type = "secondary"
        else:
            upload_button_label = "アップロード開始"
            upload_button_type = "primary"

        if st.button(upload_button_label, type=upload_button_type):
            with st.spinner("アップロード中..."):
                # S3キー生成
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                s3_key = f"videos/{test_type}/{uploaded_file.name.replace('.mp4', '')}_{timestamp}.mp4"

                try:
                    # ファイルポインタをリセット
                    uploaded_file.seek(0)

                    # S3アップロード
                    s3_client.upload_fileobj(
                        uploaded_file,
                        resources['videos_bucket'],
                        s3_key
                    )

                    st.success(f"✅ アップロード成功: {s3_key}")
                    st.info("🎬 Lambda関数による処理が開始されました。結果は「評価結果一覧」ページで確認できます。")

                    # セッション状態クリア
                    st.session_state.validation_result = None
                    st.session_state.validated_file = None

                except Exception as e:
                    st.error("❌ アップロードに失敗しました")
                    st.caption("インターネット接続とAWS権限を確認し、再度お試しください")
                    with st.expander("技術情報 (サポート向け)"):
                        st.code(str(e))


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

    # デモモード時の表示
    if demo_mode:
        st.info("🎭 **デモモード**: サンプルデータを表示中")
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
        from decimal import Decimal

        def convert_decimals(obj):
            """DynamoDB Decimal型をfloatに再帰的に変換"""
            if isinstance(obj, list):
                return [convert_decimals(item) for item in obj]
            elif isinstance(obj, dict):
                return {key: convert_decimals(value) for key, value in obj.items()}
            elif isinstance(obj, Decimal):
                return float(obj)
            return obj

        # 全てのDecimal型をfloatに変換
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

        # 追加情報の抽出
        version_info_series = df.apply(lambda row: extract_version_info(row.to_dict()), axis=1)
        df['version_label'] = version_info_series.apply(format_version_label)
        df['version_warning'] = version_info_series.apply(
            lambda info: "⚠️ バージョン不整合" if info.get('mismatch') else ""
        )
        df['client_display'] = df['video_id'].apply(format_client_id_display)

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
            show_result_detail(df, selected_video, coach_mode)

    except Exception as e:
        st.error("❌ 評価結果の表示中に予期せぬエラーが発生しました")
        st.caption("時間をおいて再度アクセスするか、サポートチームへご連絡ください")
        with st.expander("技術情報 (サポート向け)"):
            st.code(str(e))


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
    test_name = TEST_NAMES.get(test_type, test_type)

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
        prev_summary = summarize_scores(previous)
        prev_total = prev_summary.get('total_score')
        prev_max_score = prev_summary.get('max_score')

        if percentage is None or total_score is None or not max_score:
            st.info("今回のスコアが確定していないため、比較は表示されません")
        elif not prev_summary['available'] or prev_total is None or not prev_max_score:
            st.warning("前回スコアが未取得のため比較できません")
            if prev_summary.get('message'):
                st.caption(f"ℹ️ {prev_summary['message']}")
        else:
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

    # ヘッダーリンク無効化CSS
    st.markdown("""
    <style>
    .stMarkdown h1 a, .stMarkdown h2 a, .stMarkdown h3 a {
        display: none;
    }
    </style>
    """, unsafe_allow_html=True)

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

    # AWS クライアント初期化
    try:
        s3_client, dynamodb, resources = get_aws_clients(selected_env)
    except Exception as e:
        st.error(f"❌ AWS接続エラー: {str(e)}")
        st.info("AWS認証情報を確認してください（~/.aws/credentials または環境変数）")
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
    else:
        # AWS Account ID表示
        if resources:
            st.sidebar.success(f"✅ AWS Account: {resources['account_id']}")
            st.sidebar.info(f"🏗️ 使用中の環境: {resources['environment']}")

    # コーチモードチェックボックス（Phase 2.5a）
    st.sidebar.markdown("---")
    coach_mode = st.sidebar.checkbox(
        "🎓 コーチモード",
        value=False,
        help="技術詳細情報（測定値、閾値、減点内訳）を表示します"
    )

    if coach_mode:
        st.sidebar.info("📊 技術詳細表示 ON")

    # サイドバーでページ選択
    st.sidebar.markdown("---")
    page = st.sidebar.radio(
        "ページ選択",
        ["📤 動画アップロード", "📊 セッション一覧（560点満点）", "📋 評価結果一覧（種目別）"]
    )

    # ページ表示
    if page == "📤 動画アップロード":
        upload_video_page(s3_client, resources, demo_mode)
    elif page == "📊 セッション一覧（560点満点）":
        session_list_page(dynamodb, resources, demo_mode)
    elif page == "📋 評価結果一覧（種目別）":
        results_list_page(dynamodb, resources, demo_mode, coach_mode)


if __name__ == "__main__":
    main()
