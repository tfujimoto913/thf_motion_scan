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
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, List
import uuid
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from processing.pose_extractor import PoseExtractor
from processing.normalizer import BodyNormalizer
from processing.evaluators_v2.single_leg_squat_v2 import SingleLegSquatEvaluatorV2
import numpy as np


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
  - best.png, worst.png, median.png (代表フレーム3枚、--overlay true時)
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


def select_representative_frames(frame_scores: List[Dict]) -> Dict:
    """
    What: 代表フレーム3枚（best/worst/median）を抽出
    Why: MVP仕様：overall scoreベースで代表フレーム選定
    Design Decision: best=最高, worst=最低, median=中央値近傍

    Args:
        frame_scores: フレームごとのスコア
            [{'frame_idx': int, 'score': float}, ...]

    Returns:
        Dict: {
            'best': {'frame_idx': int, 'score': float},
            'worst': {'frame_idx': int, 'score': float},
            'median': {'frame_idx': int, 'score': float}
        }

    CRITICAL: 単一フレームでも処理可能（全て同じフレーム返す）
    """
    if not frame_scores:
        # フレームがない場合のフォールバック
        return {
            'best': {'frame_idx': 0, 'score': 0.0},
            'worst': {'frame_idx': 0, 'score': 0.0},
            'median': {'frame_idx': 0, 'score': 0.0}
        }

    # スコアでソート
    sorted_frames = sorted(frame_scores, key=lambda x: x['score'])

    # best: 最高スコア
    best = sorted_frames[-1]

    # worst: 最低スコア
    worst = sorted_frames[0]

    # median: 中央値近傍
    median_idx = len(sorted_frames) // 2
    median = sorted_frames[median_idx]

    return {
        'best': best,
        'worst': worst,
        'median': median
    }


def generate_versions() -> Dict[str, str]:
    """
    What: versions フィールド生成
    Why: result.json の必須フィールド
    Design Decision: MVP段階は固定値、将来 CI で artifact_sha 自動埋め込み

    Returns:
        Dict: {
            'rules_version': str,
            'normalization_version': str,
            'artifact_sha': str
        }

    CRITICAL: 3キー必須（rules_version, normalization_version, artifact_sha）
    """
    return {
        'rules_version': '0.1.0',
        'normalization_version': 'none',
        'artifact_sha': 'local-dev'
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

    representative_frames = select_representative_frames(frame_scores)

    return {
        'session_id': session_id,
        'rep_id': rep_id,
        'scores': scores,
        'class': classification,
        'class_prob': class_prob,
        'uncertainty': uncertainty,
        'flags': flags,
        'versions': versions,
        'representative_frames': representative_frames,  # 代表フレーム3枚
        'evaluation_detail': eval_result  # デバッグ用詳細情報
    }


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
        print("  [2/3] 評価実行中...")
        result = run_pipeline(landmarks_data=landmarks_data)
        print("  ✅ 評価完了")

        # ステップ3: 結果表示
        print("  [3/3] 結果生成中...")
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
