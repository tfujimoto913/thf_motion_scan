"""
Purpose: rep-cli の引数パース・エラーハンドリングテスト
Responsibility: CLI入出力ロジックの検証
Dependencies: cli.rep_cli, pytest
Created: 2025-11-02 by Claude Code
Decision Log: Rep CLI MVP - Stage 1

CRITICAL: TDD Red phase - このテストは最初失敗すべき
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock


# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestRepCLIArgumentParsing:
    """
    What: rep-cli の引数パーステスト
    Why: コマンドライン引数の正しい解析を保証
    Design Decision: argparse ベースの引数処理
    """

    def test_parse_minimal_args(self):
        """
        What: 最小限の引数（--video のみ）をパース
        Why: 必須引数のみで動作することを保証
        Design Decision: --video は必須、他はオプション
        """
        # NOTE: この段階では cli.rep_cli が存在しないため失敗する（TDD Red）
        from cli.rep_cli import parse_args

        test_args = ['--video', 'test.mp4']
        args = parse_args(test_args)

        assert args.video == 'test.mp4'
        # デフォルト値確認
        assert args.out_dir is None  # 既定：入力動画と同階層
        assert args.dump_trace is True  # デフォルトでCSV出力
        assert args.overlay is True  # デフォルトで画像出力

    def test_parse_all_args(self):
        """
        What: 全引数を指定してパース
        Why: 全フラグが正しく解析されることを保証
        """
        from cli.rep_cli import parse_args

        test_args = [
            '--video', '/path/to/video.mp4',
            '--out-dir', '/path/to/output',
            '--dump-trace', 'false',
            '--overlay', 'false'
        ]
        args = parse_args(test_args)

        assert args.video == '/path/to/video.mp4'
        assert args.out_dir == '/path/to/output'
        assert args.dump_trace is False
        assert args.overlay is False

    def test_help_flag(self):
        """
        What: --help フラグで使用方法を表示
        Why: ユーザーがフラグ一覧を確認できることを保証
        """
        from cli.rep_cli import parse_args

        # --help は SystemExit を raise する
        with pytest.raises(SystemExit) as exc_info:
            parse_args(['--help'])

        # exit code 0（正常終了）を期待
        assert exc_info.value.code == 0


class TestRepCLIInputValidation:
    """
    What: rep-cli の入力検証テスト
    Why: 異常系で適切にエラー化することを保証
    Design Decision: 明確なエラーメッセージ + 次アクション提示
    """

    def test_video_file_not_found(self):
        """
        What: 存在しない動画ファイルでエラー
        Why: 入力ファイル不在時に適切にエラー化
        """
        from cli.rep_cli import validate_input

        non_existent = Path('/non/existent/video.mp4')

        with pytest.raises(FileNotFoundError) as exc_info:
            validate_input(non_existent)

        # エラーメッセージに原因と次アクション含む
        error_msg = str(exc_info.value)
        assert 'video.mp4' in error_msg.lower()

    def test_video_file_unreadable(self):
        """
        What: 読み込み不可ファイルでエラー
        Why: 権限不足等で適切にエラー化
        """
        from cli.rep_cli import validate_input

        # 一時的に読み取り不可ファイルを作成（テスト環境依存）
        # NOTE: MVP段階では FileNotFoundError のみで可
        # 今後、権限チェックを追加する場合のプレースホルダー
        pass


class TestRepCLIErrorMessages:
    """
    What: エラーメッセージの具体性テスト
    Why: ユーザーが次アクションを判断できることを保証
    Design Decision: エラーメッセージ = 原因 + 次アクション提示
    """

    def test_error_message_includes_cause_and_action(self):
        """
        What: エラーメッセージに原因と次アクションを含む
        Why: ユーザーがエラー解決できることを保証
        """
        from cli.rep_cli import format_error_message

        error = FileNotFoundError("test.mp4")
        message = format_error_message(error)

        # 原因を含む
        assert 'test.mp4' in message or 'not found' in message.lower()

        # 次アクションを含む（例：パス確認、ファイル存在確認等）
        assert any(keyword in message.lower() for keyword in [
            'check', 'verify', 'ensure', 'provide', '確認'
        ])


class TestRepCLIPipeline:
    """
    What: rep-cli パイプライン処理テスト
    Why: pose抽出→評価→結果生成の統合処理を保証
    Design Decision: モック使用、実際の動画処理は統合テストで
    """

    def test_pipeline_returns_result_with_versions(self):
        """
        What: パイプライン実行結果に versions フィールド含む
        Why: versions必須出力を保証
        Design Decision: result.json スキーマ準拠
        """
        from cli.rep_cli import run_pipeline
        from unittest.mock import MagicMock

        # モック：ランドマークデータ
        mock_landmarks = [{'frame': 0, 'landmarks': []}]

        result = run_pipeline(
            landmarks_data=mock_landmarks,
            test_type='single_leg_squat'
        )

        # versions フィールド必須
        assert 'versions' in result
        assert 'rules_version' in result['versions']
        assert 'normalization_version' in result['versions']
        assert 'artifact_sha' in result['versions']

    def test_pipeline_returns_scores_and_class(self):
        """
        What: パイプライン実行結果に scores と class 含む
        Why: 判定結果の必須フィールドを保証
        """
        from cli.rep_cli import run_pipeline

        mock_landmarks = [{'frame': 0, 'landmarks': []}]

        result = run_pipeline(
            landmarks_data=mock_landmarks,
            test_type='single_leg_squat'
        )

        # 必須フィールド
        assert 'scores' in result
        assert 'class' in result
        assert 'class_prob' in result


class TestRepresentativeFrames:
    """
    What: 代表フレーム抽出ロジックテスト
    Why: best/worst/median フレーム選定の正確性を保証
    Design Decision: overall score ベースで抽出
    """

    def test_select_representative_frames_returns_three_frames(self):
        """
        What: 代表フレーム抽出で3枚のフレームを返す
        Why: best/worst/median の3枚必須
        """
        from cli.rep_cli import select_representative_frames

        # モック：評価結果（フレームごとのスコア）
        frame_scores = [
            {'frame_idx': 0, 'score': 10.0},
            {'frame_idx': 1, 'score': 50.0},
            {'frame_idx': 2, 'score': 90.0},  # best
            {'frame_idx': 3, 'score': 30.0},  # median (sorted: 5→10→30→50→90)
            {'frame_idx': 4, 'score': 5.0},   # worst
        ]

        result = select_representative_frames(frame_scores)

        # 3枚のフレームを返す
        assert 'best' in result
        assert 'worst' in result
        assert 'median' in result

        # 正しいインデックス
        assert result['best']['frame_idx'] == 2
        assert result['worst']['frame_idx'] == 4
        assert result['median']['frame_idx'] == 3  # sorted後の中央値

    def test_select_representative_frames_handles_single_frame(self):
        """
        What: 単一フレームの場合でも処理可能
        Why: 短い動画でもクラッシュしない
        """
        from cli.rep_cli import select_representative_frames

        frame_scores = [{'frame_idx': 0, 'score': 50.0}]

        result = select_representative_frames(frame_scores)

        # 全て同じフレーム
        assert result['best']['frame_idx'] == 0
        assert result['worst']['frame_idx'] == 0
        assert result['median']['frame_idx'] == 0
