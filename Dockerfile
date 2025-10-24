# ==============================================================================
# THF Motion Scan - Lambda Container Image
# Purpose: MediaPipe + OpenCVをLambda環境で実行するためのコンテナイメージ
# Architecture: linux/amd64 (Lambda requirement, ADR-009)
# Decision Log: ADR-007, ADR-009
#
# CRITICAL:
#   - --platform linux/amd64 必須（arm64では動作しない）
#   - mesa-libGL必須（OpenCV GUI依存解決）
#   - opencv-python-headless使用（requirements.txt）
#   - ビルドコマンド: docker buildx build --platform linux/amd64 --provenance=false --sbom=false -t <tag> .
# ==============================================================================

# Lambda Container Image用のベースイメージ
FROM public.ecr.aws/lambda/python:3.11

# 作業ディレクトリ
WORKDIR /var/task

# システム依存ライブラリとビルドツールのインストール
# mesa-libGL: OpenCVのGUI依存解決（ヘッドレス環境でも必要）
# gcc/gcc-c++/make: MediaPipeのネイティブ拡張ビルド用
RUN yum install -y \
    mesa-libGL \
    gcc \
    gcc-c++ \
    make \
    && yum clean all

# requirements.txtをコピーして依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY config.json .
COPY processing/ ./processing/
COPY src/handler.py ./

# Lambda関数ハンドラーを指定
# CRITICAL: handler.lambda_handlerは src/handler.py の lambda_handler関数を指す
CMD ["handler.lambda_handler"]
