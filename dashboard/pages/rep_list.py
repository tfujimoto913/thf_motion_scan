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
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import requests
import streamlit as st

# dashboard/config.py をインポート
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_resource_names


def get_api_gateway_url() -> str:
    """
    What: API GatewayのベースURL取得
    Why: 環境ごとにエンドポイントが異なるため

    Design Decision:
    - 環境変数優先、デフォルトはconfig.py
    - 本番環境では CloudFormation Output から取得

    CRITICAL: 環境変数 API_GATEWAY_URL が必須
    """
    # 環境変数優先
    if url := os.environ.get("API_GATEWAY_URL"):
        return url

    # config.pyからの取得（フォールバック）
    resources = get_resource_names()
    if resources and "api_endpoint" in resources:
        return resources["api_endpoint"]

    return "http://localhost:3000"


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
        st.warning(f"⚠️ 署名URL生成失敗: {e}")
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
        data = response.json()

        # API応答チェック
        if not data.get("success", True):
            st.error(f"API エラー: {data.get('message', '不明なエラー')}")
            return {"items": [], "nextCursor": None}

        return data
    except requests.RequestException as e:
        st.error(f"❌ API呼び出し失敗: {e}")
        return {"items": [], "nextCursor": None}


def render_rep_image(rep: Dict[str, Any], bucket: str) -> None:
    """
    What: Rep overlay画像の表示（フォールバック付き）
    Why: 画像表示失敗時の再試行機能

    Design Decision:
    - 署名URL有効期限5分
    - 失敗時は再試行ボタン表示
    - プレースホルダー表示
    """
    overlay_key = rep.get("overlay_key")

    if not overlay_key:
        st.info("🖼️ 画像が登録されていません")
        return

    # 再試行ボタン用のsession_state管理
    retry_key = f"retry_{rep['rep_id']}"
    if retry_key not in st.session_state:
        st.session_state[retry_key] = 0

    signed_url = generate_presigned_url(bucket, overlay_key)

    if signed_url:
        try:
            st.image(signed_url, caption=rep["rep_id"], use_container_width=True)
        except Exception as e:
            st.warning(f"⚠️ 画像表示失敗: {e}")
            if st.button(f"🔄 再試行", key=f"retry_btn_{rep['rep_id']}"):
                st.session_state[retry_key] += 1
                st.rerun()
    else:
        st.warning("⚠️ 画像の読み込みに失敗しました")
        if st.button(f"🔄 再試行", key=f"retry_btn_{rep['rep_id']}"):
            st.session_state[retry_key] += 1
            st.rerun()
        st.caption(f"**S3 Key**: {overlay_key}")


def generate_dev_token(player_id: str, team_id: str = "tm_dev") -> str:
    """
    What: 開発用JWT生成
    Why: 認証レイヤー未実装時のテスト用

    Design Decision:
    - JWT_SECRET_KEYを環境変数から取得
    - 有効期限60分

    CRITICAL: 本番環境では使用禁止
    """
    import jwt
    from datetime import datetime, timedelta

    secret = os.environ.get("JWT_SECRET_KEY", "dev-secret-key")

    payload = {
        "playerId": player_id,
        "teamId": team_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(minutes=60),
    }

    return jwt.encode(payload, secret, algorithm="HS256")


def render_rep_list_page() -> None:
    """
    What: Rep一覧ページのレンダリング
    Why: ユーザーがRep一覧を閲覧・詳細確認

    Design Decision:
    - 最小導線: 一覧表示 → 詳細表示（画像 + メトリクス）
    - 画像表示失敗時はフォールバック
    - 開発用JWT生成（認証レイヤー未実装時）

    CRITICAL: 本番環境では適切な認証実装が必須
    """
    st.title("🎯 Rep一覧")

    # リソース名取得
    resources = get_resource_names()
    if not resources:
        st.error("❌ AWS リソースの取得に失敗しました。認証情報を確認してください。")
        return

    results_bucket = resources.get("results_bucket")

    # 開発モード警告
    dev_mode = st.sidebar.checkbox(
        "🔧 開発モード",
        value=True,
        help="開発モード: JWT自動生成（本番環境では使用禁止）"
    )

    if dev_mode:
        st.warning("⚠️ 開発モード: JWT自動生成中（本番環境では認証レイヤーを実装してください）")

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
        # JWT取得（開発モード時は自動生成）
        if dev_mode:
            token = generate_dev_token(player_id)
        else:
            token = st.session_state.get("jwt_token")
            if not token:
                st.error("❌ 認証が必要です。ログインしてください。")
                return

        # API呼び出し
        with st.spinner("🔄 Reps取得中..."):
            data = fetch_reps(player_id, test_type, token, limit=20)

        st.markdown("---")
        st.markdown("### 📊 検索結果")

        items = data.get("items", [])

        if not items:
            st.info("📭 結果が見つかりませんでした")
            return

        # 一覧表示
        st.info(f"✅ {len(items)}件のRepが見つかりました")

        for idx, rep in enumerate(items):
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

                    # 追加メトリクス
                    if apex_frame := rep.get("apex_frame"):
                        st.caption(f"**Apex Frame**: {apex_frame}")

                with col_img:
                    st.markdown("#### 🖼️ Overlay画像")
                    render_rep_image(rep, results_bucket)


__all__ = ["render_rep_list_page"]
