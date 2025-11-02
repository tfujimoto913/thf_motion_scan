#!/usr/bin/env python3
"""
Purpose: Rep CLI MVP - 単一動画から rep 単位で計測・可視化・判定
Responsibility: CLI引数処理、入力検証、パイプライン実行
Dependencies: argparse, pathlib, processing.worker
Created: 2025-11-02 by Claude Code
Decision Log: Rep CLI MVP - Stage 1

CRITICAL:
- versions フィールド必須（rules_version, normalization_version, artifact_sha）
- 代表フレーム3枚（best/worst/median）
- 画像オーバーレイ仕様準拠
- result.json + trace.csv 出力
"""
import sys
import argparse
from pathlib import Path
from typing import Optional


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

        # TODO: Stage 2 でパイプライン実装
        print("⚠️  Stage 1 完了：CLI骨格実装済み")
        print("📝 次のステップ：Stage 2 パイプライン構築")

        return 0

    except FileNotFoundError as e:
        print(format_error_message(e), file=sys.stderr)
        return 1

    except Exception as e:
        print(format_error_message(e), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
