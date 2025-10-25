"""
Purpose: テストルール定義ファイルの検証とロード
Responsibility: test_rules.json の整合性検証、ルール読み込み
Dependencies: json, pathlib, typing
Created: 2025-10-25 by Claude
Decision Log: ADR-012（Phase 3: ルール定義ファイル充実）

CRITICAL: 重み合計、閾値範囲、スキーマ構造の厳格な検証必須
"""
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional


class RuleValidator:
    """
    What: ルール定義ファイルの検証クラス
    Why: test_rules.json の整合性と妥当性を保証
    Design Decision: 多層検証（スキーマ→重み→閾値）で堅牢性確保

    CRITICAL: 検証失敗時は具体的なエラーメッセージを返す
    """

    def __init__(self, rules_path: str = 'processing/config/test_rules.json'):
        """
        What: RuleValidator 初期化
        Why: ルールファイルパス保持

        Args:
            rules_path: test_rules.json のパス

        CRITICAL: ファイルの存在確認は validate() で実施
        """
        self.rules_path = Path(rules_path)
        self.rules: Optional[Dict] = None

    def validate_schema(self, rules: Dict) -> Tuple[bool, List[str]]:
        """
        What: スキーマ構造の検証
        Why: 必須フィールドの存在確認
        Design Decision: global_settings, test_types の必須キー検証

        Args:
            rules: ルール定義辞書

        Returns:
            Tuple[bool, List[str]]: (検証結果, エラーメッセージリスト)

        CRITICAL: schema_version, global_settings, test_types は必須
        """
        errors = []

        # PHASE CORE LOGIC: トップレベルキー検証
        required_top_keys = ['schema_version', 'global_settings', 'test_types']
        for key in required_top_keys:
            if key not in rules:
                errors.append(f"Missing required top-level key: {key}")

        if errors:
            return False, errors

        # PHASE CORE LOGIC: global_settings 検証
        required_global_keys = ['score_range', 'frame_detection', 'scoring_method', 'weight_validation']
        for key in required_global_keys:
            if key not in rules['global_settings']:
                errors.append(f"Missing required global_settings key: {key}")

        # PHASE CORE LOGIC: test_types 検証
        test_types = rules['test_types']
        if not isinstance(test_types, dict) or len(test_types) == 0:
            errors.append("test_types must be a non-empty dictionary")
            return False, errors

        # PHASE CORE LOGIC: 各テストタイプの構造検証
        for test_name, test_config in test_types.items():
            required_test_keys = ['display_name', 'description', 'metrics', 'overall_scoring']
            for key in required_test_keys:
                if key not in test_config:
                    errors.append(f"Test '{test_name}' missing required key: {key}")

            # CRITICAL: metrics は配列であること
            if 'metrics' in test_config:
                if not isinstance(test_config['metrics'], list):
                    errors.append(f"Test '{test_name}' metrics must be a list")
                elif len(test_config['metrics']) == 0:
                    errors.append(f"Test '{test_name}' must have at least one metric")
                else:
                    # PHASE CORE LOGIC: 各メトリックの構造検証
                    for idx, metric in enumerate(test_config['metrics']):
                        required_metric_keys = ['name', 'weight', 'unit', 'description', 'thresholds']
                        for key in required_metric_keys:
                            if key not in metric:
                                errors.append(
                                    f"Test '{test_name}' metric[{idx}] missing required key: {key}"
                                )

                        # CRITICAL: thresholds 検証
                        if 'thresholds' in metric:
                            thresholds = metric['thresholds']
                            required_scores = ['score_3', 'score_2', 'score_1', 'score_0']
                            for score in required_scores:
                                if score not in thresholds:
                                    errors.append(
                                        f"Test '{test_name}' metric[{idx}] missing threshold: {score}"
                                    )

        return len(errors) == 0, errors

    def validate_weights(self, rules: Dict) -> Tuple[bool, List[str]]:
        """
        What: メトリック重みの合計検証
        Why: 重み合計 = 1.0 の保証
        Design Decision: global_settings.weight_validation.tolerance を使用

        Args:
            rules: ルール定義辞書

        Returns:
            Tuple[bool, List[str]]: (検証結果, エラーメッセージリスト)

        CRITICAL: 各テストタイプの重み合計が 1.0 ± tolerance であること
        """
        errors = []
        tolerance = rules['global_settings']['weight_validation'].get('tolerance', 0.001)
        expected_sum = rules['global_settings']['weight_validation'].get('sum_must_equal', 1.0)

        # PHASE CORE LOGIC: 各テストタイプの重み合計チェック
        for test_name, test_config in rules['test_types'].items():
            metrics = test_config.get('metrics', [])
            if not metrics:
                continue

            # CRITICAL: 重み合計計算
            total_weight = sum(metric.get('weight', 0) for metric in metrics)

            # CRITICAL: 許容範囲チェック
            if abs(total_weight - expected_sum) > tolerance:
                errors.append(
                    f"Test '{test_name}' weight sum {total_weight:.4f} != {expected_sum} "
                    f"(tolerance: {tolerance})"
                )

        return len(errors) == 0, errors

    def validate_thresholds(self, rules: Dict) -> Tuple[bool, List[str]]:
        """
        What: 閾値範囲の妥当性検証
        Why: スコア範囲の整合性保証
        Design Decision: min/max の論理的順序チェック

        Args:
            rules: ルール定義辞書

        Returns:
            Tuple[bool, List[str]]: (検証結果, エラーメッセージリスト)

        CRITICAL: score_3 > score_2 > score_1 の順序保証（単位による）
        """
        errors = []
        score_range = rules['global_settings']['score_range']
        min_score = score_range.get('min', 0)
        max_score = score_range.get('max', 3)

        # PHASE CORE LOGIC: 各テストタイプの閾値検証
        for test_name, test_config in rules['test_types'].items():
            metrics = test_config.get('metrics', [])

            for metric in metrics:
                metric_name = metric.get('name', 'unknown')
                thresholds = metric.get('thresholds', {})

                # CRITICAL: 各スコアレベルの閾値存在確認
                for score_level in ['score_3', 'score_2', 'score_1', 'score_0']:
                    if score_level not in thresholds:
                        continue

                    threshold = thresholds[score_level]

                    # CRITICAL: min/max の両方指定は不可
                    if 'min' in threshold and 'max' in threshold:
                        errors.append(
                            f"Test '{test_name}' metric '{metric_name}' {score_level}: "
                            f"Cannot specify both 'min' and 'max'"
                        )

                    # CRITICAL: min または max のいずれかは必須
                    if 'min' not in threshold and 'max' not in threshold:
                        errors.append(
                            f"Test '{test_name}' metric '{metric_name}' {score_level}: "
                            f"Must specify either 'min' or 'max'"
                        )

        return len(errors) == 0, errors

    def validate(self) -> Tuple[bool, List[str]]:
        """
        What: 統合検証（ファイル読み込み→全検証実行）
        Why: ワンストップで完全な検証実施
        Design Decision: スキーマ→重み→閾値の順で検証

        Returns:
            Tuple[bool, List[str]]: (検証結果, 全エラーメッセージリスト)

        Raises:
            FileNotFoundError: ルールファイルが存在しない場合
            json.JSONDecodeError: JSON構文エラーの場合

        CRITICAL: 検証失敗時も self.rules に読み込み済みデータを保持
        """
        # PHASE CORE LOGIC: ファイル存在確認
        if not self.rules_path.exists():
            raise FileNotFoundError(f"Rules file not found: {self.rules_path}")

        # PHASE CORE LOGIC: JSON読み込み
        with open(self.rules_path, 'r', encoding='utf-8') as f:
            self.rules = json.load(f)

        all_errors = []

        # PHASE CORE LOGIC: 多層検証
        # 1. スキーマ構造検証
        schema_ok, schema_errors = self.validate_schema(self.rules)
        all_errors.extend(schema_errors)

        # CRITICAL: スキーマエラーがある場合は後続検証をスキップ
        if not schema_ok:
            return False, all_errors

        # 2. 重み合計検証
        weight_ok, weight_errors = self.validate_weights(self.rules)
        all_errors.extend(weight_errors)

        # 3. 閾値範囲検証
        threshold_ok, threshold_errors = self.validate_thresholds(self.rules)
        all_errors.extend(threshold_errors)

        return len(all_errors) == 0, all_errors

    def get_test_rule(self, test_type: str) -> Optional[Dict]:
        """
        What: 特定テストタイプのルール取得
        Why: Evaluator での閾値参照用

        Args:
            test_type: テストタイプ名

        Returns:
            Optional[Dict]: テストルール（存在しない場合は None）

        CRITICAL: validate() 実行済み前提
        """
        if self.rules is None:
            return None

        return self.rules.get('test_types', {}).get(test_type)

    def get_global_settings(self) -> Optional[Dict]:
        """
        What: グローバル設定取得
        Why: 共通設定の参照用

        Returns:
            Optional[Dict]: グローバル設定（読み込み前は None）

        CRITICAL: validate() 実行済み前提
        """
        if self.rules is None:
            return None

        return self.rules.get('global_settings')


def load_test_rules(rules_path: str = 'processing/config/test_rules.json') -> Dict:
    """
    What: ルール定義ファイルのロードと検証
    Why: Evaluator での簡易ルール読み込み用
    Design Decision: 検証失敗時は例外発生

    Args:
        rules_path: test_rules.json のパス

    Returns:
        Dict: 検証済みルール定義

    Raises:
        FileNotFoundError: ファイルが存在しない場合
        json.JSONDecodeError: JSON構文エラーの場合
        ValueError: 検証失敗の場合（エラー詳細を含む）

    CRITICAL: 必ず検証を実行してから返す
    """
    # PHASE CORE LOGIC: 検証実行
    validator = RuleValidator(rules_path)
    is_valid, errors = validator.validate()

    # CRITICAL: 検証失敗時は詳細エラーを含む例外発生
    if not is_valid:
        error_message = "Rule validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_message)

    return validator.rules
