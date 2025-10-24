# Lambda Container Image用のベースイメージ
FROM public.ecr.aws/lambda/python:3.11

# 作業ディレクトリ
WORKDIR /var/task

# システム依存ライブラリとビルドツールのインストール
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
CMD ["handler.lambda_handler"]
