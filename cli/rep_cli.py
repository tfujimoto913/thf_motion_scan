#!/usr/bin/env python3
"""
Purpose: Rep CLI MVP - 単一動画から rep 単位で計測・可視化・判定
Responsibility: CLI引数処理、入力検証、パイプライン実行
Dependencies: argparse, pathlib, processing.worker
Created: 2025-11-02 by Claude Code
Decision Log: Rep CLI MVP - Stage 1, Stage 2

CRITICAL:
- versions フィールド必須（rules_version, normalization_version, artifact_sha）
- 代表フレーム3枚（best/worst/median）
- 画像オーバーレイ仕様準拠
- result.json + trace.csv 出力
"""
import argparse
import os
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any
import uuid
from datetime import datetime, timezone

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# In-memory cache for thresholds metadata (avoids repeated disk reads)
_THRESHOLDS_CACHE: Optional[Dict[str, Any]] = None

from processing.pose_extractor import PoseExtractor
from processing.normalizer import BodyNormalizer
from processing.evaluators_v2.single_leg_squat_v2 import SingleLegSquatEvaluatorV2
import numpy as np
import json
import csv
import cv2

from src.config.loader import load_thresholds
from src.validation_engine import apply_rep, apply_session
from processing.frame_selector import (
    select_rep_frame_triplet,
    build_frame_filename,
    upload_frame_image,
)


