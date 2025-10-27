"""
Purpose: 動画処理のメインワークフロー管理
Responsibility: ランドマーク抽出→評価→Health Check→結果保存の統合処理
Dependencies: pose_extractor, evaluators, health_check, config.json
Created: 2025-10-19 by Claude
Decision Log: ADR-002, ADR-004

CRITICAL: Health Check必須実行、warnings.json出力必須
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

from .pose_extractor import PoseExtractor
from .normalizer import BodyNormalizer
from .evaluators.single_leg_squat import SingleLegSquatEvaluator
from .evaluators.upper_body_swing import UpperBodySwingEvaluator
from .evaluators.skater_lunge import SkaterLungeEvaluator
from .evaluators.cross_step import CrossStepEvaluator
from .evaluators.stride_mimic import StrideMinicryEvaluator
from .evaluators.push_pull import PushPullEvaluator
from .evaluators.jump_landing import JumpLandingEvaluator
from .health_check import HealthChecker, apply_random_seed
from .exporters import CSVExporter, PNGPlotter, PDFReporter


class VideoProcessingWorker:
    """
    What: 動画処理ワークフロー管理クラス
    Why: ランドマーク抽出から評価までの統合処理
    Design Decision: Health Check統合、warnings.json自動出力（ADR-004）

    CRITICAL: 初期化時にrandom_seed適用必須
    """

    def __init__(self, config_path: str = 'config.json'):
        """
        What: 各コンポーネント初期化とrandom_seed適用
        Why: 再現性保証、データ整合性確保（ADR-004）
        Design Decision: config_path一元化

        Args:
            config_path: config.jsonのパス

        CRITICAL: random_seed適用必須（data_integrity準拠）
        """
        # CRITICAL: random_seed適用（ADR-004）
        apply_random_seed(config_path)

        # PHASE CORE LOGIC: コンポーネント初期化
        self.pose_extractor = PoseExtractor()
        self.normalizer = BodyNormalizer()
        self.evaluators = {
            'single_leg_squat': SingleLegSquatEvaluator(config_path),
            'upper_body_swing': UpperBodySwingEvaluator(config_path),
            'skater_lunge': SkaterLungeEvaluator(config_path),
            'cross_step': CrossStepEvaluator(config_path),
            'stride_mimic': StrideMinicryEvaluator(config_path),
            'push_pull': PushPullEvaluator(config_path),
            'jump_landing': JumpLandingEvaluator(config_path)
        }
        self.health_checker = HealthChecker(config_path)
        self.config_path = config_path

    def process_video(self,
                      video_path: str,
                      test_type: str = 'single_leg_squat',
                      athlete_id: Optional[str] = None,
                      session_id: Optional[str] = None,
                      output_dir: Optional[str] = None,
                      output_formats: Optional[list] = None) -> Dict:
        """
        What: 動画処理メイン処理（抽出→品質チェック→評価→保存）
        Why: 統合ワークフロー実行
        Design Decision: Health Check統合、warnings.json自動出力（ADR-004）、標準出力形式（ADR-017）

        Args:
            video_path: 動画ファイルのパス
            test_type: テストタイプ（現在は'single_leg_squat'のみ）
            athlete_id: アスリートID（例: TaroYamada-100315）、Noneの場合は自動生成
            session_id: セッションID（例: 20251012-0915-A）、Noneの場合は自動生成
            output_dir: 結果を保存するディレクトリ（Noneの場合は保存しない）
            output_formats: 出力形式リスト (['csv', 'png', 'pdf'] から選択、デフォルト None）

        Returns:
            Dict: {
                'video_path': str,
                'test_type': str,
                'athlete_id': str,
                'session_id': str,
                'score': int,
                'evaluation': Dict,
                'video_info': Dict,
                'health_check': Dict,
                'processed_at': str
            }

        Raises:
            ValueError: サポートされていないテストタイプの場合
            FileNotFoundError: 動画ファイルが存在しない場合

        CRITICAL: Health Check必須、低品質データは警告出力
        """
        # 動画ファイルの存在確認
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"動画ファイルが見つかりません: {video_path}")

        # テストタイプの確認
        if test_type not in self.evaluators:
            raise ValueError(
                f"サポートされていないテストタイプ: {test_type}. "
                f"利用可能なタイプ: {list(self.evaluators.keys())}"
            )

        # CRITICAL: athlete_id/session_idのデフォルト値生成（ADR-017）
        if athlete_id is None:
            athlete_id = f"Unknown-{datetime.now().strftime('%y%m%d')}"

        if session_id is None:
            session_id = datetime.now().strftime('%Y%m%d-%H%M-X')

        # PHASE CORE LOGIC: ワークフロー実行
        # 1. ランドマーク抽出
        print(f"🎥 動画を解析中: {video_path}")
        print(f"📋 テストタイプ: {test_type}")

        extraction_result = self.pose_extractor.extract_landmarks(video_path)

        print(f"📊 動画情報: {extraction_result['frame_count']}フレーム, "
              f"{extraction_result['fps']:.1f}fps, "
              f"{extraction_result['duration']:.1f}秒")
        print(f"✅ ランドマーク抽出完了: {extraction_result['detected_frames']}フレーム検出")

        # CRITICAL: Health Check実行（ADR-004）
        # 2. ランドマーク品質チェック
        print(f"🔍 品質チェック実行中...")
        is_quality_ok, quality_result = self.health_checker.check_landmark_quality(
            extraction_result['landmarks'],
            video_path
        )

        if is_quality_ok:
            print(f"✅ 品質チェック完了: OK (検出率 {quality_result['detection_rate']:.1%})")
        else:
            print(f"⚠️  品質チェック: 低品質データ検出 (検出率 {quality_result['detection_rate']:.1%})")

        # 3. 正規化（base_width計算）
        print(f"📏 ランドマーク正規化中...")
        representative_values, _frame_values = self.normalizer.normalize_landmarks_sequence(
            extraction_result['landmarks']
        )
        base_width = representative_values.get('base_width', 1.0)
        print(f"✅ 正規化完了: base_width={base_width:.3f}")

        # 4. 評価
        print(f"📈 評価を実行中...")
        evaluator = self.evaluators[test_type]
        evaluation_result = evaluator.evaluate(
            extraction_result['landmarks'],
            base_width=base_width
        )

        print(f"✅ 評価完了: スコア {evaluation_result['total']}/12")

        # 5. 結果をまとめる
        result = {
            'video_path': str(video_path),
            'test_type': test_type,
            'athlete_id': athlete_id,
            'session_id': session_id,
            'score': evaluation_result.get('total', evaluation_result.get('score', 0)),
            'evaluation': evaluation_result,
            'video_info': {
                'fps': extraction_result['fps'],
                'frame_count': extraction_result['frame_count'],
                'duration': extraction_result['duration'],
                'detected_frames': extraction_result['detected_frames']
            },
            'health_check': quality_result,
            'processed_at': datetime.now().isoformat()
        }

        # 6. 結果を保存（オプション）
        if output_dir:
            # CRITICAL: score.json保存（ADR-017）
            score_path = self._save_results(
                result, output_dir, athlete_id, session_id, test_type
            )
            result['score_file'] = str(score_path)
            print(f"💾 score.json保存: {score_path}")

            # CRITICAL: manifest.json更新（ADR-017）
            manifest_path = self._update_manifest(
                output_dir, athlete_id, session_id, test_type, result['score']
            )
            result['manifest_file'] = str(manifest_path)
            print(f"📋 manifest.json更新: {manifest_path}")

            # CRITICAL: warnings.json出力（ADR-004, ADR-017）
            warnings_dir = Path(output_dir) / 'processed' / athlete_id / session_id
            warnings_path = self.health_checker.save_warnings(
                str(warnings_dir / 'warnings.json')
            )
            print(f"⚠️  warnings.json保存: {warnings_path}")

            # PHASE CORE LOGIC: 出力形式エクスポート（ADR-011）
            if output_formats:
                exported_files = self._export_formats(result, output_dir, output_formats)
                result['exported_files'] = exported_files

        return result

    def _export_formats(self, result: Dict, output_dir: str, formats: list) -> Dict[str, str]:
        """
        What: 複数形式でエクスポート
        Why: CSV/PNG/PDF形式での出力をサポート
        Design Decision: フォーマットごとにエクスポーター使用（ADR-011）

        Args:
            result: 評価結果
            output_dir: 出力ディレクトリ
            formats: 出力形式リスト (['csv', 'png', 'pdf'])

        Returns:
            Dict[str, str]: {format: filepath} の辞書

        CRITICAL: 不正な形式は無視して続行
        """
        exported = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_filename = f"{result['test_type']}_{timestamp}"

        # PHASE CORE LOGIC: 各形式でエクスポート
        for fmt in formats:
            try:
                if fmt == 'csv':
                    exporter = CSVExporter(output_dir)
                    filepath = exporter.export(result, base_filename)
                    exported['csv'] = filepath
                    print(f"📄 CSV出力: {filepath}")

                elif fmt == 'png':
                    exporter = PNGPlotter(output_dir)
                    filepath = exporter.export(result, base_filename)
                    exported['png'] = filepath
                    print(f"📊 PNG出力: {filepath}")

                elif fmt == 'pdf':
                    exporter = PDFReporter(output_dir)
                    filepath = exporter.export(result, base_filename)
                    exported['pdf'] = filepath
                    print(f"📋 PDF出力: {filepath}")

                else:
                    print(f"⚠️  未サポート形式: {fmt}")

            except Exception as e:
                print(f"❌ {fmt}エクスポート失敗: {e}")

        return exported

    def _update_manifest(self, output_dir: str, athlete_id: str,
                         session_id: str, test_code: str, score: int) -> Path:
        """
        What: manifest.json更新（セッションサマリー）
        Why: セッション全体の結果集約
        Design Decision: テスト実行ごとに更新（ADR-017）

        Args:
            output_dir: ベース出力ディレクトリ
            athlete_id: アスリートID
            session_id: セッションID
            test_code: テストコード
            score: テストスコア

        Returns:
            Path: manifest.jsonのパス

        CRITICAL: 既存manifest.jsonがあれば読み込んで更新
        """
        # PHASE CORE LOGIC: パス構造 /processed/{athlete_id}/{session_id}/
        manifest_dir = Path(output_dir) / 'processed' / athlete_id / session_id
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = manifest_dir / 'manifest.json'

        # 既存manifest読み込み
        if manifest_path.exists():
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
        else:
            # CRITICAL: 新規manifest作成（ADR-017仕様準拠）
            manifest = {
                'athlete_id': athlete_id,
                'session_id': session_id,
                'summary': {
                    'stability': 0.0,
                    'dissociation': 0.0,
                    'coordination': 0.0,
                    'synergy': 0.0
                },
                'tests': [],
                'weakness_tags': [],
                'version': 'scan-v1.0.0',
                'created_at': datetime.now().isoformat() + 'Z'
            }

        # PHASE CORE LOGIC: テスト結果追加/更新
        test_entry = {'test_code': test_code, 'score': score}

        # 既存テスト結果を更新
        updated = False
        for i, t in enumerate(manifest['tests']):
            if t['test_code'] == test_code:
                manifest['tests'][i] = test_entry
                updated = True
                break

        if not updated:
            manifest['tests'].append(test_entry)

        # TODO: summaryとweakness_tagsの計算ロジック実装
        # 現在はプレースホルダー値を保持

        # 保存
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        return manifest_path

    def _extract_metrics(self, evaluation: Dict) -> Dict:
        """
        What: evaluation結果からmetricsを抽出
        Why: score.jsonのmetricsフィールド生成用
        Design Decision: 各evaluatorの出力形式に応じて変換（ADR-017）

        Args:
            evaluation: evaluatorの出力結果

        Returns:
            Dict: metrics辞書

        CRITICAL: 単位付きキー名使用（例: pelvic_tilt_std_deg）
        """
        # PHASE CORE LOGIC: evaluationから主要なメトリックを抽出
        # TODO: 各evaluatorの出力形式に応じて実装を拡張
        metrics = {}

        # デバッグ用：evaluation全体を含める（将来的に詳細化）
        if 'details' in evaluation:
            metrics['evaluation_details'] = evaluation['details']

        return metrics

    def _extract_flags(self, evaluation: Dict) -> list:
        """
        What: evaluation結果からflagsを抽出
        Why: score.jsonのflagsフィールド生成用
        Design Decision: 閾値超過項目を自動検出（ADR-017）

        Args:
            evaluation: evaluatorの出力結果

        Returns:
            list: フラグリスト

        CRITICAL: 標準フラグ名使用（pelvic_instability等）
        """
        # PHASE CORE LOGIC: 閾値超過検出ロジック
        # TODO: 将来的に各evaluatorの閾値情報を使用して自動検出
        flags = []

        return flags

    def _save_results(self, result: Dict, output_dir: str,
                      athlete_id: str, session_id: str, test_code: str) -> Path:
        """
        What: score.json保存（標準パス構造）
        Why: Notion仕様書準拠の出力形式統一
        Design Decision: /processed/{athlete_id}/{session_id}/{test_code}/score.json（ADR-017）

        Args:
            result: 評価結果
            output_dir: ベース出力ディレクトリ
            athlete_id: アスリートID
            session_id: セッションID
            test_code: テストコード

        Returns:
            Path: 保存したscore.jsonのパス

        CRITICAL: test_code は実装コード使用（single_leg_squat等）
        """
        # PHASE CORE LOGIC: パス構造 /processed/{athlete_id}/{session_id}/{test_code}/
        score_dir = Path(output_dir) / 'processed' / athlete_id / session_id / test_code
        score_dir.mkdir(parents=True, exist_ok=True)

        # CRITICAL: score.json作成（ADR-017仕様準拠）
        score_data = {
            'athlete_id': athlete_id,
            'session_id': session_id,
            'test_code': test_code,
            'score': result['score'],
            'metrics': self._extract_metrics(result['evaluation']),
            'flags': self._extract_flags(result['evaluation']),
            'version': 'scan-v1.0.0',
            'created_at': datetime.now().isoformat() + 'Z'
        }

        score_path = score_dir / 'score.json'
        with open(score_path, 'w', encoding='utf-8') as f:
            json.dump(score_data, f, indent=2, ensure_ascii=False)

        return score_path

    def get_summary(self, result: Dict) -> str:
        """
        What: 評価結果サマリー生成
        Why: コンソール出力用の可読性向上
        Design Decision: health_check結果も含める（ADR-004）

        Args:
            result: process_videoの結果

        Returns:
            str: サマリー文字列

        CRITICAL: 個人情報除外済み前提
        """
        summary = "=" * 60 + "\n"
        summary += "📊 評価結果サマリー\n"
        summary += "=" * 60 + "\n"
        summary += f"テストタイプ: {result['test_type']}\n"
        summary += f"スコア: {result['score']}/12\n"  # ADR-016: 12点満点システム

        # PHASE CORE LOGIC: Health Check結果追加（ADR-004）
        if 'health_check' in result:
            hc = result['health_check']
            summary += f"\n品質チェック:\n"
            summary += f"  検出率: {hc['detection_rate']:.1%}\n"
            summary += f"  品質: {'OK' if hc['is_quality_ok'] else '低品質'}\n"

        # ADR-016: 12点満点システム（execution + principles構造）
        evaluation = result['evaluation']
        if 'details' in evaluation:
            summary += f"\n{evaluation['details']}\n"
        else:
            # 12点満点システムのサマリー
            summary += f"\nExecution: {evaluation.get('execution', {}).get('total', 0):.1f}/3\n"
            summary += f"Principles: {evaluation.get('principles', {}).get('total', 0):.1f}/9\n"

        summary += "=" * 60 + "\n"

        return summary


def process_video(video_path: str,
                  test_type: str = 'single_leg_squat',
                  athlete_id: Optional[str] = None,
                  session_id: Optional[str] = None,
                  output_dir: Optional[str] = None,
                  output_formats: Optional[list] = None) -> Dict:
    """
    動画を処理する便利関数

    Args:
        video_path: 動画ファイルのパス
        test_type: テストタイプ
        athlete_id: アスリートID（例: TaroYamada-100315）、Noneの場合は自動生成
        session_id: セッションID（例: 20251012-0915-A）、Noneの場合は自動生成
        output_dir: 結果を保存するディレクトリ
        output_formats: 出力形式リスト (['csv', 'png', 'pdf'])

    Returns:
        Dict: 処理結果
    """
    worker = VideoProcessingWorker()
    return worker.process_video(
        video_path, test_type, athlete_id, session_id, output_dir, output_formats
    )
