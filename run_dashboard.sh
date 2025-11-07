#!/bin/bash
# Streamlit Dashboard起動スクリプト
# 仮想環境を明示的にアクティベートしてから起動

cd "$(dirname "$0")"
source .venv/bin/activate

# CRITICAL: 動画アップロード上限を500MBに設定
# Why: config.tomlに加えて環境変数でも明示（キャッシュ問題回避）
export STREAMLIT_SERVER_MAX_UPLOAD_SIZE=500

.venv/bin/streamlit run dashboard/app.py
