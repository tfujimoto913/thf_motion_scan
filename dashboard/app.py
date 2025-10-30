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
from typing import Dict, List, Optional
import re

# dashboard/config.py, demo_data.py をインポート
sys.path.insert(0, str(Path(__file__).parent))
from config import get_resource_names, TEST_TYPES, TEST_TYPE_DISPLAY
from demo_data import get_demo_results


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
def get_aws_clients():
    """
    What: AWS クライアント初期化（S3, DynamoDB）
    Why: Streamlit再実行時の再初期化防止
    Design Decision: st.cache_resource でシングルトン化（ADR-014）

    CRITICAL: AWS認証情報は環境変数または~/.aws/credentialsから取得
    """
    s3_client = boto3.client('s3')
    dynamodb = boto3.resource('dynamodb')
    resources = get_resource_names()
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
        # アップロードボタン
        if st.button("アップロード開始", type="primary"):
            with st.spinner("アップロード中..."):
                # S3キー生成
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                s3_key = f"videos/{test_type}/{uploaded_file.name.replace('.mp4', '')}_{timestamp}.mp4"

                try:
                    # S3アップロード
                    s3_client.upload_fileobj(
                        uploaded_file,
                        resources['videos_bucket'],
                        s3_key
                    )

                    st.success(f"✅ アップロード成功: {s3_key}")
                    st.info("🎬 Lambda関数による処理が開始されました。結果は「評価結果一覧」ページで確認できます。")

                except Exception as e:
                    st.error(f"❌ アップロード失敗: {str(e)}")