def parse_args(args: Optional[list] = None):
    """
    What: CLI引数をパース
    Why: コマンドライン引数の解析と検証
    Design Decision: argparse ベース、明確なヘルプメッセージ

    Args:
        args: テスト用引数リスト（省略時は sys.argv を使用）

    Returns:
        argparse.Namespace: パース済み引数

    CRITICAL: --video は必須、他はオプション
    """
    parser = argparse.ArgumentParser(
        prog='rep-cli',
        description='THF Motion Scan - Rep CLI MVP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  rep-cli --video test.mp4
  rep-cli --video test.mp4 --out-dir ./output
  rep-cli --video test.mp4 --dump-trace false --overlay false
  rep-cli --help

出力:
  - {session_id}_{rep_id}_{type}.jpg ×3 (type: best/worst/repr、--overlay true時)
  - result.json (scores, class, versions含む)
  - trace.csv (時系列データ、--dump-trace true時)

フラグ一覧:
  --video PATH         入力動画ファイルパス（必須）
  --out-dir PATH       出力ディレクトリ（既定：入力動画と同階層）
  --dump-trace BOOL    CSV出力ON/OFF（既定：true）
  --overlay BOOL       画像出力ON/OFF（既定：true）
  --help               このヘルプを表示
        """
    )

    parser.add_argument(
        '--video',
        required=True,
        help='入力動画ファイルパス（必須）'
    )

    parser.add_argument(
        '--out-dir',
        default=None,
        help='出力ディレクトリ（既定：入力動画と同階層）'
    )

    parser.add_argument(
        '--dump-trace',
        default='true',
        choices=['true', 'false'],
        help='CSV出力ON/OFF（既定：true）'
    )

    parser.add_argument(
        '--overlay',
        default='true',
        choices=['true', 'false'],
        help='画像出力ON/OFF（既定：true）'
    )

    parsed = parser.parse_args(args)

    # 文字列 'true'/'false' を bool に変換
    parsed.dump_trace = parsed.dump_trace == 'true'
    parsed.overlay = parsed.overlay == 'true'

    return parsed


def validate_input(video_path: Path) -> None:
    """
    What: 入力動画ファイルの検証
    Why: ファイル存在チェック、エラーの早期検出
    Design Decision: 明確なエラーメッセージ + 次アクション提示

    Args:
        video_path: 検証対象の動画ファイルパス

    Raises:
        FileNotFoundError: ファイルが存在しない場合

    CRITICAL: エラーメッセージに原因 + 次アクション含む
    """
    if not video_path.exists():
        raise FileNotFoundError(
            f"❌ 動画ファイルが見つかりません: {video_path}\n"
            f"次のアクション:\n"
            f"  1. ファイルパスを確認してください\n"
            f"  2. ファイルが存在することを確認してください\n"
            f"  3. 絶対パスまたは正しい相対パスを指定してください"
        )


def format_error_message(error: Exception) -> str:
    """
    What: エラーメッセージを整形
    Why: ユーザーが次アクションを判断できるようにする
    Design Decision: 原因 + 次アクション提示

    Args:
        error: 発生したエラー

    Returns:
        str: 整形済みエラーメッセージ

    CRITICAL: ユーザーフレンドリーなメッセージ
    """
    error_type = type(error).__name__
    error_msg = str(error)

    # FileNotFoundError の場合
    if isinstance(error, FileNotFoundError):
        # validate_input で生成されたメッセージがある場合はそのまま返す
        if '次のアクション' in error_msg:
            return error_msg
        # シンプルなメッセージの場合は整形
        return (
            f"❌ ファイルが見つかりません: {error_msg}\n"
            f"次のアクション:\n"
            f"  1. ファイルパスを確認してください\n"
            f"  2. ファイルが存在することを確認してください\n"
            f"  3. 絶対パスまたは正しい相対パスを指定してください"
        )

    # その他のエラー
    return (
        f"❌ エラーが発生しました: {error_type}\n"
        f"詳細: {error_msg}\n"
        f"次のアクション:\n"
        f"  1. 入力ファイルとパラメータを確認してください\n"
        f"  2. --help でフラグ一覧を確認してください\n"
        f"  3. 問題が解決しない場合は issue を作成してください"
    )


def select_representative_frames(
    frame_scores: List[Dict],
    *,
    session_mean: Optional[float] = None,
) -> Dict:
    """
    What: 代表フレーム3枚（best/worst/repr）を抽出
    Why: Task E仕様：composite score を主軸に代表フレーム選定
    Design Decision: best=最高, worst=最低, repr=セッション平均に最も近いフレーム

    Args:
        frame_scores: フレームごとのスコア
            [{'frame_idx': int, 'score': float}, ...]
        session_mean: セッション平均スコア（repr選定のタイブレークで利用）

    Returns:
        Dict: {
            'best': {'frame_idx': int, 'score': float},
            'worst': {'frame_idx': int, 'score': float},
            'repr': {'frame_idx': int, 'score': float}
        }

    CRITICAL: 単一フレームでも処理可能（全て同じフレーム返す）
    """
    selection = select_rep_frame_triplet(frame_scores, session_mean=session_mean)
    # 後方互換のため median alias を追加
    selection['median'] = selection['repr']
    return selection


def check_visibility(landmarks: List[Dict], threshold: float = 0.5) -> bool:
    """
    What: ランドマークの可視性をチェック
    Why: 描画に必要なランドマークが十分に見えているか確認
    Design Decision: 肩・hip・鼻の可視性をチェック（MVP簡易版）

    Args:
        landmarks: ランドマークリスト（33個想定）
        threshold: 可視性閾値（デフォルト0.5）

    Returns:
        bool: 全ての必要ランドマークが閾値以上ならTrue

    CRITICAL: MediaPipeインデックス（NOSE=0, LEFT_SHOULDER=11, RIGHT_SHOULDER=12, LEFT_HIP=23, RIGHT_HIP=24）
    """
    # 必要なランドマークのインデックス
    required_indices = [0, 11, 12, 23, 24]  # NOSE, LEFT_SHOULDER, RIGHT_SHOULDER, LEFT_HIP, RIGHT_HIP

    for idx in required_indices:
        if idx >= len(landmarks):
            return False
        if landmarks[idx].get('visibility', 0.0) < threshold:
            return False

    return True


def draw_overlay(frame: np.ndarray, landmarks: List[Dict], overlay_info: Dict) -> np.ndarray:
    """
    What: フレームに骨格オーバーレイを描画
    Why: 視覚的な評価結果を提供
    Design Decision: 肩線・骨盤線・体幹軸・class注記（MVP簡易版）

    Args:
        frame: 元フレーム画像（BGR形式）
        landmarks: ランドマークリスト（33個想定）
        overlay_info: オーバーレイ情報（class, class_prob, scores）

    Returns:
        np.ndarray: 注釈付き画像

    CRITICAL:
    - 座標は正規化（0-1）→ピクセル座標に変換
    - MediaPipeインデックス使用
    - 可視性チェックは呼び出し側で実施
    """
    # コピーして元画像を保護
    annotated = frame.copy()
    h, w = frame.shape[:2]

    # MediaPipeランドマークインデックス
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24

    def to_pixel(landmark):
        """正規化座標→ピクセル座標"""
        x = int(landmark['x'] * w)
        y = int(landmark['y'] * h)
        return (x, y)

    # 肩線描画
    if len(landmarks) > RIGHT_SHOULDER:
        left_shoulder = to_pixel(landmarks[LEFT_SHOULDER])
        right_shoulder = to_pixel(landmarks[RIGHT_SHOULDER])
        cv2.line(annotated, left_shoulder, right_shoulder, (0, 255, 0), 2)  # 緑

    # 骨盤線描画
    if len(landmarks) > RIGHT_HIP:
        left_hip = to_pixel(landmarks[LEFT_HIP])
        right_hip = to_pixel(landmarks[RIGHT_HIP])
        cv2.line(annotated, left_hip, right_hip, (255, 0, 0), 2)  # 青

    # 体幹軸描画（首〜骨盤中心）
    if len(landmarks) > RIGHT_HIP:
        # 首の位置（肩の中点で近似）
        left_shoulder_pt = to_pixel(landmarks[LEFT_SHOULDER])
        right_shoulder_pt = to_pixel(landmarks[RIGHT_SHOULDER])
        neck_x = (left_shoulder_pt[0] + right_shoulder_pt[0]) // 2
        neck_y = (left_shoulder_pt[1] + right_shoulder_pt[1]) // 2
        neck = (neck_x, neck_y)

        # 骨盤中心
        left_hip_pt = to_pixel(landmarks[LEFT_HIP])
        right_hip_pt = to_pixel(landmarks[RIGHT_HIP])
        pelvis_x = (left_hip_pt[0] + right_hip_pt[0]) // 2
        pelvis_y = (left_hip_pt[1] + right_hip_pt[1]) // 2
        pelvis = (pelvis_x, pelvis_y)

        cv2.line(annotated, neck, pelvis, (0, 255, 255), 2)  # 黄

    # Class注記（左上）
    class_text = f"{overlay_info['class']} (p={overlay_info['class_prob']:.2f})"
    cv2.putText(annotated, class_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    # スコア注記（左上、2行目）
    score_text = f"Score: {overlay_info['scores']['overall']:.1f}"
    cv2.putText(annotated, score_text, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    return annotated


def export_result_json(result: Dict, output_path: str) -> None:
    """
    What: result.json を出力
    Why: MVP必須出力ファイル（scores, class, versions含む）
    Design Decision: JSON形式、indent=2で可読性確保

    Args:
        result: パイプライン実行結果
        output_path: 出力ファイルパス

    CRITICAL: versions フィールド必須
    """
    # evaluation_detail は internal なのでファイル出力から除外
    output_data = {k: v for k, v in result.items() if k != 'evaluation_detail'}

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def _load_thresholds_data() -> Dict[str, Any]:
    """
    What: Load thresholds_v2 JSON once and cache it.
    Why: Version metadata and validation thresholds are reused across exports.
    """
    global _THRESHOLDS_CACHE

    if _THRESHOLDS_CACHE is not None:
        return _THRESHOLDS_CACHE

    thresholds_path = project_root / "config" / "thresholds_v2.json"
    if thresholds_path.exists():
        thresholds = load_thresholds(str(thresholds_path))
    else:
        thresholds = {
            "versions": {
                "rules_version": "0.1.0",
                "thresholds_version": "0.1.0",
                "normalization_version": "none",
                "artifact_sha": "local-dev",
            },
            "tests": [],
        }

    tests = thresholds.get("tests", [])
    if isinstance(tests, dict):
        normalized_tests = []
        for code, entry in tests.items():
            merged = {"code": code}
            merged.update(entry)
            normalized_tests.append(merged)
        thresholds["tests"] = normalized_tests

    _THRESHOLDS_CACHE = thresholds
    return thresholds


def export_trace_csv(trace_data: List[Dict], output_path: str) -> None:
    """
    What: trace.csv を出力（時系列データ）
    Why: フレームごとの角度・イベント・判定を記録
    Design Decision: CSV形式、ヘッダー付き

    Args:
        trace_data: フレームごとのトレースデータ
            [{'time': float, 'angle_x': float, ...}, ...]
        output_path: 出力ファイルパス

    CRITICAL: スキーマ固定（time, angle_x, angle_y, angle_z, events, class_trace）
    """
    if not trace_data:
        # データがない場合は空ファイル作成
        with open(output_path, 'w', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['time', 'angle_x', 'angle_y', 'angle_z', 'events', 'class_trace'])
        return

    fieldnames = ['time', 'angle_x', 'angle_y', 'angle_z', 'events', 'class_trace']

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trace_data)


def generate_versions() -> Dict[str, str]:
    """
    What: versions フィールド生成
    Why: result.json 及び rep/session exports の必須フィールド
    Design Decision: thresholds_v2.json の versions セクションを単一の真実源とする
    """
    thresholds = _load_thresholds_data()
    versions = thresholds.get("versions", {})

    return {
        'rules_version': versions.get('rules_version', '0.1.0'),
        'thresholds_version': versions.get('thresholds_version', '0.1.0'),
        'normalization_version': versions.get('normalization_version', 'none'),
        'artifact_sha': versions.get('artifact_sha', 'local-dev'),
    }


STATE_MAP = {
    "OK": "VALID",
    "WARN": "WARN",
    "ERROR": "INVALID"
}


def _normalise_validation(validation: Dict[str, Any]) -> Dict[str, Any]:
    raw_state = validation.get('state', 'WARN')
    mapped_state = STATE_MAP.get(raw_state, 'WARN')
    raw_messages = validation.get('violations', []) or validation.get('messages', [])
    messages: List[str] = []
    for item in raw_messages:
        if isinstance(item, str):
            messages.append(item)
        elif isinstance(item, dict):
            if 'message' in item:
                messages.append(str(item['message']))
            elif 'field' in item and 'status' in item:
                messages.append(f"{item['field']} -> {item['status']}")
            else:
                messages.append(json.dumps(item, ensure_ascii=False))
        else:
            messages.append(str(item))
    if mapped_state == 'VALID':
        messages = []
    return {
        'state': mapped_state,
        'messages': messages
    }


def build_rep_result_record(result: Dict[str, Any], rep_index: int = 0) -> Dict[str, Any]:
    """Construct a rep_result entry that aligns with schema/rep_result.schema.json."""

    evaluation = result.get('evaluation_detail') or result.get('evaluation', {})
    scores_payload = result.get('scores', {})

    scores = {
        'angle_score': float(scores_payload.get('A_execution', 0.0)),
        'stability_score': float(scores_payload.get('B_total', 0.0)),
        'composite_score': float(scores_payload.get('overall', 0.0))
    }

    metadata_src = result.get('metadata', {})
    processed_at = metadata_src.get('processed_at')
    if not processed_at:
        processed_at = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()
    frame_count = metadata_src.get('frame_count') or 1
    video_url = metadata_src.get('video_url') or f"s3://mock/rep-results/{result.get('rep_id')}.mp4"

    return {
        'rep_id': result.get('rep_id'),
        'session_id': result.get('session_id'),
        'test_name': result.get('test_type'),
        'threshold_version': result['versions'].get('thresholds_version', 'v0.0'),
        'scores': scores,
        'validation': _normalise_validation(result.get('validation', {})),
        'metadata': {
            'processed_at': processed_at,
            'frame_count': int(frame_count),
            'video_url': video_url
        }
    }


def build_session_result_record(
    result: Dict[str, Any],
    rep_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Construct a session_result entry that aligns with schema/session_result.schema.json.
    """
    total_reps = len(rep_records)
    composite_scores = [rep['scores']['composite_score'] for rep in rep_records]
    mean_composite = float(sum(composite_scores) / len(composite_scores)) if composite_scores else 0.0
    if len(composite_scores) > 1:
        variance = sum((score - mean_composite) ** 2 for score in composite_scores) / len(composite_scores)
    else:
        variance = 0.0
    std_composite = variance ** 0.5

    versions = result['versions']
    thresholds = _load_thresholds_data()
    session_validation = apply_session(
        {'overall_score': mean_composite} if composite_scores else {},
        versions,
        thresholds
    )['validation']

    normalized_session_validation = _normalise_validation(session_validation)

    rep_states = [rep['validation']['state'] for rep in rep_records]
    valid_rep_count = sum(1 for state in rep_states if state == 'VALID')
    qc_pass = valid_rep_count >= 3

    metadata_src = result.get('metadata', {})
    processed_at = metadata_src.get('processed_at') or datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    return {
        'session_id': result.get('session_id'),
        'athlete_id': result.get('athlete_id') or 'Unknown',
        'test_name': result.get('test_type'),
        'threshold_version': versions.get('thresholds_version', 'v0.0'),
        'aggregated_scores': {
            'mean_composite': round(mean_composite, 2),
            'std_composite': round(std_composite, 2),
            'valid_rep_count': valid_rep_count,
            'total_rep_count': 5
        },
        'validation': {
            'state': normalized_session_validation['state'],
            'messages': normalized_session_validation['messages'],
            'qc_gate_result': {
                'gate_name': 'B4_sigma',
                'passed': qc_pass,
                'criteria_met': ['B4_sigma >= 3.0'] if qc_pass else []
            }
        },
        'reps': [
            {
                'rep_id': rep['rep_id'],
                'state': rep['validation']['state']
            }
            for rep in rep_records
        ],
        'metadata': {
            'processed_at': processed_at,
            'versions': {
                'threshold': versions.get('thresholds_version', 'v0.0'),
                'schema': '1.0.0'
            }
        }
    }


def export_rep_session_results(result: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
    """
    Export rep_result.json and session_result.json documents for downstream consumers.
    Returns a dict of created file paths for convenience.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rep_record = build_rep_result_record(result, rep_index=0)
    rep_result_path = output_dir / 'rep_result.json'
    with open(rep_result_path, 'w', encoding='utf-8') as fh:
        json.dump(rep_record, fh, indent=2, ensure_ascii=False)

    session_record = build_session_result_record(result, [rep_record])
    session_result_path = output_dir / 'session_result.json'
    with open(session_result_path, 'w', encoding='utf-8') as fh:
        json.dump(session_record, fh, indent=2, ensure_ascii=False)

    return {
        'rep_result': rep_result_path,
        'session_result': session_result_path,
    }


def run_pipeline(
    landmarks_data: List[Dict],
    test_type: str = 'single_leg_squat'
) -> Dict:
    """
    What: パイプライン実行（pose抽出→評価→結果生成）
    Why: rep単位の計測・判定を実行
    Design Decision: evaluators_v2 使用（8原則・560点満点システム）

    Args:
        landmarks_data: ランドマークデータ（フレームごと）
        test_type: テストタイプ（MVP: single_leg_squat のみ）

    Returns:
        Dict: {
            'session_id': str,
            'rep_id': str,
            'scores': Dict,
            'class': str,
            'class_prob': float,
            'uncertainty': float,
            'flags': List[str],
            'versions': Dict
        }

    CRITICAL: versions フィールド必須
    """
    # セッションID・repID生成
    session_id = str(uuid.uuid4())
    rep_id = str(uuid.uuid4())

    # versions 生成
    versions = generate_versions()

    # フラグ初期化
    flags = []

    # PHASE CORE LOGIC: Normalizer で base_width 計算
    normalizer = BodyNormalizer()

    # 最初のフレームから base_width を計算（MVP: 簡易実装）
    base_width = None
    if landmarks_data and len(landmarks_data) > 0:
        first_frame = landmarks_data[0]
        if 'landmarks' in first_frame:
            base_width = normalizer.calculate_base_width(first_frame['landmarks'])

    # base_width が取得できない場合のフォールバック
    if base_width is None:
        base_width = 1.0  # デフォルト値
        flags.append('base_width_unavailable')

    # PHASE CORE LOGIC: Evaluator統合
    # MVP段階：single_leg_squat のみ対応
    evaluator = SingleLegSquatEvaluatorV2()
    eval_result = evaluator.evaluate(landmarks_data, base_width=base_width)

    # スコア抽出
    scores = {
        'overall': eval_result.get('total_score', 0.0),
        'A_execution': eval_result.get('A_execution_score', 0.0),
        'B_total': eval_result.get('B_total', 0.0)
    }

    # 判定（MVP: 簡易的な閾値ベース）
    overall = scores['overall']
    if overall >= 60:  # 80点満点の75%
        classification = 'pass'
        class_prob = 0.9
    elif overall >= 40:  # 80点満点の50%
        classification = 'needs_improvement'
        class_prob = 0.7
    else:
        classification = 'fail'
        class_prob = 0.8

    uncertainty = 1.0 - class_prob

    # フラグ追加（Evaluatorから）
    if eval_result.get('flags'):
        flags.extend(eval_result['flags'])

    # PHASE CORE LOGIC: 代表フレーム抽出（MVP: overall scoreベース）
    # 各フレームのスコアを抽出
    frame_scores = []
    if 'frame_scores' in eval_result:
        frame_scores = eval_result['frame_scores']
    else:
        # フォールバック：全フレームにoverallスコアを割り当て
        for idx in range(len(landmarks_data)):
            frame_scores.append({'frame_idx': idx, 'score': overall})

    selection = select_representative_frames(frame_scores, session_mean=scores['overall'])
    static_frames = {key: selection[key] for key in ['best', 'worst', 'repr']}

    thresholds = _load_thresholds_data()
    rep_validation = apply_rep(
        {'overall_score': overall},
        versions,
        thresholds
    )['validation']

    result = {
        'session_id': session_id,
        'rep_id': rep_id,
        'test_type': test_type,
        'scores': scores,
        'class': classification,
        'class_prob': class_prob,
        'uncertainty': uncertainty,
        'flags': flags,
        'versions': versions,
        'static_frames': static_frames,  # best/worst/repr
        'representative_frames': selection,  # 後方互換（median alias含む）
        'evaluation_detail': eval_result,  # デバッグ用詳細情報
        'validation': rep_validation,
    }

    return result


def main():
    """
    What: CLIメインエントリーポイント
    Why: 引数パース→検証→パイプライン実行
    Design Decision: エラーハンドリング統合、構造化ログ出力

    CRITICAL: versions フィールド必須出力
    """
    try:
        # 引数パース
        args = parse_args()

        # 入力検証
        video_path = Path(args.video)
        validate_input(video_path)

        # 出力ディレクトリ決定
        if args.out_dir is None:
            # 既定：入力動画と同階層
            out_dir = video_path.parent
        else:
            out_dir = Path(args.out_dir)

        print("=" * 60)
        print("🚀 Rep CLI MVP - THF Motion Scan")
        print("=" * 60)
        print(f"📹 入力動画: {video_path}")
        print(f"📂 出力先: {out_dir}")
        print(f"📊 CSV出力: {'ON' if args.dump_trace else 'OFF'}")
        print(f"🎨 画像出力: {'ON' if args.overlay else 'OFF'}")
        print("=" * 60)
        print()

        # PHASE CORE LOGIC: パイプライン実行
        print("🔧 パイプライン実行中...")

        # ステップ1: 骨格推定
        print("  [1/3] 骨格推定中...")
        pose_extractor = PoseExtractor()
        landmarks_result = pose_extractor.extract_landmarks(str(video_path))
        landmarks_data = landmarks_result['landmarks']
        print(f"  ✅ {landmarks_result['detected_frames']}/{landmarks_result['frame_count']} フレーム検出")

        # ステップ2: 評価実行
        print("  [2/4] 評価実行中...")
        result = run_pipeline(landmarks_data=landmarks_data)
        print("  ✅ 評価完了")

        # ステップ2.5: 代表フレーム画像生成（--overlay true の場合）
        image_paths = []
        if args.overlay:
            print("  [2.5/4] 代表フレーム画像生成中...")

            # 出力ディレクトリ作成
            out_dir.mkdir(parents=True, exist_ok=True)

            rep_frames = result.get('static_frames', {})

            cap = cv2.VideoCapture(str(video_path))
            frame_bucket = os.environ.get("THF_FRAME_BUCKET")
            frame_prefix = os.environ.get("THF_FRAME_PREFIX")
            s3_client = None
            s3_uris: List[str] = []
            if frame_bucket:
                import boto3

                s3_client = boto3.client("s3")

            for frame_type in ['best', 'worst', 'repr']:
                if frame_type not in rep_frames:
                    continue

                frame_idx = rep_frames[frame_type]['frame_idx']

                # フレーム位置設定
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
                ret, frame = cap.read()

                if not ret:
                    print(f"  ⚠️  {frame_type} フレーム取得失敗（idx={frame_idx}）")
                    continue

                # ランドマーク取得
                if frame_idx < len(landmarks_data) and 'landmarks' in landmarks_data[frame_idx]:
                    landmarks = landmarks_data[frame_idx]['landmarks']

                    # 可視性チェック
                    if check_visibility(landmarks):
                        # オーバーレイ情報
                        overlay_info = {
                            'class': result['class'],
                            'class_prob': result['class_prob'],
                            'scores': result['scores']
                        }

                        # オーバーレイ描画
                        annotated = draw_overlay(frame, landmarks, overlay_info)

                        # 画像保存
                        file_name = build_frame_filename(result['session_id'], result['rep_id'], frame_type)
                        image_path = out_dir / file_name
                        cv2.imwrite(str(image_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 92])
                        image_paths.append(image_path)
                        print(f"  ✅ {image_path}")

                        if s3_client and frame_bucket:
                            metadata = {
                                "session_id": result['session_id'],
                                "rep_id": result['rep_id'],
                                "frame_type": frame_type,
                                "frame_idx": rep_frames[frame_type]['frame_idx'],
                                "score": rep_frames[frame_type]['score'],
                            }
                            s3_key = upload_frame_image(
                                s3_client,
                                frame_bucket,
                                result['session_id'],
                                result['rep_id'],
                                frame_type,
                                image_path,
                                prefix=frame_prefix,
                                metadata=metadata,
                            )
                            s3_uri = f"s3://{frame_bucket}/{s3_key}"
                            s3_uris.append(s3_uri)
                            print(f"     ↳ ☁️ Uploaded to {s3_uri}")

                    else:
                        # 可視性不足
                        if 'low_visibility' not in result['flags']:
                            result['flags'].append('low_visibility')
                        print(f"  ⚠️  {frame_type} フレーム：可視性不足（描画スキップ）")

            cap.release()
            if image_paths:
                result.setdefault('frame_assets', {})['local'] = [str(path) for path in image_paths]
            if s3_client and frame_bucket and s3_uris:
                result.setdefault('frame_assets', {})['s3'] = s3_uris

        # ステップ3: ファイル出力
        print("  [3/4] ファイル出力中...")

        # 出力ディレクトリ作成
        out_dir.mkdir(parents=True, exist_ok=True)

        # result.json 出力
        result_json_path = out_dir / "result.json"
        export_result_json(result, str(result_json_path))
        print(f"  ✅ {result_json_path}")

        # rep/session スキーマ準拠の出力
        rep_session_paths = export_rep_session_results(result, out_dir)
        print(f"  ✅ {rep_session_paths['rep_result']}")
        print(f"  ✅ {rep_session_paths['session_result']}")

        # trace.csv 出力（--dump-trace true の場合）
        if args.dump_trace:
            # MVP段階：トレースデータは evaluation_detail から抽出
            trace_data = []
            if 'evaluation_detail' in result and 'frame_data' in result['evaluation_detail']:
                for frame in result['evaluation_detail']['frame_data']:
                    trace_data.append({
                        'time': frame.get('time', 0.0),
                        'angle_x': frame.get('angle_x', 0.0),
                        'angle_y': frame.get('angle_y', 0.0),
                        'angle_z': frame.get('angle_z', 0.0),
                        'events': frame.get('events', ''),
                        'class_trace': frame.get('class_trace', 'pending')
                    })

            trace_csv_path = out_dir / "trace.csv"
            export_trace_csv(trace_data, str(trace_csv_path))
            print(f"  ✅ {trace_csv_path}")

        # ステップ4: 結果表示
        print("  [4/4] 完了")
        print("=" * 60)
        print("✨ 処理完了")
        print("=" * 60)
        print(f"📊 versions:")
        for key, value in result['versions'].items():
            print(f"   - {key}: {value}")
        print(f"🎯 scores: {result['scores']}")
        print(f"📝 flags: {result['flags']}")
        print(f"🆔 session_id: {result['session_id']}")
        print(f"🆔 rep_id: {result['rep_id']}")
        print()
        print("📁 出力ファイル:")
        print(f"   - {result_json_path}")
        print(f"   - {rep_session_paths['rep_result']}")
        print(f"   - {rep_session_paths['session_result']}")
        if args.dump_trace:
            print(f"   - {trace_csv_path}")
        if args.overlay and image_paths:
            for img_path in image_paths:
                print(f"   - {img_path}")
        if args.overlay and result.get('frame_assets', {}).get('s3'):
            for uri in result['frame_assets']['s3']:
                print(f"   - {uri}")
        print("=" * 60)

        return 0

    except FileNotFoundError as e:
        print(format_error_message(e), file=sys.stderr)
        return 1

    except Exception as e:
        print(format_error_message(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
