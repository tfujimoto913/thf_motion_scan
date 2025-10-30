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
    print(f"📥 イベント受信: {json.dumps(event)}")
    
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
        
        print(f"📦 処理対象: s3://{bucket}/{key}")
        
        # テストタイプをキーから抽出（例: videos/single_leg_squat/xxx.mp4）
        test_type = extract_test_type(key)
        print(f"📋 テストタイプ: {test_type}")
        
        # 動画をダウンロード
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            video_path = tmp_file.name
            print(f"⬇️  動画ダウンロード中: {key}")
            s3_client.download_file(bucket, key, video_path)
        
        # 動画処理
        print(f"🎬 動画処理開始")
        worker = VideoProcessingWorker('/var/task/config.json')

        # PHASE B: スコアリングバージョン確認（v2.1システム検証用）
        print(f"📊 スコアリングシステム: {worker.scoring_version}")
        print(f"🔄 検証モード: {worker.validation_mode}")

        result = worker.process_video(video_path, test_type=test_type)
        
        # 一時ファイル削除
        os.unlink(video_path)
        
        # 結果をS3に保存
        result_key = save_results_to_s3(result, key)
        print(f"💾 結果保存: s3://{RESULTS_BUCKET}/{result_key}")
        
        # DynamoDBに記録
        save_to_dynamodb(result, bucket, key, result_key)
        print(f"📝 DynamoDB記録完了")
        
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
        print(f"❌ エラー: {str(e)}")
        import traceback
        traceback.print_exc()
        
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


def save_to_dynamodb(result: Dict, bucket: str, video_key: str, result_key: str):
    """
    処理結果をDynamoDBに保存

    Args:
        result: 処理結果
        bucket: 元のバケット名
        video_key: 動画のS3キー
        result_key: 結果のS3キー

    PHASE B: v2.1対応 - max_scoreとscoring_versionを記録
    CRITICAL: DynamoDBはfloat型を受け付けないため、Decimal変換必須
    """
    from datetime import datetime

    table = dynamodb.Table(TABLE_NAME)

    # PHASE B: v2.1システム対応（max_scoreとversionを追加）
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
        'ttl': int(datetime.now().timestamp()) + (90 * 24 * 60 * 60)  # 90日後に削除
    }

    # DynamoDB用にfloatをDecimalに変換
    item = convert_float_to_decimal(item)

    table.put_item(Item=item)
