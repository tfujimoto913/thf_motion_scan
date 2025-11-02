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

# requirements-lambda.txtをコピーして依存関係を/var/taskにインストール
# CRITICAL: Lambda必須依存のみ（streamlit等の開発ツール除外）
# CRITICAL: numpy<2.0を明示（GCC 7.3.1制約）
# CRITICAL: /var/taskにインストールすることで、MediaPipeモデルダウンロード先も書き込み可能に
COPY requirements-lambda.txt ./
RUN pip install --no-cache-dir --target /var/task -r requirements-lambda.txt

# MediaPipeモデルを手動ダウンロード
# CRITICAL: Lambda実行時は/var/taskが読み取り専用になるため、ビルド時にモデルを配置必須
# CRITICAL: pose_landmark_heavy.tflite (model_complexity=2, デフォルト)
ENV PYTHONPATH="/var/task:${PYTHONPATH}"
RUN mkdir -p /var/task/mediapipe/modules/pose_landmark && \
    curl -L -o /var/task/mediapipe/modules/pose_landmark/pose_landmark_heavy.tflite \
    https://storage.googleapis.com/mediapipe-assets/pose_landmark_heavy.tflite && \
    ls -lh /var/task/mediapipe/modules/pose_landmark/pose_landmark_heavy.tflite && \
    echo "✅ MediaPipeモデルダウンロード完了"

# アプリケーションコードをコピー
COPY config.json .
COPY processing/ ./processing/
COPY lambda/common/ ./common/
COPY src/handler.py ./

# Lambda関数ハンドラーを指定
# CRITICAL: handler.lambda_handlerは src/handler.py の lambda_handler関数を指す
CMD ["handler.lambda_handler"]
