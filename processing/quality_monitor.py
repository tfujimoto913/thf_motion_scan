"""
Purpose: MediaPipe検出品質のリアルタイム監視とquality_log.json生成
Responsibility: 品質メトリクス計算、品質スコア算出、再撮影推奨判定
Dependencies: json, config.json
Created: 2025-10-30 by Claude
Decision Log: Phase 1 - Motion Scan Quality Monitoring

CRITICAL: 既存のHealthCheckerに影響を与えない、非侵襲的実装
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class QualityMonitor:
    """
    What: MediaPipe検出品質モニタリングクラス
    Why: 計測中の品質をリアルタイムで監視し、低品質データを早期検知
    Design Decision: HealthCheckerとは独立、委譲パターンで統合予定（Phase 1 設計）

    CRITICAL: 既存のHealthCheckerとは別クラスとして実装（非侵襲的）
    """

    def __init__(self, config_path: str = 'config.json'):
        """
        What: config.json読み込みと閾値設定
        Why: 品質判定閾値の一元管理
        Design Decision: config.json使用、既存パターン踏襲

        Args:
            config_path: config.jsonのパス

        CRITICAL: 既存のHealthCheckerと同じconfig.jsonを共有
        """
        # PHASE CORE LOGIC: config.json読み込み
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"config.json not found: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        # PHASE CORE LOGIC: 閾値取得（Phase 1で定義）
        # visibility閾値（既存のHealthCheckerと同じ）
        self.visibility_threshold = self.config['thresholds'].get('confidence_min', 0.5)
        # フレーム欠損許容率（新規定義）
        self.frame_completeness_threshold = 0.9  # 90%以上で品質OK
        # 品質スコア閾値
        self.quality_score_threshold = 70  # 70点未満で再撮影推奨

    def calculate_quality_metrics(
        self,
        landmarks_data: List[Dict],
        total_frames: Optional[int] = None
    ) -> Dict:
        """
        What: ランドマークデータから品質メトリクスを計算
        Why: detection confidence, visibility, frame completenessを集約
        Design Decision: Phase 1ハンドオーバー仕様準拠

        Args:
            landmarks_data: フレームごとのランドマークデータ
            total_frames: 総フレーム数（指定なしの場合はlen(landmarks_data)）

        Returns:
            Dict: {
                'landmark_visibility_avg': float (0-1),
                'frame_completeness': float (0-1),
                'quality_score': int (0-100),
                'warnings': List[str],
                'recommend_retake': bool
            }

        CRITICAL: MediaPipeはvisibilityのみ提供（detection confidenceは取得不可）
        """
        # PHASE CORE LOGIC: エッジケース処理（空データ）
        if not landmarks_data:
            return {
                'landmark_visibility_avg': 0.0,
                'frame_completeness': 0.0,
                'quality_score': 0,
                'warnings': ['No landmark data available'],
                'recommend_retake': True
            }

        # PHASE CORE LOGIC: landmark visibility平均計算
        total_visibility = 0.0
        visibility_count = 0

        for frame_data in landmarks_data:
            landmarks = frame_data.get('landmarks', [])
            for lm in landmarks:
                visibility = lm.get('visibility', 0.0)
                total_visibility += visibility
                visibility_count += 1

        landmark_visibility_avg = (
            total_visibility / visibility_count if visibility_count > 0 else 0.0
        )

        # PHASE CORE LOGIC: frame completeness計算
        detected_frames = len(landmarks_data)
        if total_frames is None:
            total_frames = detected_frames

        frame_completeness = (
            detected_frames / total_frames if total_frames > 0 else 0.0
        )

        # PHASE CORE LOGIC: 品質スコア計算（Phase 1ハンドオーバー仕様）
        # quality_score = (visibility * 40 + completeness * 60) * 100
        quality_score = int(
            (landmark_visibility_avg * 0.4 + frame_completeness * 0.6) * 100
        )

        # PHASE CORE LOGIC: 警告生成
        warnings = []
        if landmark_visibility_avg < self.visibility_threshold:
            warnings.append('Low landmark visibility')
        if frame_completeness < self.frame_completeness_threshold:
            warnings.append('High frame loss rate')

        # PHASE CORE LOGIC: 再撮影推奨判定
        recommend_retake = quality_score < self.quality_score_threshold

        return {
            'landmark_visibility_avg': float(landmark_visibility_avg),
            'frame_completeness': float(frame_completeness),
            'quality_score': quality_score,
            'warnings': warnings,
            'recommend_retake': recommend_retake
        }

    def save_quality_log(
        self,
        landmarks_data: List[Dict],
        output_path: str,
        measurement_id: str,
        total_frames: Optional[int] = None
    ) -> Path:
        """
        What: quality_log.jsonを生成して保存
        Why: 計測ごとの品質メトリクスを記録
        Design Decision: Phase 1ハンドオーバーのJSON構造準拠

        Args:
            landmarks_data: フレームごとのランドマークデータ
            output_path: 出力先JSONファイルパス
            measurement_id: 計測ID
            total_frames: 総フレーム数

        Returns:
            Path: 保存したquality_log.jsonのパス

        CRITICAL: S3保存時にもこの形式を使用（Phase 3で実装）
        """
        # PHASE CORE LOGIC: 品質メトリクス計算
        metrics = self.calculate_quality_metrics(landmarks_data, total_frames)

        # PHASE CORE LOGIC: quality_log.json構造生成（Phase 1仕様）
        quality_log = {
            'measurement_id': measurement_id,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'quality_metrics': {
                'landmark_visibility_avg': metrics['landmark_visibility_avg'],
                'frame_completeness': metrics['frame_completeness'],
                'quality_score': metrics['quality_score'],
                'warnings': metrics['warnings'],
                'recommend_retake': metrics['recommend_retake']
            }
        }

        # PHASE CORE LOGIC: JSON保存
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(quality_log, f, indent=2, ensure_ascii=False)

        return output_file
