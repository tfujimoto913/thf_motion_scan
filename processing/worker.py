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
from .evaluators.single_leg_squat import SingleLegSquatEvaluator
from .evaluators.upper_body_swing import UpperBodySwingEvaluator
from .evaluators.skater_lunge import SkaterLungeEvaluator
from .evaluators.cross_step import CrossStepEvaluator
from .evaluators.stride_mimic import StrideMimicEvaluator
from .evaluators.push_pull import PushPullEvaluator
from .evaluators.jump_landing import JumpLandingEvaluator
from .health_check import HealthChecker, apply_random_seed


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
        self.evaluators = {
            'single_leg_squat': SingleLegSquatEvaluator(config_path),
            'upper_body_swing': UpperBodySwingEvaluator(config_path),
            'skater_lunge': SkaterLungeEvaluator(config_path),
            'cross_step': CrossStepEvaluator(config_path),
            'stride_mimic': StrideMimicEvaluator(config_path),
            'push_pull': PushPullEvaluator(config_path),
            'jump_landing': JumpLandingEvaluator(config_path)
        }
        self.health_checker = HealthChecker(config_path)
        self.config_path = config_path

    def process_video(self,
                      video_path: str,
                      test_type: str = 'single_leg_squat',
                      output_dir: Optional[str] = None) -> Dict:
        """
        What: 動画処理メイン処理（抽出→品質チェック→評価→保存）
        Why: 統合ワークフロー実行
        Design Decision: Health Check統合、warnings.json自動出力（ADR-004）

        Args:
            video_path: 動画ファイルのパス
            test_type: テストタイプ（現在は'single_leg_squat'のみ）
            output_dir: 結果を保存するディレクトリ（Noneの場合は保存しない）

        Returns:
            Dict: {
                'video_path': str,
                'test_type': str,
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

        # 3. 評価
        print(f"📈 評価を実行中...")
        evaluator = self.evaluators[test_type]
        evaluation_result = evaluator.evaluate(extraction_result['landmarks'])

        print(f"✅ 評価完了: スコア {evaluation_result['score']}/3")

        # 4. 結果をまとめる
        result = {
            'video_path': str(video_path),
            'test_type': test_type,
            'score': evaluation_result['score'],
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

        # 5. 結果を保存（オプション）
        if output_dir:
            output_path = self._save_results(result, output_dir)
            result['output_file'] = str(output_path)
            print(f"💾 結果を保存: {output_path}")

            # CRITICAL: warnings.json出力（ADR-004）
            warnings_path = self.health_checker.save_warnings(
                str(Path(output_dir) / 'warnings.json')
            )
            print(f"📋 警告ログ保存: {warnings_path}")

        return result

    def _save_results(self, result: Dict, output_dir: str) -> Path:
        """
        What: 評価結果JSON保存
        Why: 結果永続化と後続処理での参照
        Design Decision: タイムスタンプ付きファイル名（ADR-002）

        Args:
            result: 結果データ
            output_dir: 出力ディレクトリ

        Returns:
            Path: 保存したファイルのパス

        CRITICAL: 個人情報含む場合は匿名化処理後に保存
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{result['test_type']}_{timestamp}.json"
        filepath = output_path / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        return filepath

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
        summary += f"スコア: {result['score']}/3\n"

        # PHASE CORE LOGIC: Health Check結果追加（ADR-004）
        if 'health_check' in result:
            hc = result['health_check']
            summary += f"\n品質チェック:\n"
            summary += f"  検出率: {hc['detection_rate']:.1%}\n"
            summary += f"  品質: {'OK' if hc['is_quality_ok'] else '低品質'}\n"

        summary += f"\n{result['evaluation']['details']}\n"
        summary += "=" * 60 + "\n"

        return summary


def process_video(video_path: str,
                  test_type: str = 'single_leg_squat',
                  output_dir: Optional[str] = None) -> Dict:
    """
    動画を処理する便利関数

    Args:
        video_path: 動画ファイルのパス
        test_type: テストタイプ
        output_dir: 結果を保存するディレクトリ

    Returns:
        Dict: 処理結果
    """
    worker = VideoProcessingWorker()
    return worker.process_video(video_path, test_type, output_dir)
