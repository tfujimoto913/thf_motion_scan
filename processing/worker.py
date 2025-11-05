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
from aws_xray_sdk.core import xray_recorder

# PHASE 5: 構造化ロギング（JSON形式）
from .logger import (
    log_info,
    log_warning,
    log_error,
    log_processing_start,
    log_processing_complete,
    log_quality_check,
    log_qc_gate,
    emit_metric,
    set_processing_context,
)

from .pose_extractor import PoseExtractor
from .normalizer import BodyNormalizer
from .evaluators.single_leg_squat import SingleLegSquatEvaluator
from .evaluators.upper_body_swing import UpperBodySwingEvaluator
from .evaluators.skater_lunge import SkaterLungeEvaluator
from .evaluators.cross_step import CrossStepEvaluator
from .evaluators.stride_mimic import StrideMinicryEvaluator
from .evaluators.push_pull import PushPullEvaluator
from .evaluators.jump_landing import JumpLandingEvaluator
# PHASE B: v2評価器（8原則・560点満点システム）
from .evaluators_v2.single_leg_squat_v2 import SingleLegSquatEvaluatorV2
from .evaluators_v2.upper_body_swing_v2 import UpperBodySwingEvaluatorV2
from .evaluators_v2.skater_lunge_v2 import SkaterLungeEvaluatorV2
from .evaluators_v2.cross_step_v2 import CrossStepEvaluatorV2
from .evaluators_v2.stride_mimic_v2 import StrideMimicEvaluatorV2
from .evaluators_v2.push_pull_v2 import PushPullEvaluatorV2
from .evaluators_v2.jump_landing_v2 import JumpLandingEvaluatorV2
from .health_check import HealthChecker, apply_random_seed
from .quality_monitor import QualityMonitor
from .qc_gate import QCGate
from .exporters import CSVExporter, PNGPlotter, PDFReporter
from .rep_detection import detect_single_leg_squat_reps


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

        # PHASE A: scoring_system設定読み込み（並行動作環境）
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.scoring_version = config.get('scoring_system', {}).get('version', 'v1')
        self.validation_mode = config.get('scoring_system', {}).get('validation_mode', False)

        # PHASE CORE LOGIC: コンポーネント初期化
        self.pose_extractor = PoseExtractor()
        self.normalizer = BodyNormalizer()

        # PHASE A: v1（既存システム）のevaluators初期化
        # v2の場合でも一旦v1を初期化（validation_modeで両方使用）
        self.evaluators = {
            'single_leg_squat': SingleLegSquatEvaluator(config_path),
            'upper_body_swing': UpperBodySwingEvaluator(config_path),
            'skater_lunge': SkaterLungeEvaluator(config_path),
            'cross_step': CrossStepEvaluator(config_path),
            'stride_mimic': StrideMinicryEvaluator(config_path),
            'push_pull': PushPullEvaluator(config_path),
            'jump_landing': JumpLandingEvaluator(config_path)
        }

        # PHASE B: v2（新システム）のevaluators初期化（8原則・560点満点）
        # ADR-022, ADR-023: v2.1システム実装完了
        self.evaluators_v2 = {
            'single_leg_squat': SingleLegSquatEvaluatorV2(),
            'upper_body_swing': UpperBodySwingEvaluatorV2(),
            'skater_lunge': SkaterLungeEvaluatorV2(),
            'cross_step': CrossStepEvaluatorV2(),
            'stride_mimic': StrideMimicEvaluatorV2(),
            'push_pull': PushPullEvaluatorV2(),
            'jump_landing': JumpLandingEvaluatorV2()
        }

        self.health_checker = HealthChecker(config_path)
        self.quality_monitor = QualityMonitor(config_path)  # Phase 1: 品質モニタリング追加
        self.qc_gate = QCGate(Path("config") / "qc_gate.json")
        self.config_path = config_path
        self._last_context: Dict[str, Any] = {}

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

        set_processing_context(
            test_code=test_type,
            athlete_id=athlete_id,
            session_id=session_id,
        )

        # PHASE CORE LOGIC: ワークフロー実行
        # 1. ランドマーク抽出
        log_processing_start(str(video_path), test_type)

        extraction_result = self.pose_extractor.extract_landmarks(video_path)
        self._last_context = {
            "landmarks_sequence": extraction_result["landmarks"],
            "fps": extraction_result["fps"],
        }

        log_info(
            "Landmark extraction completed",
            test_type=test_type,
            context={
                "frame_count": extraction_result['frame_count'],
                "fps": round(extraction_result['fps'], 1),
                "duration": round(extraction_result['duration'], 1),
                "detected_frames": extraction_result['detected_frames']
            }
        )

        # CRITICAL: Health Check実行（ADR-004）
        # 2. ランドマーク品質チェック
        log_info("Quality check in progress", test_type=test_type)
        is_quality_ok, quality_result = self.health_checker.check_landmark_quality(
            extraction_result['landmarks'],
            video_path
        )

        # PHASE 1: 品質モニタリング実行
        log_info("Quality monitoring in progress", test_type=test_type)
        quality_metrics = self.quality_monitor.calculate_quality_metrics(
            extraction_result['landmarks'],
            total_frames=extraction_result['frame_count']
        )

        detection_rate = float(quality_result['detection_rate'])
        log_quality_check(
            detection_rate=detection_rate,
            quality_score=quality_metrics['quality_score'],
            test_type=test_type,
            passed=is_quality_ok and not quality_metrics['recommend_retake']
        )
        emit_metric("LandmarkDetectionRate", detection_rate * 100, unit="Percent")
        if not (is_quality_ok and not quality_metrics['recommend_retake']):
            emit_metric("LandmarkDetectionFailures", 1)

        # 3. 正規化（base_width計算）
        log_info("Landmark normalization in progress", test_type=test_type)
        representative_values, _frame_values = self.normalizer.normalize_landmarks_sequence(
            extraction_result['landmarks']
        )
        base_width = representative_values.get('base_width', 1.0)
        log_info(
            "Normalization completed",
            test_type=test_type,
            context={"base_width": round(base_width, 3)}
        )

        # 4. 評価（バージョン切り替え対応）
        log_info(
            "Evaluation in progress",
            test_type=test_type,
            context={"scoring_version": self.scoring_version}
        )

        # PHASE B: バージョン選択ロジック（ADR-022, ADR-023）
        with xray_recorder.in_subsegment('score_calculation') as subsegment:
            subsegment.put_annotation('scoringVersion', self.scoring_version)
            subsegment.put_annotation('testCode', test_type)
            if self.scoring_version in ['v2', 'v2.1']:
                # v2/v2.1: 8原則・560点満点評価システム
                evaluator = self.evaluators_v2[test_type]
                evaluation_result = evaluator.evaluate(
                    extraction_result['landmarks'],
                    base_width=base_width,
                    shoulder_width=representative_values.get('shoulder_width', 0.4),
                    leg_length=representative_values.get('leg_length', 0.9)
                )
                # CRITICAL: v2システムでは'total_score'を'score'にマッピング
                score = evaluation_result.get('total_score', 0)
                max_score = evaluation_result.get('max_possible', 80)
            else:
                # v1: 既存システム（7原則・12点満点）
                evaluator = self.evaluators[test_type]
                evaluation_result = evaluator.evaluate(
                    extraction_result['landmarks'],
                    base_width=base_width,
                    shoulder_width=representative_values.get('shoulder_width', 0.4),
                    leg_length=representative_values.get('leg_length', 1.0)
                )
                score = evaluation_result.get('total', 0)
                max_score = 12
            subsegment.put_metadata('score', score, 'motion_scan')
            subsegment.put_metadata('maxScore', max_score, 'motion_scan')

        log_processing_complete(
            test_type=test_type,
            score=round(score, 1),
            max_score=max_score
        )

        rep_detection = None
        if test_type == "single_leg_squat":
            rep_detection = detect_single_leg_squat_reps(
                extraction_result["landmarks"],
                fps=extraction_result["fps"],
            )
            if rep_detection and rep_detection.get("reps"):
                for rep in rep_detection["reps"]:
                    rep_index = int(rep.get("rep_index", len(rep_detection["reps"])))
                    rep["rep_id"] = f"{session_id}-{rep_index:03d}"

        # 5. 結果をまとめる
        qc_gate_result = None
        if self.qc_gate:
            qc_gate_result = self.qc_gate.evaluate(test_type, evaluation_result)
            log_qc_gate(
                test_type=test_type,
                passed=qc_gate_result["passed"],
                violations=qc_gate_result.get("violations"),
            )

        result = {
            'video_path': str(video_path),
            'test_type': test_type,
            'athlete_id': athlete_id,
            'session_id': session_id,
            'score': score,  # v1: 'total', v2: 'total_score'
            'max_score': max_score,  # v1: 12, v2: 80
            'evaluation': evaluation_result,
            'qc_gate': qc_gate_result or {"passed": True, "violations": []},
            'video_info': {
                'fps': extraction_result['fps'],
                'frame_count': extraction_result['frame_count'],
                'duration': extraction_result['duration'],
                'detected_frames': extraction_result['detected_frames']
            },
            'health_check': quality_result,
            'quality_metrics': quality_metrics,  # Phase 1: 品質メトリクス追加
            'rep_detection': rep_detection or {"series": [], "reps": []},
            'processed_at': datetime.now().isoformat()
        }

        # 6. 結果を保存（オプション）
        if output_dir:
            # CRITICAL: score.json保存（ADR-017）
            score_path = self._save_results(
                result, output_dir, athlete_id, session_id, test_type
            )
            result['score_file'] = str(score_path)
            log_info(
                "Results saved to score.json",
                test_type=test_type,
                context={"score_path": str(score_path)}
            )

            # CRITICAL: manifest.json更新（ADR-017）
            manifest_path = self._update_manifest(
                output_dir, athlete_id, session_id, test_type, result['score']
            )
            result['manifest_file'] = str(manifest_path)
            log_info(
                "Manifest updated",
                test_type=test_type,
                context={"manifest_path": str(manifest_path)}
            )

            # CRITICAL: warnings.json出力（ADR-004, ADR-017）
            warnings_dir = Path(output_dir) / 'processed' / athlete_id / session_id
            warnings_path = self.health_checker.save_warnings(
                str(warnings_dir / 'warnings.json')
            )
            log_info(
                "Warnings saved",
                test_type=test_type,
                context={"warnings_path": str(warnings_path)}
            )

            # PHASE 1: quality_log.json保存
            measurement_id = f"{athlete_id}_{session_id}_{test_type}"
            quality_log_path = self.quality_monitor.save_quality_log(
                extraction_result['landmarks'],
                output_path=str(warnings_dir / 'quality_log.json'),
                measurement_id=measurement_id,
                total_frames=extraction_result['frame_count']
            )
            result['quality_log_file'] = str(quality_log_path)
            log_info(
                "Quality log saved",
                test_type=test_type,
                context={"quality_log_path": str(quality_log_path)}
            )

            # PHASE CORE LOGIC: 出力形式エクスポート（ADR-011）
            if output_formats:
                exported_files = self._export_formats(result, output_dir, output_formats)
                result['exported_files'] = exported_files

        return result

    def get_last_context(self) -> Dict[str, Any]:
        """
        What: Return artifacts from the most recent process_video execution.
        Why: Downstream handlers (Lambda/CLI) use landmarks for overlay generation.
        Design Decision: Lightweight accessor instead of mutating result payloads.
        """
        return getattr(self, "_last_context", {})

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
                    log_info(
                        f"CSV export completed",
                        test_type=result['test_type'],
                        context={"filepath": filepath}
                    )

                elif fmt == 'png':
                    exporter = PNGPlotter(output_dir)
                    filepath = exporter.export(result, base_filename)
                    exported['png'] = filepath
                    log_info(
                        f"PNG export completed",
                        test_type=result['test_type'],
                        context={"filepath": filepath}
                    )

                elif fmt == 'pdf':
                    exporter = PDFReporter(output_dir)
                    filepath = exporter.export(result, base_filename)
                    exported['pdf'] = filepath
                    log_info(
                        f"PDF export completed",
                        test_type=result['test_type'],
                        context={"filepath": filepath}
                    )

                else:
                    log_warning(
                        f"Unsupported format: {fmt}",
                        test_type=result['test_type'],
                        context={"format": fmt}
                    )

            except Exception as e:
                log_error(
                    f"{fmt} export failed",
                    test_type=result['test_type'],
                    context={"format": fmt},
                    exc_info=e
                )

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
