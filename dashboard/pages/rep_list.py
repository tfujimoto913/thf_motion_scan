"""
Purpose: Rep一覧ページ（Streamlit UI）
Responsibility: Rep一覧取得、詳細表示、画像表示
Dependencies: streamlit, boto3, requests
Created: 2025-11-06 by Claude Code
Decision Log: Stage 5 - Streamlit Repタブ実装

CRITICAL:
- GET /reps API連携
- 署名URL生成（boto3.generate_presigned_url）
- 画像表示フォールバック
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import boto3
import requests
import streamlit as st


def get_api_gateway_url() -> str:
    """
    What: API GatewayのベースURL取得
    Why: 環境ごとにエンドポイントが異なるため

    Design Decision:
    - 環境変数優先、デフォルトはlocal
    - 本番環境では CloudFormation Output から取得

    CRITICAL: 環境変数 API_GATEWAY_URL が必須
    """
    return os.environ.get("API_GATEWAY_URL", "http://localhost:3000")


def generate_presigned_url(
    bucket: str, key: str, expiration: int = 300
) -> Optional[str]:
    """
    What: S3オブジェクトの署名URL生成
    Why: overlay.pngへのアクセス権限を一時的に付与

    Design Decision:
    - ExpiresIn=300秒（5分）
    - エラー時はNoneを返し、フォールバック表示

    CRITICAL: S3アクセス権限が必要（GetObject）
    """
    try:
        s3_client = boto3.client("s3")
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiration,
        )
        return url
    except Exception as e:
        st.error(f"署名URL生成失敗: {e}")
        return None


def fetch_reps(
    player_id: str,
    test_type: str,
    token: str,
    limit: int = 20,
    cursor: Optional[str] = None,
) -> Dict[str, Any]:
    """
    What: GET /reps API呼び出し
    Why: DynamoDBからRep一覧を取得

    Design Decision:
    - JWT Bearer認証
    - カーソルベースページング
    - エラー時は空リストを返す

    CRITICAL: JWT認証が必須
    """
    base_url = get_api_gateway_url()
    params = {
        "player_id": player_id,
        "test_type": test_type,
        "limit": limit,
    }
    if cursor:
        params["cursor"] = cursor

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{base_url}/reps",
            params=params,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"API呼び出し失敗: {e}")
        return {"items": [], "nextCursor": None}


def render_rep_list_page() -> None:
    """
    What: Rep一覧ページのレンダリング
    Why: ユーザーがRep一覧を閲覧・詳細確認

    Design Decision:
    - 最小導線: 一覧表示 → 詳細表示（画像 + メトリクス）
    - 画像表示失敗時はフォールバック

    CRITICAL: JWT認証トークンが必要（session_state経由）
    """
    st.title("🎯 Rep一覧")

    # Step 1: 開発用スタブ（JWT未実装時）
    st.warning("⚠️ 開発中: JWT認証未実装のため、スタブデータを表示")

    # 入力フォーム
    st.markdown("### 🔍 検索条件")
    col1, col2 = st.columns(2)
    with col1:
        player_id = st.text_input(
            "Player ID",
            value="plr_sakae_19",
            help="選手IDを入力（例: plr_sakae_19）",
        )
    with col2:
        test_type = st.selectbox(
            "Test Type",
            [
                "single_leg_squat",
                "skater_lunge",
                "stride_mimic",
                "jump_landing",
                "upper_body_swing",
                "push_pull",
                "cross_step",
            ],
            help="種目を選択",
        )

    # 検索ボタン
    if st.button("🔍 検索", type="primary"):
        # TODO: JWT認証実装後に有効化
        # token = st.session_state.get("jwt_token")
        # if not token:
        #     st.error("認証が必要です")
        #     return

        # スタブデータ表示
        st.markdown("---")
        st.markdown("### 📊 検索結果")

        # スタブレコード
        stub_data = [
            {
                "rep_id": "session123-001",
                "session_id": "session123",
                "test_type": "single_leg_squat",
                "score_primary": 85.5,
                "start_frame": 10,
                "end_frame": 50,
                "overlay_key": "team/player/test/session/reps/session123-001/overlay.png",
            },
            {
                "rep_id": "session123-002",
                "session_id": "session123",
                "test_type": "single_leg_squat",
                "score_primary": 78.3,
                "start_frame": 60,
                "end_frame": 100,
                "overlay_key": "team/player/test/session/reps/session123-002/overlay.png",
            },
        ]

        if not stub_data:
            st.info("結果が見つかりませんでした")
            return

        # 一覧表示
        st.info(f"✅ {len(stub_data)}件のRepが見つかりました")

        for idx, rep in enumerate(stub_data):
            with st.expander(
                f"**Rep #{idx + 1}** - {rep['rep_id']} (スコア: {rep['score_primary']:.1f})",
                expanded=(idx == 0),
            ):
                col_info, col_img = st.columns([1, 1])

                with col_info:
                    st.markdown("#### 📋 基本情報")
                    st.metric("スコア", f"{rep['score_primary']:.1f}")
                    st.caption(f"**Session ID**: {rep['session_id']}")
                    st.caption(f"**Rep ID**: {rep['rep_id']}")
                    st.caption(f"**Test Type**: {rep['test_type']}")
                    st.caption(f"**フレーム範囲**: {rep['start_frame']} - {rep['end_frame']}")

                with col_img:
                    st.markdown("#### 🖼️ Overlay画像")

                    # TODO: 署名URL生成実装後に有効化
                    # signed_url = generate_presigned_url(
                    #     bucket="your-results-bucket",
                    #     key=rep["overlay_key"],
                    # )
                    # if signed_url:
                    #     st.image(signed_url, caption=rep["rep_id"])
                    # else:
                    #     st.warning("画像の読み込みに失敗しました")

                    st.info("🚧 画像表示は署名URL実装後に有効化")
                    st.caption(f"**S3 Key**: {rep['overlay_key']}")


__all__ = ["render_rep_list_page"]
