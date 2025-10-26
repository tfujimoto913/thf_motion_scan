#!/bin/bash
# Streamlit Dashboard起動スクリプト
# 仮想環境を明示的にアクティベートしてから起動

cd "$(dirname "$0")"
source .venv/bin/activate
.venv/bin/streamlit run dashboard/app.py
