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
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from aws_xray_sdk.core import patch_all, xray_recorder
from decimal import Decimal
import boto3
from botocore.config import Config
from urllib.parse import unquote_plus
import cv2

# processingモジュールをインポート
sys.path.append('/var/task')
from processing.worker import VideoProcessingWorker
from processing.logger import (
    log_info,
    log_warning,
    log_error,
    set_request_context,
    set_processing_context,
    clear_context,
    emit_metric,
)
from processing.overlay_drawer import draw_overlay
from processing.utils import rotate_frame

patch_all()

# Retry policy configuration
# Design Decision: Exponential backoff with max 5 attempts (ADR-TBD)
# Why: Improve resilience against transient S3/DynamoDB errors
retry_config = Config(
    retries={
        'mode': 'adaptive',  # adaptive mode: exponential backoff + circuit breaker
        'max_attempts': 5,   # max 5 retries
    }
)

# AWS クライアント初期化（リトライポリシー適用）
s3_client = boto3.client('s3', config=retry_config)
sqs_client = boto3.client('sqs', config=retry_config)
dynamodb = boto3.resource('dynamodb', config=retry_config)

# 環境変数
RESULTS_BUCKET = os.environ.get('RESULTS_BUCKET', 'thf-motion-scan-results')
QUEUE_URL = os.environ.get('QUEUE_URL', '')
TABLE_NAME = os.environ.get('TABLE_NAME', 'thf-motion-scan-results')
REPS_TABLE_NAME = os.environ.get('REPS_TABLE_NAME')
RULES_VERSION = os.environ.get('RULES_VERSION', 'unknown')
THRESHOLDS_VERSION = os.environ.get('THRESHOLDS_VERSION', 'unknown')
ARTIFACT_SHA = os.environ.get('ARTIFACT_SHA', 'local-dev')


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda関数のメインハンドラー
    
    Args:
        event: S3イベントまたはSQSメッセージ
        context: Lambdaコンテキスト
        
    Returns:
        Dict: 処理結果
    """
    request_id = getattr(context, 'aws_request_id', None) if context else None
    function_name = getattr(context, 'function_name', os.environ.get('AWS_LAMBDA_FUNCTION_NAME'))
    environment = os.environ.get('ENVIRONMENT', os.environ.get('STAGE', 'dev'))
    set_request_context(
        request_id=request_id,
        environment=environment,
        function_name=function_name,
    )
    log_info("Event received", context={"event": event})

    start_time = time.perf_counter()
    result: Optional[Dict[str, Any]] = None

    try:
        # 変数初期化
        skip_metadata_fetch = False
        team_id = None
        athlete_id = None
        session_id = None
        test_type = None

        # S3イベントからバケット名とキーを取得
        if 'Records' in event:
            # S3またはSQS経由
            record = event['Records'][0]

            if 'eventSource' in record and record['eventSource'] == 'aws:s3':
                # S3ダイレクト
                bucket = record['s3']['bucket']['name']
                key = unquote_plus(record['s3']['object']['key'])
            elif 'body' in record:
                # SQS経由
                body = json.loads(record['body'])

                # カスタムフォーマット判定（videoKey存在チェック）
                if 'videoKey' in body:
                    # カスタムSQSメッセージフォーマット
                    # {"teamId": "...", "playerId": "...", "testType": "...", "videoKey": "...", "sessionId": "..."}
                    videos_bucket = os.environ.get('VIDEOS_BUCKET', 'thf-motion-scan-videos')
                    bucket = videos_bucket
                    key = body['videoKey']
                    # メタデータをbodyから直接取得
                    team_id = body.get('teamId')
                    athlete_id = body.get('playerId')
                    session_id = body.get('sessionId')
                    test_type = body.get('testType')

                    # 早期セット（S3メタデータ取得をスキップ）
                    set_processing_context(test_code=test_type, athlete_id=athlete_id, session_id=session_id)

                    log_info(
                        "Processing target identified (custom SQS format)",
                        test_type=test_type,
                        context={
                            "bucket": bucket,
                            "key": key,
                            "athlete_id": athlete_id,
                            "session_id": session_id,
                            "team_id": team_id
                        }
                    )

                    # S3メタデータ取得をスキップするフラグ
                    skip_metadata_fetch = True
                elif 'Records' in body:
                    # SQS経由のS3イベント（直接）
                    s3_record = body['Records'][0]
                    bucket = s3_record['s3']['bucket']['name']
                    key = unquote_plus(s3_record['s3']['object']['key'])
                    skip_metadata_fetch = False
                else:
                    raise ValueError("未知のSQSメッセージフォーマット")
            else:
                raise ValueError("未知のイベントフォーマット")
        else:
            raise ValueError("イベントにRecordsが含まれていません")

        # S3メタデータ取得（カスタムSQS形式の場合はスキップ）
        if not skip_metadata_fetch:
            # テストタイプをキーから抽出（例: videos/single_leg_squat/xxx.mp4）
            test_type = extract_test_type(key)

            # S3オブジェクトのメタデータからathlete_id, session_idを取得
            try:
                obj_metadata = s3_client.head_object(Bucket=bucket, Key=key)
                metadata = obj_metadata.get('Metadata', {})
                athlete_id = metadata.get('athlete-id', None)
                session_id = metadata.get('session-id', None)
                team_id = metadata.get('team-id', None)
            except Exception as e:
                log_warning(
                    "Failed to retrieve S3 object metadata",
                    test_type=test_type,
                    context={"error": str(e)}
                )
                athlete_id = None
                session_id = None
                team_id = None

            set_processing_context(test_code=test_type, athlete_id=athlete_id, session_id=session_id)

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

        with xray_recorder.in_subsegment('video_processing') as subsegment:
            subsegment.put_annotation('testType', test_type)
            subsegment.put_metadata('bucket', bucket, 'motion_scan')
            subsegment.put_metadata('s3Key', key, 'motion_scan')
            result = worker.process_video(
                video_path,
                test_type=test_type,
                athlete_id=athlete_id,
                session_id=session_id,
            )
        result_duration_ms = (time.perf_counter() - start_time) * 1000
        emit_metric(
            "VideoAnalysisDuration",
            result_duration_ms,
            unit="Milliseconds",
            dimensions={"Stage": "EndToEnd"},
        )
        emit_metric("AnalysesCompleted", 1)

        processing_context = worker.get_last_context()
        result_session_id = result.get("session_id") or session_id or datetime.utcnow().strftime('%Y%m%d-%H%M-X')
        overlay_items = upload_rep_overlays(
            video_path=video_path,
            result=result,
            landmark_frames=processing_context.get("landmarks_sequence"),
            bucket=RESULTS_BUCKET,
            player_id=athlete_id,
            team_id=team_id,
            test_type=test_type,
            session_id=result_session_id,
        )

        if overlay_items:
            overlay_map = {entry["rep_id"]: entry["overlay_key"] for entry in overlay_items}
            for rep in result.get("rep_detection", {}).get("reps", []):
                rep_id = rep.get("rep_id")
                if rep_id and rep_id in overlay_map:
                    rep["overlay_key"] = overlay_map[rep_id]
            result.setdefault("rep_detection", {})["overlays"] = overlay_items
            log_info(
                "Rep overlays uploaded",
                test_type=test_type,
                context={"count": len(overlay_items)},
            )

        derived_team_id = team_id or _derive_team_id(athlete_id)
        if derived_team_id:
            result["team_id"] = derived_team_id

        player_id = result.get("athlete_id") or athlete_id or "unknown-player"

        reps = result.get("rep_detection", {}).get("reps", [])
        rep_scores = [float(rep.get("score_primary") or 0.0) for rep in reps]
        best_score = max(rep_scores) if rep_scores else 0.0
        best_score = round(best_score, 1)
        best_rep_id = None
        if reps and rep_scores:
            best_rep = max(reps, key=lambda r: float(r.get("score_primary") or 0.0))
            best_rep_id = best_rep.get("rep_id")

        summary = {
            "player_id": player_id,
            "team_id": derived_team_id,
            "session_id": result_session_id,
            "test_type": test_type,
            "rep_count": len(reps),
            "score_primary": best_score,
            "best_rep_id": best_rep_id,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
        summary_key = upload_rep_summary_to_s3(
            summary,
            team_id=derived_team_id,
            player_id=player_id,
            test_type=test_type,
            session_id=result_session_id,
        )
        summary["s3_key"] = summary_key
        result["summary"] = summary

        # Health Check: summary.rep_count vs overlay PNG件数
        verify_rep_artifacts_health(
            summary=summary,
            overlay_count=len(overlay_items) if overlay_items else 0,
            test_type=test_type,
        )

        save_reps_to_dynamodb(
            reps,
            player_id=player_id,
            team_id=derived_team_id,
            session_id=result_session_id,
            test_type=test_type,
            processed_at=result.get("processed_at"),
        )

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
        save_to_dynamodb(result, bucket, key, result_key, environment, player_id, result_session_id)
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
    finally:
        clear_context()


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


def _sanitize_s3_component(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", value)
    safe = safe.strip("-")
    return safe or "unknown"


def _derive_team_id(player_id: Optional[str]) -> Optional[str]:
    if not player_id:
        return None
    parts = player_id.split("_")
    if len(parts) < 3 or parts[0] != "plr":
        return None
    return f"tm_{parts[1]}"


def _resize_with_max_edge(image, max_edge: int = 512):
    height, width = image.shape[:2]
    long_edge = max(height, width)
    if long_edge <= max_edge:
        return image
    scale = max_edge / long_edge
    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA)


def _build_overlay_annotation(result: Dict[str, Any], rep: Dict[str, Any]) -> Dict[str, Any]:
    rules_version = os.environ.get("RULES_VERSION") or result.get("rules_version") or "unknown"
    thresholds_version = (
        os.environ.get("THRESHOLDS_VERSION")
        or result.get("thresholds_version")
        or "unknown"
    )
    normalization_version = os.environ.get("NORMALIZATION_VERSION") or "none"

    return {
        "kpi_values": {},
        "kpi_classes": {},
        "kpi_p_values": {},
        "versions": {
            "rules_version": rules_version,
            "thresholds_version": thresholds_version,
            "normalization_version": normalization_version,
        },
        "metadata": {
            "selection_reason": "apex",
            "valid_kpi_count": 0,
            "total_kpi_count": 0,
            "na_rate": 0.0,
            "rep_id": rep.get("rep_id", "-"),
            "score_primary": rep.get("score_primary", 0.0),
            "dominant_leg": rep.get("dominant_leg", "-"),
        },
    }


def _build_session_prefix(
    team_id: Optional[str],
    player_id: Optional[str],
    test_type: str,
    session_id: str,
) -> str:
    components = [
        _sanitize_s3_component(team_id or "unknown-team"),
        _sanitize_s3_component(player_id or "unknown-player"),
        _sanitize_s3_component(test_type),
        _sanitize_s3_component(session_id),
    ]
    return "/".join(components)


def _build_overlay_key(
    team_id: Optional[str],
    player_id: Optional[str],
    test_type: str,
    session_id: str,
    rep_id: str,
) -> str:
    session_prefix = _build_session_prefix(team_id, player_id, test_type, session_id)
    return "/".join([session_prefix, "reps", _sanitize_s3_component(rep_id), "overlay.png"])


def upload_rep_summary_to_s3(
    summary: Dict[str, Any],
    *,
    team_id: Optional[str],
    player_id: Optional[str],
    test_type: str,
    session_id: str,
) -> str:
    session_prefix = _build_session_prefix(team_id, player_id, test_type, session_id)
    key = "/".join([session_prefix, "summary.json"])
    s3_client.put_object(
        Bucket=RESULTS_BUCKET,
        Key=key,
        Body=json.dumps(summary, ensure_ascii=False, indent=2),
        ContentType="application/json",
    )
    return key


def verify_rep_artifacts_health(
    summary: Dict[str, Any],
    overlay_count: int,
    test_type: str,
) -> None:
    """
    What: Rep artifacts健全性チェック
    Why: summary.jsonのrep_countとPNG実体件数の一致を検証

    Design Decision:
    - 不一致時は警告ログを出力（エラーにはしない）
    - 品質フラグの統計も出力（運用監視用）

    Args:
        summary: summary.jsonの内容
        overlay_count: 実際にアップロードしたoverlay.png件数
        test_type: テスト種別

    CRITICAL: 不一致時はアラート・監視対象とする
    """
    rep_count = summary.get("rep_count", 0)

    if rep_count != overlay_count:
        log_warning(
            "Rep count mismatch detected",
            test_type=test_type,
            context={
                "summary_rep_count": rep_count,
                "actual_overlay_count": overlay_count,
                "diff": abs(rep_count - overlay_count),
            },
        )
    else:
        log_info(
            "Rep artifacts health check passed",
            test_type=test_type,
            context={"rep_count": rep_count, "overlay_count": overlay_count},
        )


def upload_rep_overlays(
    video_path: str,
    result: Dict[str, Any],
    landmark_frames: Optional[List[Dict[str, Any]]],
    *,
    bucket: str,
    player_id: Optional[str],
    team_id: Optional[str],
    test_type: str,
    session_id: str,
) -> List[Dict[str, str]]:
    reps = (result.get("rep_detection") or {}).get("reps") or []
    if not reps or not landmark_frames:
        return []

    frame_map = {
        int(frame.get("frame", idx)): frame for idx, frame in enumerate(landmark_frames)
    }

    derived_team = team_id or _derive_team_id(player_id)
    overlays: List[Dict[str, str]] = []

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        log_warning(
            "Failed to open video for overlay generation",
            test_type=test_type,
            context={"video_path": video_path},
        )
        return overlays

    # CRITICAL: analyzer.pyで自動検出された回転角度を使用（メタデータに依存しない）
    rotation = result.get("rotation", 0)

    log_info(
        "Overlay rotation from processing context",
        test_type=test_type,
        context={"rotation": rotation},
    )

    try:
        for rep in reps:
            rep_id = rep.get("rep_id")
            apex_frame = rep.get("apex_frame")
            if rep_id is None or apex_frame is None:
                continue

            frame_data = frame_map.get(int(apex_frame))
            if not frame_data:
                continue

            cap.set(cv2.CAP_PROP_POS_FRAMES, int(apex_frame))
            success, frame = cap.read()
            if not success or frame is None:
                continue

            frame = rotate_frame(frame, rotation)

            landmarks = frame_data.get("landmarks")
            if not landmarks:
                continue

            annotation = _build_overlay_annotation(result, rep)
            try:
                overlay = draw_overlay(frame, landmarks, annotation)
            except Exception as exc:  # pragma: no cover - defensive
                log_warning(
                    "Overlay drawing failed",
                    test_type=test_type,
                    context={"rep_id": rep_id, "error": str(exc)},
                )
                continue

            overlay = _resize_with_max_edge(overlay, 512)
            success, encoded = cv2.imencode(".png", overlay)
            if not success:
                continue

            key = _build_overlay_key(
                derived_team,
                player_id,
                test_type,
                session_id,
                rep_id,
            )
            s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=encoded.tobytes(),
                ContentType="image/png",
            )
            overlays.append({"rep_id": rep_id, "overlay_key": key})
    finally:
        cap.release()

    return overlays


def save_reps_to_dynamodb(
    reps: List[Dict[str, Any]],
    *,
    player_id: str,
    team_id: Optional[str],
    session_id: str,
    test_type: str,
    processed_at: Optional[str],
):
    if not REPS_TABLE_NAME:
        log_warning(
            "REPS_TABLE_NAME not configured; skipping rep persistence",
            test_type=test_type,
        )
        return

    table = dynamodb.Table(REPS_TABLE_NAME)
    ttl_seconds = int(time.time()) + (90 * 24 * 60 * 60)

    default_team = team_id or _derive_team_id(player_id) or "unknown-team"

    with table.batch_writer() as batch:
        for rep in reps:
            rep_id = rep.get("rep_id")
            if not rep_id:
                continue

            score_primary = float(rep.get("score_primary") or 0.0)
            overlay_key = rep.get("overlay_key")
            dominant_leg = rep.get("dominant_leg")
            min_angle = rep.get("min_angle")
            item = {
                "PK": f"PLAYER#{player_id}",
                "SK": f"{session_id}#{test_type}#{rep_id}",
                "rep_id": rep_id,
                "rep_index": int(rep.get("rep_index", 0)),
                "player_id": player_id,
                "team_id": default_team,
                "session_id": session_id,
                "test_type": test_type,
                "score_primary": score_primary,
                "start_frame": int(rep.get("start_frame", 0)),
                "end_frame": int(rep.get("end_frame", 0)),
                "apex_frame": int(rep.get("apex_frame", 0)),
                "rules_version": RULES_VERSION,
                "thresholds_version": THRESHOLDS_VERSION,
                "artifact_sha": ARTIFACT_SHA,
                "processed_at": processed_at,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "ttl": ttl_seconds,
            }

            if overlay_key:
                item["overlay_key"] = overlay_key
            if dominant_leg:
                item["dominant_leg"] = dominant_leg
            if min_angle is not None:
                item["min_angle"] = float(min_angle)

            item = convert_float_to_decimal(item)
            batch.put_item(Item=item)


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
    environment: str,
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
    # Phase 2: quality_metricsを追加（技術的負債解消）
    item = {
        'video_id': f"{bucket}/{video_key}",
        'processed_at': result['processed_at'],
        'env': environment,
        'test_type': result['test_type'],
        'score': result['score'],
        'ai_score': result['score'],
        'max_score': result.get('max_score', 12),  # v1: 12, v2.1: 80
        'scoring_version': result.get('evaluation', {}).get('version', 'v1'),  # v1 or v2.1
        'result_s3_key': result_key,
        'video_key': video_key,
        'viz_key': result_key,
        'video_info': result['video_info'],
        'health_check': result['health_check'],
        'quality_metrics': result.get('quality_metrics', {}),  # Phase 2: 品質メトリクス保存
        'evaluation': result.get('evaluation', {}),  # CRITICAL: Dashboard表示用に評価詳細も保存
        'ttl': int(datetime.now().timestamp()) + (90 * 24 * 60 * 60)  # 90日後に削除
    }

    # athlete_id, session_idが存在する場合のみ追加
    if athlete_id:
        item['athlete_id'] = athlete_id
    if session_id:
        item['session_id'] = session_id
    team_id = result.get('team_id')
    if team_id:
        item['team_id'] = team_id

    # DynamoDB用にfloatをDecimalに変換
    item = convert_float_to_decimal(item)

    table.put_item(Item=item)