def results_list_page(dynamodb, resources, demo_mode=False):
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
            st.error(f"❌ データ取得エラー: {str(e)}")
            return

    # 共通処理（デモモード・通常モード両対応）
    try:

        if not items:
            st.warning("評価結果がありません。動画をアップロードしてください。")
            return

        # DataFrame変換
        df = pd.DataFrame(items)

        # 列選択と並び替え
        display_columns = ['video_id', 'test_type', 'score', 'processed_at']
        df_display = df[display_columns].copy()

        # クライアントID表示用カラム追加
        df_display['client'] = df_display['video_id'].apply(format_client_id_display)

        df_display['processed_at'] = pd.to_datetime(df_display['processed_at'])
        df_display = df_display.sort_values('processed_at', ascending=False)

        # 表示用に列を並び替え（client, test_type, score, processed_at）
        df_display = df_display[['client', 'test_type', 'score', 'processed_at', 'video_id']]

        # テストタイプフィルタ
        test_filter = st.multiselect(
            "テストタイプでフィルタ",
            TEST_TYPES,
            default=TEST_TYPES
        )
        df_filtered = df_display[df_display['test_type'].isin(test_filter)]

        # テーブル表示（video_idカラムは非表示）
        st.dataframe(
            df_filtered[['client', 'test_type', 'score', 'processed_at']],
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
            show_result_detail(df, selected_video)

    except Exception as e:
        st.error(f"❌ データ処理エラー: {str(e)}")


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
    df_same_client['processed_at'] = pd.to_datetime(df_same_client['processed_at'])
    df_same_client = df_same_client.sort_values('processed_at', ascending=False)

    # 最新の過去データを返す
    return df_same_client.iloc[0].to_dict()


def show_result_detail(df: pd.DataFrame, video_id: str):
    """
    What: 詳細結果表示（v2.1: 80点満点対応版）
    Why: 選択された動画の評価結果詳細を表示
    Design Decision: v2.1システム（80点満点 = Section A 20点 + Section B 60点）

    CRITICAL: evaluation フィールドの構造に依存（v2.1形式）
    """
    # 該当行取得
    row = df[df['video_id'] == video_id].iloc[0]
    test_type = row['test_type']
    test_name = TEST_NAMES.get(test_type, test_type)

    # 種目名表示
    st.markdown(f"## {test_name}")
    st.markdown("---")

    # === 総合スコア（80点満点） ===
    # v2.1データ構造:
    # {
    #   'A_execution_score': 20点満点,
    #   'B_total': 60点満点,
    #   'B_principles': {'eccentric': {...}, 'concentric': {...}},
    #   'total_score': 80点満点
    # }

    if 'evaluation' in row and isinstance(row['evaluation'], dict):
        evaluation = row['evaluation']

        # v2.1データの場合
        if 'version' in evaluation and evaluation['version'] == 'v2.1':
            total_score = evaluation.get('total_score', 0.0)
            execution_score = evaluation.get('A_execution_score', 0.0)  # Section A: 20点
            principles_score = evaluation.get('B_total', 0.0)           # Section B: 60点
            max_score = 80.0
        # 旧v1データの場合（12点満点）
        else:
            execution_score = evaluation.get('execution', {}).get('total', 0.0)
            principles_score = evaluation.get('principles', {}).get('total', 0.0)
            total_score = execution_score + principles_score
            max_score = 12.0
    else:
        # デモデータ（3点満点を80点満点に換算）
        total_score = row['score'] * (80.0 / 3.0)
        execution_score = total_score * (20.0 / 80.0)  # 25%
        principles_score = total_score * (60.0 / 80.0)  # 75%
        max_score = 80.0

    percentage = (total_score / max_score) * 100

    # 色判定
    if percentage >= 80:
        color_emoji = "🟢"
        status_text = "優秀"
    elif percentage >= 60:
        color_emoji = "🟡"
        status_text = "良好"
    else:
        color_emoji = "🔴"
        status_text = "要改善"

    # スコア表示
    col1, col2, col3 = st.columns(3)
    with col1:
        if max_score == 80.0:
            st.metric("総合スコア", f"{total_score:.1f}/80", help="Section A(20点) + Section B(60点)")
        else:
            st.metric("総合スコア", f"{total_score:.1f}/{int(max_score)}", help="旧システム（12点満点）")
    with col2:
        st.metric("達成率", f"{percentage:.0f}%", help=f"総合スコア / {int(max_score)}点満点")
    with col3:
        st.metric("評価", f"{color_emoji} {status_text}")

    st.markdown("")
    if max_score == 80.0:
        st.write(f"📐 **Section A（実施可否）**: {execution_score:.1f}/20.0")
        st.write(f"🎯 **Section B（8原則）**: {principles_score:.1f}/60.0")
    else:
        st.write(f"📐 **完全性**: {execution_score:.1f}/3.0")
        st.write(f"🎯 **7原則**: {principles_score:.1f}/9.0")

    # === 評価される原則のみ表示 ===
    st.markdown("---")
    st.subheader("📊 評価原則の詳細")

    # v2.1の場合、B_principlesから原則別スコアを取得
    if 'evaluation' in row and isinstance(row['evaluation'], dict) and evaluation.get('version') == 'v2.1':
        b_principles = evaluation.get('B_principles', {})
        ecc_scores = b_principles.get('eccentric', {})
        con_scores = b_principles.get('concentric', {})

        # Eccentric局面
        if ecc_scores:
            st.write("### 下降局面（Eccentric）")
            for key, value in ecc_scores.items():
                # キー形式: "B1_core_stability" → "B1", "core_stability"
                if isinstance(value, (int, float)):
                    principle_num = key.split('_')[0].replace('B', '')
                    principle_full_name = key.replace(f'B{principle_num}_', '').replace('_', ' ').title()
                    warning = " ⚠️" if value < 2.0 else ""

                    # プログレスバー（最大値を15点と仮定、実際はmax_scoreが必要）
                    max_principle_score = 15.0  # Eccentric 30点を2原則で分割の場合
                    progress = min(value / max_principle_score, 1.0)

                    st.write(f"**B{principle_num} {principle_full_name}**: {value:.1f}点{warning}")
                    st.progress(progress)
                    st.write("")

        # Concentric局面
        if con_scores:
            st.write("### 上昇局面（Concentric）")
            for key, value in con_scores.items():
                if isinstance(value, (int, float)):
                    principle_num = key.split('_')[0].replace('B', '')
                    principle_full_name = key.replace(f'B{principle_num}_', '').replace('_', ' ').title()
                    warning = " ⚠️" if value < 2.0 else ""

                    max_principle_score = 15.0
                    progress = min(value / max_principle_score, 1.0)

                    st.write(f"**B{principle_num} {principle_full_name}**: {value:.1f}点{warning}")
                    st.progress(progress)
                    st.write("")

    else:
        # 旧システムまたはデモデータの場合
        principles_to_show = TEST_PRINCIPLES_MAP.get(test_type, [])

        if principles_to_show:
            st.write("")
            for principle_num in principles_to_show:
                # 仮実装: 各原則のスコアを均等配分
                if max_score == 80.0:
                    score = principles_score / len(principles_to_show)  # 60点を原則数で均等割り
                    max_principle_score = 60.0 / len(principles_to_show)
                else:
                    score = principles_score / len(principles_to_show)  # 9点を原則数で均等割り
                    max_principle_score = 9.0 / len(principles_to_show)

                principle_name = PRINCIPLE_NAMES.get(principle_num, f"P{principle_num}")
                warning = " ⚠️" if score < 2.0 else ""

                # プログレスバー表示
                progress = score / max_principle_score if max_principle_score > 0 else 0
                st.write(f"**P{principle_num} {principle_name}**: {score:.1f}/{max_principle_score:.1f}点{warning}")
                st.progress(progress)
                st.write("")
        else:
            st.info("この種目の評価原則マッピングが未定義です")

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
        # 2回目以降の表示
        # 前回スコア取得
        if 'evaluation' in previous and isinstance(previous['evaluation'], dict):
            prev_evaluation = previous['evaluation']

            # v2.1データの場合
            if 'version' in prev_evaluation and prev_evaluation['version'] == 'v2.1':
                prev_total = prev_evaluation.get('total_score', 0.0)
                prev_max_score = 80.0
            # 旧v1データの場合
            else:
                prev_execution = prev_evaluation.get('execution', {}).get('total', 0.0)
                prev_principles = prev_evaluation.get('principles', {}).get('total', 0.0)
                prev_total = prev_execution + prev_principles
                prev_max_score = 12.0
        else:
            # デモデータ（3点満点を80点満点に換算）
            prev_total = previous['score'] * (80.0 / 3.0)
            prev_max_score = 80.0

        curr_total = total_score
        diff = curr_total - prev_total

        # 異なるスコアシステム間の比較の場合、パーセンテージで比較
        if prev_max_score != max_score:
            prev_pct = (prev_total / prev_max_score) * 100
            curr_pct = (curr_total / max_score) * 100
            pct_diff = curr_pct - prev_pct
            use_percentage_only = True
        else:
            prev_pct = (prev_total / max_score) * 100
            curr_pct = percentage
            pct_diff = curr_pct - prev_pct
            use_percentage_only = False

        # 比較表示
        col1, col2 = st.columns(2)
        with col1:
            if use_percentage_only:
                st.metric("達成率（今回）", f"{curr_pct:.0f}%", f"{pct_diff:+.0f}%")
            else:
                st.metric("総合スコア", f"{curr_total:.1f}/{int(max_score)}", f"{diff:+.1f}")
        with col2:
            if use_percentage_only:
                st.info(f"前回システム: {int(prev_max_score)}点満点、今回: {int(max_score)}点満点")
            else:
                st.metric("達成率", f"{curr_pct:.0f}%", f"{pct_diff:+.0f}%")

        st.write("")

        # 改善・悪化判定（パーセンテージベース）
        if pct_diff > 5:
            st.success(f"✅ **{pct_diff:.1f}% 改善しました！**")
        elif pct_diff < -5:
            st.warning(f"⚠️ **{abs(pct_diff):.1f}% 低下しています**")
        else:
            st.info("📊 前回とほぼ同じ水準です")

        # 異なるシステム間の比較時の注意
        if use_percentage_only:
            st.caption("ℹ️ スコアシステムが異なるため、達成率での比較を表示しています")

    # === Health Check ===
    st.markdown("---")
    if 'health_check' in row and row['health_check']:
        with st.expander("🏥 Health Check"):
            health = row['health_check']

            if health.get('is_valid'):
                st.success("✅ データ品質: 良好")
            else:
                st.error("❌ データ品質: 問題あり")

            if 'detection_rate' in health:
                st.metric("検出率", f"{health['detection_rate']*100:.1f}%")

            if 'warnings' in health and health['warnings']:
                st.warning("⚠️ 警告:")
                for warning in health['warnings']:
                    st.write(f"- {warning}")

            st.json(health)

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

    # AWS クライアント初期化
    try:
        s3_client, dynamodb, resources = get_aws_clients()
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

    # サイドバーでページ選択
    st.sidebar.markdown("---")
    page = st.sidebar.radio(
        "ページ選択",
        ["📤 動画アップロード", "📊 評価結果一覧"]
    )

    # ページ表示
    if page == "📤 動画アップロード":
        upload_video_page(s3_client, resources, demo_mode)
    elif page == "📊 評価結果一覧":
        results_list_page(dynamodb, resources, demo_mode)


if __name__ == "__main__":
    main()
