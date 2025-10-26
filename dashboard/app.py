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

# dashboard/config.py をインポート
sys.path.insert(0, str(Path(__file__).parent))
from config import get_resource_names, TEST_TYPES, TEST_TYPE_DISPLAY

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


def upload_video_page(s3_client, resources):
    """
    What: 動画アップロードページ
    Why: S3 VideosBucketへの動画アップロード機能
    Design Decision: Streamlit file_uploader使用（ADR-014）

    CRITICAL: videos/{test_type}/ パス構造でアップロード
    """
    st.header("📤 動画アップロード")

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


def results_list_page(dynamodb, resources):
    """
    What: 評価結果一覧ページ
    Why: DynamoDBから評価結果を取得して一覧表示
    Design Decision: pandas DataFrameで表形式表示（ADR-014）

    CRITICAL: DynamoDB Scanは項目数が多い場合にコスト増加
    """
    st.header("📊 評価結果一覧")

    if not resources:
        st.error("❌ AWS設定エラー: AccountIdが取得できません")
        return

    try:
        table = dynamodb.Table(resources['table_name'])
        response = table.scan()
        items = response['Items']

        if not items:
            st.warning("評価結果がありません。動画をアップロードしてください。")
            return

        # DataFrame変換
        df = pd.DataFrame(items)

        # 列選択と並び替え
        display_columns = ['video_id', 'test_type', 'score', 'processed_at']
        df_display = df[display_columns].copy()
        df_display['processed_at'] = pd.to_datetime(df_display['processed_at'])
        df_display = df_display.sort_values('processed_at', ascending=False)

        # テストタイプフィルタ
        test_filter = st.multiselect(
            "テストタイプでフィルタ",
            TEST_TYPES,
            default=TEST_TYPES
        )
        df_filtered = df_display[df_display['test_type'].isin(test_filter)]

        # テーブル表示
        st.dataframe(
            df_filtered,
            use_container_width=True,
            hide_index=True
        )

        # 詳細表示用の選択
        st.subheader("詳細結果")
        selected_video = st.selectbox(
            "動画を選択",
            df_filtered['video_id'].tolist()
        )

        if selected_video:
            show_result_detail(df, selected_video)

    except Exception as e:
        st.error(f"❌ データ取得エラー: {str(e)}")


def show_result_detail(df: pd.DataFrame, video_id: str):
    """
    What: 詳細結果表示
    Why: 選択された動画の評価結果詳細を表示
    Design Decision: Plotlyでスコアグラフ化（ADR-014）

    CRITICAL: evaluation フィールドの構造に依存
    """
    # 該当行取得
    row = df[df['video_id'] == video_id].iloc[0]

    # 基本情報
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("総合スコア", f"{row['score']:.1f} / 3.0")
    with col2:
        st.metric("テストタイプ", row['test_type'].replace('_', ' ').title())
    with col3:
        st.metric("処理日時", row['processed_at'])

    # Health Check
    if 'health_check' in row:
        with st.expander("🏥 Health Check"):
            st.json(row['health_check'])

    # 評価詳細（モックデータ - 実際のDynamoDB構造に合わせて調整必要）
    st.subheader("📈 評価詳細")

    # グラフ表示（例: 各メトリックのスコア）
    # PHASE CORE LOGIC: 実際のevaluationフィールド構造に依存
    # TODO: DynamoDBの実データ構造に合わせて調整

    st.info("💡 実際のDynamoDBデータ構造に合わせてグラフ実装が必要です")

    # JSON表示
    with st.expander("🔍 JSON詳細"):
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

    # AWS Account ID表示
    if resources:
        st.sidebar.success(f"✅ AWS Account: {resources['account_id']}")

    # サイドバーでページ選択
    page = st.sidebar.radio(
        "ページ選択",
        ["📤 動画アップロード", "📊 評価結果一覧"]
    )

    # ページ表示
    if page == "📤 動画アップロード":
        upload_video_page(s3_client, resources)
    elif page == "📊 評価結果一覧":
        results_list_page(dynamodb, resources)


if __name__ == "__main__":
    main()
