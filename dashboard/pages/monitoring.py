"""
Purpose: DLQ監視UI（Streamlit multi-page）
Responsibility:
  - DeadLetterQueueからの失敗タスク取得
  - エラー詳細表示
  - リトライ機能（Phase 5 - Stage 1）
Dependencies: streamlit, boto3
Created: 2025-10-31 by Claude
Decision Log: Phase 5 - Stage 1（運用監視基盤）

CRITICAL: AWS認証情報は環境変数または~/.aws/credentialsから取得
"""
import streamlit as st
import boto3
import json
from datetime import datetime
from typing import List, Dict, Optional
import sys
from pathlib import Path

# dashboard/config.py をインポート
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_aws_account_id

# AWS クライアント初期化
@st.cache_resource
def get_sqs_client():
    """
    What: SQS クライアント初期化
    Why: DLQメッセージ取得に使用
    Design Decision: st.cache_resource でシングルトン化

    CRITICAL: AWS認証情報は環境変数または~/.aws/credentialsから取得
    """
    return boto3.client('sqs')


def get_dlq_url() -> Optional[str]:
    """
    What: DLQ URL取得
    Why: SQS操作に必要
    Design Decision: AccountId から動的生成

    Returns:
        str: DLQ URL or None

    CRITICAL: AccountId取得失敗時はNoneを返す
    """
    account_id = get_aws_account_id()
    if not account_id:
        return None

    # DLQ名は template.yaml の QueueName: thf-motion-scan-dlq に対応
    region = boto3.Session().region_name or 'us-east-1'
    return f"https://sqs.{region}.amazonaws.com/{account_id}/thf-motion-scan-dlq"


def get_processing_queue_url() -> Optional[str]:
    """
    What: ProcessingQueue URL取得
    Why: リトライ時のメッセージ送信先
    Design Decision: AccountId から動的生成

    Returns:
        str: ProcessingQueue URL or None

    CRITICAL: AccountId取得失敗時はNoneを返す
    """
    account_id = get_aws_account_id()
    if not account_id:
        return None

    # Queue名は template.yaml の QueueName: thf-motion-scan-processing-queue に対応
    region = boto3.Session().region_name or 'us-east-1'
    return f"https://sqs.{region}.amazonaws.com/{account_id}/thf-motion-scan-processing-queue"


def get_dlq_messages(sqs_client, dlq_url: str, max_messages: int = 10) -> List[Dict]:
    """
    What: DLQからメッセージ取得
    Why: 失敗タスク一覧表示
    Design Decision: ReceiveMessage API使用（最大10件）

    Args:
        sqs_client: SQS client
        dlq_url: DLQ URL
        max_messages: 取得する最大メッセージ数

    Returns:
        List[Dict]: メッセージリスト

    CRITICAL: VisibilityTimeout設定でメッセージを一時的に非表示
    """
    try:
        response = sqs_client.receive_message(
            QueueUrl=dlq_url,
            MaxNumberOfMessages=max_messages,
            VisibilityTimeout=30,  # 30秒間非表示（処理中）
            WaitTimeSeconds=1  # Long polling
        )

        return response.get('Messages', [])

    except Exception as e:
        st.error(f"❌ DLQメッセージ取得エラー: {str(e)}")
        return []


def parse_message_body(body: str) -> Optional[Dict]:
    """
    What: メッセージボディのパース
    Why: S3イベント通知構造の解析
    Design Decision: JSON → S3イベント → Records[0]

    Args:
        body: メッセージボディ（JSON文字列）

    Returns:
        Dict: パース済みメッセージ or None

    CRITICAL: S3イベント通知は Records 配列に包まれている
    """
    try:
        data = json.loads(body)

        # S3イベント通知の場合
        if 'Records' in data and len(data['Records']) > 0:
            record = data['Records'][0]

            # S3バケット・キー情報抽出
            s3_info = record.get('s3', {})
            bucket = s3_info.get('bucket', {}).get('name', 'N/A')
            key = s3_info.get('object', {}).get('key', 'N/A')

            return {
                'bucket': bucket,
                'key': key,
                'event_time': record.get('eventTime', 'N/A'),
                'event_name': record.get('eventName', 'N/A'),
                'raw_body': body
            }

        # その他のメッセージ形式
        return {
            'raw_body': body
        }

    except Exception as e:
        return {
            'parse_error': str(e),
            'raw_body': body
        }


