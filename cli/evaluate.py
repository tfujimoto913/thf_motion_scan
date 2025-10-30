"""
Purpose: ローカル環境での動画評価CLIツール
Responsibility: 単一動画ファイルの評価と結果出力
Dependencies: processing.worker, argparse, pathlib
Created: 2025-10-29 by Claude Code
Decision Log: ローカル評価CLI - Stage 1

CRITICAL: worker.pyを変更せず再利用、出力形式はAWS Lambdaと完全一致
"""

import sys
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from processing.worker import VideoProcessingWorker


def main():
    """
    What: CLIメインエントリーポイント
    Why: コマンドライン引数を受け取り、動画評価を実行
    Design Decision: シンプルな単一動画評価（Stage 1）

    Usage:
        python cli/evaluate.py test_videos/balance/sample1.mp4
        python cli/evaluate.py test_videos/balance/sample1.mp4 --test-type single_leg_squat

    CRITICAL: worker.pyを変更せず、既存APIをそのまま使用
    """
    # コマンドライン引数解析
    parser = argparse.ArgumentParser(
        description='THF Motion Scan - ローカル評価CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python cli/evaluate.py test_videos/balance/sample1.mp4
  python cli/evaluate.py test_videos/balance/sample1.mp4 --test-type single_leg_squat
  python cli/evaluate.py /absolute/path/to/video.mp4 --athlete-id TaroYamada-100315

対応するテストタイプ:
  single_leg_squat, upper_body_swing, skater_lunge,
  cross_step, stride_mimic, push_pull, jump_landing
        """
    )

    parser.add_argument(
        'video_path',
        help='評価する動画ファイルのパス（相対パスまたは絶対パス）'
    )

    parser.add_argument(
        '--test-type',
        default='single_leg_squat',
        help='テストタイプ（デフォルト: single_leg_squat）'
    )

    parser.add_argument(
        '--athlete-id',
        default=None,
        help='アスリートID（省略時は自動生成）'
    )

    parser.add_argument(
        '--session-id',
        default=None,
        help='セッションID（省略時は自動生成）'
    )

    parser.add_argument(
        '--output-dir',
        default='output',
        help='出力ディレクトリ（デフォルト: output）'
    )

    parser.add_argument(
        '--config',
        default='config.json',
        help='config.jsonのパス（デフォルト: config.json）'
    )

    args = parser.parse_args()

    # 動画ファイルパスを解決
    video_path = Path(args.video_path)

    # 動画ファイルの存在確認
    if not video_path.exists():
        print(f"❌ エラー: 動画ファイルが見つかりません: {video_path}")
        print(f"   現在のディレクトリ: {Path.cwd()}")
        sys.exit(1)

    # 動画ファイル名から出力フォルダ名を生成
    video_stem = video_path.stem  # 拡張子なしのファイル名

    # 出力ディレクトリを解決
    output_dir = Path(args.output_dir)

    print("=" * 60)
    print("🚀 THF Motion Scan - ローカル評価")
    print("=" * 60)
    print(f"📹 動画ファイル: {video_path}")
    print(f"🧪 テストタイプ: {args.test_type}")
    print(f"📂 出力先: {output_dir}")
    print("=" * 60)
    print()

    try:
        # PHASE CORE LOGIC: VideoProcessingWorker初期化
        print("🔧 評価エンジン初期化中...")
        worker = VideoProcessingWorker(config_path=args.config)
        print("✅ 初期化完了")
        print()

        # PHASE CORE LOGIC: 動画評価実行
        result = worker.process_video(
            video_path=str(video_path),
            test_type=args.test_type,
            athlete_id=args.athlete_id,
            session_id=args.session_id,
            output_dir=str(output_dir)
        )

        # PHASE CORE LOGIC: 結果サマリー表示
        print()
        print("=" * 60)
        print("✨ 評価完了！")
        print("=" * 60)

        # PHASE B: v2.1対応（動的max_score表示）
        max_score = result.get('max_score', 12)
        print(f"🎯 総合スコア: {result['score']:.1f}/{max_score}")

        # v2.1の場合は詳細スコア表示
        if 'evaluation' in result and 'version' in result['evaluation']:
            version = result['evaluation']['version']
            if version in ['v2', 'v2.1']:
                eval_data = result['evaluation']
                print(f"   📊 システムバージョン: {version}")
                print(f"   🅰️  A評価（実施可否）: {eval_data.get('A_execution_score', 0):.1f}/20")
                print(f"   🅱️  B評価（8原則）: {eval_data.get('B_total', 0):.1f}/60")

                # B評価の局面別詳細（B_principlesから計算）
                if 'B_principles' in eval_data:
                    principles = eval_data['B_principles']
                    ecc_total = sum(principles.get('eccentric', {}).values())
                    con_total = sum(principles.get('concentric', {}).values())
                    print(f"      - Eccentric局面: {ecc_total:.1f}/30")
                    print(f"      - Concentric局面: {con_total:.1f}/30")

        print(f"👤 アスリートID: {result['athlete_id']}")
        print(f"📅 セッションID: {result['session_id']}")
        print(f"⏱️  処理時間: {result['processed_at']}")
        print()
        print("📁 出力ファイル:")
        if 'score_file' in result:
            print(f"   - {result['score_file']}")
        if 'manifest_file' in result:
            print(f"   - {result['manifest_file']}")
        print("=" * 60)

        return 0

    except FileNotFoundError as e:
        print(f"❌ エラー: {e}")
        sys.exit(1)

    except ValueError as e:
        print(f"❌ エラー: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"❌ 予期しないエラーが発生しました:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    sys.exit(main())
