"""
Purpose: 8原則・237点満点評価システムの抽象基底クラス
Responsibility: 新評価体系の共通インターフェース定義
Dependencies: test_rules_v2.json
Created: 2025-10-30 by Claude
Decision Log: Phase A - 並行動作環境構築

CRITICAL: Phase Aでは雛形のみ、Phase Bで実装追加
"""
from abc import ABC, abstractmethod
from typing import Dict, List
from pathlib import Path
import json


class BaseEvaluatorV2(ABC):
    """
    What: 8原則（B1-B8）・237点満点評価システムの基底クラス
    Why: 新評価体系の共通インターフェースを統一
    Design Decision: 並行動作方式、既存BaseEvaluatorとは完全分離

    CRITICAL: 既存のBaseEvaluatorには一切影響を与えない
    """

    def __init__(self, config_path: str = 'processing/evaluators_v2/config_v2/test_rules_v2.json'):
        """
        What: 8原則ルール読み込み
        Why: 237点満点システムの定義を取得
        Design Decision: test_rules_v2.json使用

        Args:
            config_path: test_rules_v2.jsonのパス

        CRITICAL: Phase Bで実装、Phase Aではプレースホルダー
        """
        self.config_path = Path(config_path)

        # PHASE A: プレースホルダー（Phase Bで実装）
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.rules = json.load(f)
        else:
            # Phase Aではファイルがまだ存在しないため、空の構造
            self.rules = {
                'version': 'v2.0',
                'total_score': 237,
                'principles': {}
            }

    @abstractmethod
    def evaluate(
        self,
        landmarks_data: List[Dict],
        **kwargs
    ) -> Dict:
        """
        What: 評価実行メソッド（抽象メソッド）
        Why: サブクラスで具体的な評価ロジックを実装
        Design Decision: 8原則・局面別評価に対応

        Args:
            landmarks_data: フレームごとのランドマークデータ
            **kwargs: 追加パラメータ（base_width, shoulder_width, leg_length等）

        Returns:
            Dict: {
                'version': 'v2',
                'total_score': int (0-237),
                'section_a': Dict,  # 21点
                'section_b': Dict,  # 216点（8原則）
                'phase_scores': Dict,  # Eccentric/Concentric別
                'details': str
            }

        CRITICAL: Phase Bで実装、Phase Aでは NotImplementedError
        """
        raise NotImplementedError(
            "Phase B で実装予定: 8原則・237点満点評価ロジック"
        )

    def _detect_phases(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: 局面検出（Eccentric/Concentric）
        Why: 局面別評価のため
        Design Decision: 動作フェーズを自動検出

        Returns:
            Dict: {
                'eccentric': {'start_frame': int, 'end_frame': int},
                'concentric': {'start_frame': int, 'end_frame': int}
            }

        CRITICAL: Phase Bで実装、Phase Aではプレースホルダー
        """
        raise NotImplementedError("Phase B で実装予定: 局面検出ロジック")

    def _evaluate_principle(
        self,
        principle_id: str,
        landmarks_data: List[Dict],
        phase: str
    ) -> Dict:
        """
        What: 個別原則の評価
        Why: 各原則（B1-B8）ごとのスコア計算
        Design Decision: 原則IDベースで柔軟に対応

        Args:
            principle_id: 原則ID（例: "B1", "B2"）
            landmarks_data: ランドマークデータ
            phase: "eccentric" or "concentric"

        Returns:
            Dict: {
                'score': int,
                'max_score': int,
                'details': str
            }

        CRITICAL: Phase Bで実装、Phase Aではプレースホルダー
        """
        raise NotImplementedError("Phase B で実装予定: 原則別評価ロジック")
