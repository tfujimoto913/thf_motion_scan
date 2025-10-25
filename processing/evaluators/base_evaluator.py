"""
Purpose: 評価器の基底クラス
Responsibility: 共通ルール読み込み、閾値取得、評価インターフェース定義
Dependencies: abc, json, config.rule_validator
Created: 2025-10-25 by Claude
Decision Log: ADR-012（Phase 3: ルール定義ファイル充実）

CRITICAL: 全evaluatorはこのベースクラスを継承すること
"""
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any

from ..config import load_test_rules


class BaseEvaluator(ABC):
    """
    What: 評価器の抽象基底クラス
    Why: 共通機能の一元管理、ルール定義の統一的アクセス
    Design Decision: test_rules.json と config.json の両対応（ADR-012）

    CRITICAL: evaluate() は各サブクラスで実装必須
    """

    def __init__(self,
                 config_path: str = 'config.json',
                 rules_path: str = 'processing/config/test_rules.json',
                 test_type: Optional[str] = None):
        """
        What: 評価器初期化（config.json + test_rules.json 読み込み）
        Why: レガシーconfig.json と新test_rules.json の両対応
        Design Decision: 段階的移行のため両ファイル共存（ADR-012）

        Args:
            config_path: config.json のパス（レガシー互換用）
            rules_path: test_rules.json のパス
            test_type: テストタイプ名（test_rules.json から該当ルール取得用）

        CRITICAL: config.json 存在しない場合は警告のみ（test_rules.json優先）
        """
        self.test_type = test_type
        self.config = None
        self.test_rules = None
        self.test_rule = None

        # PHASE CORE LOGIC: レガシーconfig.json読み込み（互換性維持）
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            # CRITICAL: config.json無しでも動作可能（test_rules.jsonのみ使用）
            print(f"⚠️  config.json not found: {config_path} (test_rules.json will be used)")

        # PHASE CORE LOGIC: test_rules.json読み込み（ADR-012）
        rules_file = Path(rules_path)
        if rules_file.exists():
            try:
                # CRITICAL: load_test_rules() は検証済みルールを返す
                self.test_rules = load_test_rules(str(rules_file))

                # CRITICAL: test_type指定時は該当ルール取得
                if test_type:
                    self.test_rule = self.test_rules.get('test_types', {}).get(test_type)
                    if not self.test_rule:
                        print(f"⚠️  Test type '{test_type}' not found in test_rules.json")

            except (FileNotFoundError, ValueError) as e:
                print(f"⚠️  Failed to load test_rules.json: {e}")
        else:
            print(f"⚠️  test_rules.json not found: {rules_path}")

    @abstractmethod
    def evaluate(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: ランドマークデータから評価結果を生成
        Why: 各evaluatorの主要機能
        Design Decision: 統一インターフェース（ADR-012）

        Args:
            landmarks_data: フレームごとのランドマークデータ
                [{
                    'frame': int,
                    'timestamp': float,
                    'landmarks': [{'x': float, 'y': float, 'z': float, 'visibility': float}, ...]
                }, ...]

        Returns:
            Dict: {
                'score': int (0-3),
                'details': str,
                ... 各evaluator固有のフィールド
            }

        CRITICAL: サブクラスで必ず実装すること
        """
        pass

    def get_metric_threshold(self,
                             metric_name: str,
                             score_level: int,
                             threshold_type: str = 'max') -> Optional[float]:
        """
        What: メトリック閾値の取得
        Why: test_rules.json から動的に閾値参照
        Design Decision: score_level (0-3) から threshold キー生成（ADR-012）

        Args:
            metric_name: メトリック名（例: 'pelvic_stability'）
            score_level: スコアレベル（0-3）
            threshold_type: 閾値タイプ（'min' or 'max'）

        Returns:
            Optional[float]: 閾値（見つからない場合は None）

        Usage:
            >>> evaluator = SingleLegSquatEvaluator()
            >>> threshold = evaluator.get_metric_threshold('pelvic_stability', 3, 'max')
            >>> # Returns 0.03 (score_3 の max 値)

        CRITICAL: test_rule が None の場合は None を返す
        """
        # CRITICAL: test_rule 未ロードの場合は None
        if not self.test_rule:
            return None

        # PHASE CORE LOGIC: メトリック検索
        metrics = self.test_rule.get('metrics', [])
        for metric in metrics:
            if metric.get('name') == metric_name:
                # CRITICAL: score_level から閾値キー生成
                score_key = f'score_{score_level}'
                thresholds = metric.get('thresholds', {})

                if score_key in thresholds:
                    threshold_config = thresholds[score_key]
                    return threshold_config.get(threshold_type)

        # CRITICAL: メトリック見つからない場合は None
        return None

    def get_all_metric_thresholds(self, metric_name: str) -> Optional[Dict]:
        """
        What: メトリックの全閾値取得
        Why: 全スコアレベルの閾値を一括取得
        Design Decision: スコアリングロジックで複数閾値参照時に効率的（ADR-012）

        Args:
            metric_name: メトリック名

        Returns:
            Optional[Dict]: {
                'score_3': {'max': float, 'description': str},
                'score_2': {'max': float, 'description': str},
                ...
            }

        CRITICAL: test_rule が None の場合は None を返す
        """
        if not self.test_rule:
            return None

        # PHASE CORE LOGIC: メトリック検索
        metrics = self.test_rule.get('metrics', [])
        for metric in metrics:
            if metric.get('name') == metric_name:
                return metric.get('thresholds')

        return None

    def get_metric_weight(self, metric_name: str) -> Optional[float]:
        """
        What: メトリック重み取得
        Why: 加重平均スコア計算用
        Design Decision: test_rules.json の weight フィールド参照（ADR-012）

        Args:
            metric_name: メトリック名

        Returns:
            Optional[float]: 重み（見つからない場合は None）

        CRITICAL: 重み合計は必ず 1.0 （load_test_rules() で検証済み）
        """
        if not self.test_rule:
            return None

        # PHASE CORE LOGIC: メトリック検索
        metrics = self.test_rule.get('metrics', [])
        for metric in metrics:
            if metric.get('name') == metric_name:
                return metric.get('weight')

        return None

    def get_global_setting(self, setting_key: str) -> Optional[Any]:
        """
        What: グローバル設定取得
        Why: 共通設定（score_range, frame_detection等）の参照
        Design Decision: test_rules.json の global_settings から取得（ADR-012）

        Args:
            setting_key: 設定キー（例: 'score_range', 'frame_detection'）

        Returns:
            Optional[Any]: 設定値（見つからない場合は None）

        CRITICAL: test_rules が None の場合は None を返す
        """
        if not self.test_rules:
            return None

        return self.test_rules.get('global_settings', {}).get(setting_key)

    def get_score_range(self) -> Optional[Dict]:
        """
        What: スコア範囲取得
        Why: スコア検証用
        Design Decision: global_settings.score_range 参照（ADR-012）

        Returns:
            Optional[Dict]: {'min': int, 'max': int, 'description': str}

        CRITICAL: 全テストで共通（0-3）
        """
        return self.get_global_setting('score_range')

    def get_overall_scoring_method(self) -> Optional[str]:
        """
        What: 総合スコア計算方法取得
        Why: min / weighted_average の選択
        Design Decision: test_rule.overall_scoring 参照（ADR-012）

        Returns:
            Optional[str]: 'min' or 'weighted_average'

        CRITICAL: デフォルトは 'min'（全指標を満たす必要がある）
        """
        if not self.test_rule:
            return None

        return self.test_rule.get('overall_scoring', 'min')

    def calculate_overall_score(self, metric_scores: Dict[str, int]) -> int:
        """
        What: メトリックスコアから総合スコア計算
        Why: overall_scoring_method に基づく統一的なスコア計算
        Design Decision: 'min' または 'weighted_average' を使用（ADR-012）

        Args:
            metric_scores: {metric_name: score} の辞書

        Returns:
            int: 総合スコア（0-3）

        CRITICAL: overall_scoring_method が None の場合は min を使用
        """
        if not metric_scores:
            return 0

        scoring_method = self.get_overall_scoring_method() or 'min'

        # PHASE CORE LOGIC: スコア計算方法による分岐
        if scoring_method == 'min':
            # CRITICAL: 全指標を満たす必要がある（最弱リンク）
            return min(metric_scores.values())

        elif scoring_method == 'weighted_average':
            # CRITICAL: 重み付き平均（重み合計 = 1.0 前提）
            total = 0.0
            for metric_name, score in metric_scores.items():
                weight = self.get_metric_weight(metric_name) or 0.0
                total += score * weight

            # CRITICAL: 四捨五入して整数化（0-3 範囲）
            return min(3, max(0, round(total)))

        else:
            # CRITICAL: 未知の方法の場合は min を使用
            print(f"⚠️  Unknown scoring method '{scoring_method}', using 'min'")
            return min(metric_scores.values())