def retry_message(sqs_client, dlq_url: str, processing_queue_url: str,
                  receipt_handle: str, message_body: str) -> bool:
    """
    What: DLQメッセージをProcessingQueueに再送信
    Why: 失敗タスクのリトライ機能
    Design Decision: Delete from DLQ → Send to ProcessingQueue

    Args:
        sqs_client: SQS client
        dlq_url: DLQ URL
        processing_queue_url: ProcessingQueue URL
        receipt_handle: メッセージのReceiptHandle
        message_body: メッセージボディ

    Returns:
        bool: リトライ成功/失敗

    CRITICAL: DLQから削除してからProcessingQueueに送信
    """
    try:
        # ProcessingQueueに送信
        sqs_client.send_message(
            QueueUrl=processing_queue_url,
            MessageBody=message_body
        )

        # DLQから削除
        sqs_client.delete_message(
            QueueUrl=dlq_url,
            ReceiptHandle=receipt_handle
        )

        return True

    except Exception as e:
        st.error(f"❌ リトライ失敗: {str(e)}")
        return False


def main():
    """
    What: DLQ監視UIのメインエントリーポイント
    Why: 失敗タスクの可視化とリトライ機能
    Design Decision: Streamlit multi-page

    CRITICAL: AWS認証情報が設定されていることを前提
    """
    st.set_page_config(
        page_title="DLQ Monitoring - THF Motion Scan",
        page_icon="🚨",
        layout="wide"
    )

    st.title("🚨 Dead Letter Queue (DLQ) 監視")
    st.markdown("---")

    # AWS クライアント初期化
    try:
        sqs_client = get_sqs_client()
        dlq_url = get_dlq_url()
        processing_queue_url = get_processing_queue_url()

        if not dlq_url:
            st.error("❌ AWS設定エラー: AccountIdが取得できません")
            st.info("AWS認証情報を確認してください（~/.aws/credentials または環境変数）")
            return

    except Exception as e:
        st.error(f"❌ AWS接続エラー: {str(e)}")
        return

    # DLQメッセージ取得
    st.subheader("📋 失敗タスク一覧")

    # 更新ボタン
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🔄 更新", type="primary"):
            st.rerun()

    with st.spinner("DLQメッセージを取得中..."):
        messages = get_dlq_messages(sqs_client, dlq_url)

    if not messages:
        st.success("✅ DLQにメッセージはありません（全タスクが正常に処理されています）")
        return

    # 警告表示
    st.warning(f"⚠️ {len(messages)}件の失敗タスクがあります")

    # メッセージ一覧表示
    for idx, message in enumerate(messages):
        receipt_handle = message.get('ReceiptHandle')
        body = message.get('Body', '')

        # メッセージボディをパース
        parsed = parse_message_body(body)

        # Expander で個別表示
        with st.expander(f"❌ タスク #{idx + 1}: {parsed.get('key', 'Unknown')}"):
            # 基本情報
            if 'bucket' in parsed:
                st.write(f"**S3バケット**: {parsed['bucket']}")
                st.write(f"**S3キー**: {parsed['key']}")
                st.write(f"**イベント時刻**: {parsed['event_time']}")
                st.write(f"**イベント名**: {parsed['event_name']}")

            # エラー情報（あれば）
            if 'parse_error' in parsed:
                st.error(f"**パースエラー**: {parsed['parse_error']}")

            # Raw Body（デバッグ用）
            with st.expander("🔍 Raw Message Body"):
                st.code(parsed.get('raw_body', ''), language='json')

            # リトライボタン
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button(f"🔄 リトライ", key=f"retry_{idx}"):
                    with st.spinner("リトライ中..."):
                        success = retry_message(
                            sqs_client,
                            dlq_url,
                            processing_queue_url,
                            receipt_handle,
                            body
                        )

                    if success:
                        st.success("✅ リトライに成功しました。ProcessingQueueに再送信されました。")
                        st.rerun()
                    else:
                        st.error("❌ リトライに失敗しました")

    st.markdown("---")
    st.info("""
    ### 📘 使い方
    - **🔄 更新**: 最新のDLQメッセージを取得します
    - **🔄 リトライ**: 失敗タスクをProcessingQueueに再送信し、再処理を試みます
    - **Raw Message Body**: S3イベント通知の詳細を確認できます

    ### ⚠️ 注意事項
    - リトライしても再度失敗する場合は、Lambda関数のログを確認してください
    - DLQメッセージは14日間保持されます
    """)


if __name__ == "__main__":
    main()
