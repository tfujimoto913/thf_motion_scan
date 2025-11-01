"""
Purpose: S3イベントをトリガーにした動画処理のLambdaエントリーポイント
Responsibility:
  - S3/SQSイベントの受信とパース
  - 動画ダウンロードと一時ファイル管理
  - VideoProcessingWorkerの実行
  - 結果のS3保存とDynamoDB記録
Dependencies: processing.worker, boto3, config.json
Created: 2025-10-24 by Claude
Decision Log: ADR-007, ADR-008

CRITICAL:
  - 環境変数RESULTS_BUCKET, TABLE_NAME必須
  - 一時ファイルのクリーンアップ必須（os.unlink）
  - DynamoDB TTL設定（90日）必須
  - S3イベントとSQSイベント両対応
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any
from decimal import Decimal
import boto3
from urllib.parse import unquote_plus

# processingモジュールをインポート
sys.path.append('/var/task')
from processing.worker import VideoProcessingWorker
from processing.logger import log_info, log_warning, log_error

# AWS クライアント初期化
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')
dynamodb = boto3.resource('dynamodb')

# 環境変数
RESULTS_BUCKET = os.environ.get('RESULTS_BUCKET', 'thf-motion-scan-results')
QUEUE_URL = os.environ.get('QUEUE_URL', '')
TABLE_NAME = os.environ.get('TABLE_NAME', 'thf-motion-scan-results')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のメインハンドラー
    
    Args:
        event: S3イベントまたはSQSメッセージ
        context: Lambdaコンテキスト
        
    Returns:
        Dict: 処理結果
    """
    log_info("Event received", context={"event": event})

    try:
        # S3イベントからバケット名とキーを取得
        if 'Records' in event:
            # S3またはSQS経由
            record = event['Records'][0]

            if 'eventSource' in record and record['eventSource'] == 'aws:s3':
                # S3ダイレクト
                bucket = record['s3']['bucket']['name']
                key = unquote_plus(record['s3']['object']['key'])
            elif 'body' in record:
                # SQS経由のS3イベント（直接）
                body = json.loads(record['body'])
                # bodyに直接S3イベント構造が含まれている
                s3_record = body['Records'][0]
                bucket = s3_record['s3']['bucket']['name']
                key = unquote_plus(s3_record['s3']['object']['key'])
            else:
                raise ValueError("未知のイベントフォーマット")

        else:
            raise ValueError("イベントにRecordsが含まれていません")

        # テストタイプをキーから抽出（例: videos/single_leg_squat/xxx.mp4）
        test_type = extract_test_type(key)

        # S3オブジェクトのメタデータからathlete_id, session_idを取得
        try:
            obj_metadata = s3_client.head_object(Bucket=bucket, Key=key)
            metadata = obj_metadata.get('Metadata', {})
            athlete_id = metadata.get('athlete-id', None)
            session_id = metadata.get('session-id', None)
        except Exception as e:
            log_warning(
                "Failed to retrieve S3 object metadata",
                test_type=test_type,
                context={"error": str(e)}
            )
            athlete_id = None
            session_id = None

        log_info(
            "Processing target identified",
            test_type=test_type,
            context={
                "bucket": bucket,
                "key": key,
                "athlete_id": athlete_id,
                "session_id": session_id
            }
        )
        
        # 動画をダウンロード
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            video_path = tmp_file.name
            log_info(
                "Downloading video from S3",
                test_type=test_type,
                context={"key": key}
            )
            s3_client.download_file(bucket, key, video_path)

        # 動画処理
        worker = VideoProcessingWorker('/var/task/config.json')

        log_info(
            "Video processing started",
            test_type=test_type,
            context={
                "scoring_version": worker.scoring_version,
                "validation_mode": worker.validation_mode
            }
        )

        result = worker.process_video(video_path, test_type=test_type)

        # 一時ファイル削除
        os.unlink(video_path)

        # 結果をS3に保存
        result_key = save_results_to_s3(result, key)
        log_info(
            "Results saved to S3",
            test_type=test_type,
            context={"result_key": result_key, "bucket": RESULTS_BUCKET}
        )

        # DynamoDBに記録
        save_to_dynamodb(result, bucket, key, result_key, athlete_id, session_id)
        log_info(
            "Results saved to DynamoDB",
            test_type=test_type,
            context={"table_name": TABLE_NAME}
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': '処理成功',
                'video_key': key,
                'result_key': result_key,
                'score': result['score']
            })
        }
        
    except Exception as e:
        # エラーコンテキスト情報を含むログ出力
        error_context = {
            "bucket": bucket if 'bucket' in locals() else None,
            "key": key if 'key' in locals() else None,
            "test_type": test_type if 'test_type' in locals() else None
        }

        log_error(
            "Lambda function execution failed",
            video_id=key if 'key' in locals() else None,
            test_type=test_type if 'test_type' in locals() else None,
            context=error_context,
            exc_info=e
        )

        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'エラー発生',
                'error': str(e)
            })
        }


