"""
Purpose: データ品質検証とエラー集約管理（Health Check）
Responsibility: ランドマーク品質チェック、warnings.json出力、再現性保証
Dependencies: numpy, json, config.json
Created: 2025-10-19 by Claude
Decision Log: ADR-004

CRITICAL: 個人情報・環境変数をwarnings.jsonに記録禁止、random_seed必須適用
"""
import numpy as np
import json
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple


class HealthChecker:
    """
    What: データ品質検証とエラー集約クラス
    Why: 三層防御の検知層強化、データ整合性保証
    Design Decision: config.json閾値参照、warnings.json集約出力（ADR-004）

    CRITICAL: 個人情報（Face/Name/Path）をログ出力禁止
    """

    def __init__(self, config_path: str = 'config.json'):
        """
        What: config.json読み込みとrandom_seed適用
        Why: 検証閾値一元管理、再現性保証（ADR-004）
        Design Decision: 初期化時にrandom_seed設定

        Args:
            config_path: config.jsonのパス

        CRITICAL: random_seed適用必須（データ整合性ルール準拠）
        """
        # PHASE CORE LOGIC: config.json読み込み
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"config.json not found: {config_path}")

        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        # CRITICAL: random_seed適用（再現性保証、ADR-004）
        seed = self.config['data_integrity']['random_seed']
        random.seed(seed)
        np.random.seed(seed)

        # 閾値取得
        self.confidence_min = self.config['thresholds']['confidence_min']
        self.frame_skip_tolerance = self.config['thresholds']['frame_skip_tolerance']

        # warnings履歴
        self.warnings: List[Dict] = []

    def check_landmark_quality(
        self,
        landmarks_data: List[Dict],
        video_path: Optional[str] = None
    ) -> Tuple[bool, Dict]:
        """
        What: ランドマーク品質検証（visibility閾値、フレームスキップ許容）
        Why: 低品質データの早期検出、評価精度向上
        Design Decision: config.json閾値参照でチェック（ADR-004）

        Args:
            landmarks_data: フレームごとのランドマークデータ
            video_path: 動画パス（警告記録用、個人情報除外処理あり）

        Returns:
            Tuple[bool, Dict]:
                - 品質OK: True/False
                - 詳細: {'total_frames': int, 'detected_frames': int, ...}

        CRITICAL: video_pathは匿名化してwarnings.json記録
        """
        total_frames = len(landmarks_data)
        detected_frames = 0
        low_visibility_frames = 0
        low_visibility_landmarks = []

        # PHASE CORE LOGIC: visibility品質チェック
        for frame_data in landmarks_data:
            landmarks = frame_data.get('landmarks', [])
            if not landmarks:
                continue

            detected_frames += 1
            frame_idx = frame_data.get('frame', -1)

            # 各ランドマークのvisibility確認
            low_vis_count = 0
            for lm_idx, lm in enumerate(landmarks):
                visibility = lm.get('visibility', 0.0)
                if visibility < self.confidence_min:
                    low_vis_count += 1
                    low_visibility_landmarks.append({
                        'frame': frame_idx,
                        'landmark_idx': lm_idx,
                        'visibility': float(visibility)
                    })

            # フレーム内の低visibility割合
            if landmarks and (low_vis_count / len(landmarks)) > 0.3:
                low_visibility_frames += 1

        # フレームスキップ許容チェック
        detection_rate = detected_frames / total_frames if total_frames > 0 else 0
        skip_rate = 1.0 - detection_rate

        # CRITICAL: frame_skip_tolerance検証（ADR-004）
        # CRITICAL: total_frames=0の場合はis_quality_ok=False
        if total_frames == 0:
            is_quality_ok = False
        else:
            is_quality_ok = (
                skip_rate <= (self.frame_skip_tolerance / total_frames) and
                (low_visibility_frames / total_frames) < 0.2
            )

        result = {
            'total_frames': total_frames,
            'detected_frames': detected_frames,
            'detection_rate': float(detection_rate),
            'low_visibility_frames': low_visibility_frames,
            'low_visibility_landmarks_count': len(low_visibility_landmarks),
            'is_quality_ok': is_quality_ok
        }

        # 品質NGの場合はwarning記録
        if not is_quality_ok:
            # SECURITY REQUIREMENT: video_path匿名化
            anonymized_path = self._anonymize_path(video_path) if video_path else "unknown"
            self._add_warning(
                level='WARNING',
                message='低品質ランドマークデータ検出',
                details={
                    'video': anonymized_path,
                    'detection_rate': float(detection_rate),
                    'low_visibility_frames_ratio': float(low_visibility_frames / total_frames) if total_frames > 0 else 0
                }
            )

        return is_quality_ok, result

    def validate_config(self) -> Tuple[bool, List[str]]:
        """
        What: config.json整合性検証
        Why: 設定不備による実行時エラー防止
        Design Decision: 必須キー存在確認、閾値範囲チェック（ADR-004）

        Returns:
            Tuple[bool, List[str]]:
                - 検証OK: True/False
                - エラーメッセージリスト

        CRITICAL: random_seed存在必須
        """
        errors = []

        # PHASE CORE LOGIC: 必須キー確認
        required_keys = [
            ('thresholds', 'confidence_min'),
            ('thresholds', 'frame_skip_tolerance'),
            ('data_integrity', 'random_seed'),
            ('data_integrity', 'nan_handling')
        ]

        for keys in required_keys:
            obj = self.config
            for key in keys:
                if key not in obj:
                    errors.append(f"Missing required config key: {'.'.join(keys)}")
                    break
                obj = obj[key]

        # 閾値範囲チェック
        if 'confidence_min' in self.config.get('thresholds', {}):
            conf_min = self.config['thresholds']['confidence_min']
            if not (0.0 <= conf_min <= 1.0):
                errors.append(f"Invalid confidence_min: {conf_min} (must be 0.0-1.0)")

        # random_seed型チェック
        if 'random_seed' in self.config.get('data_integrity', {}):
            seed = self.config['data_integrity']['random_seed']
            if not isinstance(seed, int):
                errors.append(f"Invalid random_seed type: {type(seed)} (must be int)")

        is_valid = len(errors) == 0

        if not is_valid:
            self._add_warning(
                level='ERROR',
                message='config.json検証エラー',
                details={'errors': errors}
            )

        return is_valid, errors

    def save_warnings(self, output_path: str = 'warnings.json') -> Path:
        """
        What: warnings.json出力
        Why: エラー集約管理、デバッグ効率化
        Design Decision: タイムスタンプ付き、個人情報除外（ADR-004）

        Args:
            output_path: 出力ファイルパス

        Returns:
            Path: 保存したファイルパス

        CRITICAL: 環境変数・個人情報を含めない
        """
        # PHASE CORE LOGIC: warnings.json生成
        output_file = Path(output_path)

        warnings_data = {
            'generated_at': datetime.now().isoformat(),
            'total_warnings': len(self.warnings),
            'warnings': self.warnings,
            'config_summary': {
                'confidence_min': self.confidence_min,
                'frame_skip_tolerance': self.frame_skip_tolerance,
                'random_seed': self.config['data_integrity']['random_seed']
            }
        }

        # SECURITY REQUIREMENT: 環境変数除外確認
        # （現状、config.jsonに環境変数なし。将来Azure連携時に注意）

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(warnings_data, f, indent=2, ensure_ascii=False)

        return output_file

    def _add_warning(self, level: str, message: str, details: Optional[Dict] = None):
        """
        What: warning記録
        Why: エラー履歴追跡
        Design Decision: タイムスタンプ付きで履歴保持（ADR-004）

        Args:
            level: WARNING/ERROR
            message: エラーメッセージ
            details: 詳細情報（個人情報除外済み前提）

        CRITICAL: details内に個人情報含まないこと
        """
        warning = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }

        if details:
            warning['details'] = details

        self.warnings.append(warning)

    def _anonymize_path(self, path: Optional[str]) -> str:
        """
        What: ファイルパス匿名化
        Why: 個人情報（ユーザー名等）をログから除外
        Design Decision: ファイル名のみ保持、パスは除外（ADR-004）

        Args:
            path: 元のファイルパス

        Returns:
            str: 匿名化パス（ファイル名のみ）

        CRITICAL: フルパスをwarnings.jsonに記録禁止
        """
        if not path:
            return "unknown"

        # SECURITY REQUIREMENT: ファイル名のみ抽出
        return Path(path).name

    def get_warnings_summary(self) -> Dict:
        """
        What: warnings集約サマリー
        Why: エラー傾向分析
        Design Decision: レベル別カウント（ADR-004）

        Returns:
            Dict: {'total': int, 'ERROR': int, 'WARNING': int}

        CRITICAL: 個人情報含まないこと
        """
        summary = {
            'total': len(self.warnings),
            'ERROR': 0,
            'WARNING': 0
        }

        for warning in self.warnings:
            level = warning.get('level', 'WARNING')
            if level in summary:
                summary[level] += 1

        return summary


def apply_random_seed(config_path: str = 'config.json'):
    """
    What: random_seed適用ヘルパー関数
    Why: HealthChecker外でも再現性保証
    Design Decision: グローバル関数でseed設定（ADR-004）

    Args:
        config_path: config.jsonのパス

    CRITICAL: 全処理開始前に必ず実行
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    seed = config['data_integrity']['random_seed']
    random.seed(seed)
    np.random.seed(seed)