def extract_test_type(s3_key: str) -> str:
    """
    S3キーからテストタイプを抽出
    
    例: videos/single_leg_squat/video.mp4 → single_leg_squat
    """
    parts = s3_key.split('/')
    if len(parts) >= 2:
        return parts[1]
    return 'single_leg_squat'  # デフォルト


def save_results_to_s3(result: Dict, original_key: str) -> str:
    """
    処理結果をS3に保存
    
    Args:
        result: 処理結果
        original_key: 元の動画のS3キー
        
    Returns:
        str: 保存したS3キー
    """
    from datetime import datetime
    
    # results/YYYY/MM/DD/original_filename_timestamp.json
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    date_path = datetime.now().strftime('%Y/%m/%d')
    
    filename = Path(original_key).stem
    result_key = f"results/{date_path}/{filename}_{timestamp}.json"
    
    s3_client.put_object(
        Bucket=RESULTS_BUCKET,
        Key=result_key,
        Body=json.dumps(result, ensure_ascii=False, indent=2),
        ContentType='application/json'
    )
    
    return result_key


def convert_float_to_decimal(obj):
    """
    DynamoDB用にfloatをDecimalに変換

    Args:
        obj: 変換対象のオブジェクト（dict, list, float等）

    Returns:
        変換後のオブジェクト
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_float_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_float_to_decimal(item) for item in obj]
    return obj


def save_to_dynamodb(
    result: Dict,
    bucket: str,
    video_key: str,
    result_key: str,
    athlete_id: str = None,
    session_id: str = None
):
    """
    処理結果をDynamoDBに保存

    Args:
        result: 処理結果
        bucket: 元のバケット名
        video_key: 動画のS3キー
        result_key: 結果のS3キー
        athlete_id: 選手ID（オプション）
        session_id: セッションID（オプション）

    PHASE B: v2.1対応 - max_scoreとscoring_versionを記録
    Stage 4: athlete_id, session_idを記録（セッション比較機能対応）
    CRITICAL: DynamoDBはfloat型を受け付けないため、Decimal変換必須
    """
    from datetime import datetime

    table = dynamodb.Table(TABLE_NAME)

    # PHASE B: v2.1システム対応（max_scoreとversionを追加）
    # Stage 4: athlete_id, session_idを追加
    item = {
        'video_id': f"{bucket}/{video_key}",
        'processed_at': result['processed_at'],
        'test_type': result['test_type'],
        'score': result['score'],
        'max_score': result.get('max_score', 12),  # v1: 12, v2.1: 80
        'scoring_version': result.get('evaluation', {}).get('version', 'v1'),  # v1 or v2.1
        'result_s3_key': result_key,
        'video_info': result['video_info'],
        'health_check': result['health_check'],
        'evaluation': result.get('evaluation', {}),  # CRITICAL: Dashboard表示用に評価詳細も保存
        'ttl': int(datetime.now().timestamp()) + (90 * 24 * 60 * 60)  # 90日後に削除
    }

    # athlete_id, session_idが存在する場合のみ追加
    if athlete_id:
        item['athlete_id'] = athlete_id
    if session_id:
        item['session_id'] = session_id

    # DynamoDB用にfloatをDecimalに変換
    item = convert_float_to_decimal(item)

    table.put_item(Item=item)
