"""
Purpose: テストルール定義ファイルの検証とロード（12点満点システム対応）
Responsibility: test_rules.json の整合性検証、ルール読み込み
Dependencies: json, pathlib, typing
Created: 2025-10-25 by Claude
Updated: 2025-10-27 - 12点満点システム（A: 3点 + B: 9点）対応
Decision Log: ADR-012, ADR-016

CRITICAL: 12点満点システム（execution 3点 + principles 9点）の厳格な検証必須
"""
import json
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional


class RuleValidator:
    """
    What: ルール定義ファイルの検証クラス（12点満点システム対応）
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
        What: スキーマ構造の検証（12点満点システム）
        Why: 必須フィールドの存在確認
        Design Decision: version, score_system, tests の必須キー検証

        Args:
            rules: ルール定義辞書

        Returns:
            Tuple[bool, List[str]]: (検証結果, エラーメッセージリスト)

        CRITICAL: version, score_system, tests は必須
        """
        errors = []

        # PHASE CORE LOGIC: トップレベルキー検証
        required_top_keys = ['version', 'updated_at', 'score_system', 'tests']
        for key in required_top_keys:
            if key not in rules:
                errors.append(f"Missing required top-level key: {key}")

        if errors:
            return False, errors

        # PHASE CORE LOGIC: score_system 検証
        score_system = rules.get('score_system', {})
        required_score_keys = ['total_points', 'per_test_max', 'execution_score_max', 'principles_score_max']
        for key in required_score_keys:
            if key not in score_system:
                errors.append(f"Missing required score_system key: {key}")

        # CRITICAL: スコアシステムの整合性チェック
        if 'execution_score_max' in score_system and 'principles_score_max' in score_system and 'per_test_max' in score_system:
            exec_max = score_system['execution_score_max']
            prin_max = score_system['principles_score_max']
            per_test = score_system['per_test_max']
            if exec_max + prin_max != per_test:
                errors.append(
                    f"score_system inconsistent: execution_score_max ({exec_max}) + "
                    f"principles_score_max ({prin_max}) != per_test_max ({per_test})"
                )

        # PHASE CORE LOGIC: tests 検証
        tests = rules.get('tests', {})
        if not isinstance(tests, dict) or len(tests) == 0:
            errors.append("tests must be a non-empty dictionary")
            return False, errors

        # PHASE CORE LOGIC: 各テストの構造検証
        for test_code, test_config in tests.items():
            required_test_keys = ['test_id', 'name', 'name_en', 'evaluation_principle', 'execution', 'principles']
            for key in required_test_keys:
                if key not in test_config:
                    errors.append(f"Test '{test_code}' missing required key: {key}")

            # CRITICAL: execution 検証
            if 'execution' in test_config:
                execution = test_config['execution']
                if 'total_points' not in execution or 'metrics' not in execution:
                    errors.append(f"Test '{test_code}' execution missing 'total_points' or 'metrics'")
                elif execution['total_points'] != score_system.get('execution_score_max', 3):
                    errors.append(
                        f"Test '{test_code}' execution.total_points ({execution['total_points']}) != "
                        f"execution_score_max ({score_system.get('execution_score_max', 3)})"
                    )

            # CRITICAL: principles 検証
            if 'principles' in test_config:
                principles = test_config['principles']
                if 'total_points' not in principles:
                    errors.append(f"Test '{test_code}' principles missing 'total_points'")
                elif principles['total_points'] != score_system.get('principles_score_max', 9):
                    errors.append(
                        f"Test '{test_code}' principles.total_points ({principles['total_points']}) != "
                        f"principles_score_max ({score_system.get('principles_score_max', 9)})"
                    )

        return len(errors) == 0, errors

    def validate_weights(self, rules: Dict) -> Tuple[bool, List[str]]:
        """
        What: メトリック重みの合計検証（12点満点システム）
        Why: execution と principles の重み合計検証
        Design Decision: execution 合計 = 3点、各principle = 3点

        Args:
            rules: ルール定義辞書

        Returns:
            Tuple[bool, List[str]]: (検証結果, エラーメッセージリスト)

        CRITICAL: execution メトリックの重み合計 = 3.0、各principle = 3.0
        """
        errors = []
        tolerance = 0.001

        tests = rules.get('tests', {})

        # PHASE CORE LOGIC: 各テストの重み合計チェック
        for test_code, test_config in tests.items():
            # Execution メトリックの重み合計チェック
            execution = test_config.get('execution', {})
            metrics = execution.get('metrics', {})

            if isinstance(metrics, dict):
                exec_weights = []
                for metric_name, metric_config in metrics.items():
                    weight = metric_config.get('weight', 0)
                    exec_weights.append(weight)

                exec_total = sum(exec_weights)
                expected_exec = execution.get('total_points', 3)

                if abs(exec_total - expected_exec) > tolerance:
                    errors.append(
                        f"Test '{test_code}' execution weights sum {exec_total:.4f} != {expected_exec} "
                        f"(tolerance: {tolerance})"
                    )

            # Principles の重み合計チェック
            principles = test_config.get('principles', {})
            principle_total_weight = 0

            for prin_key, prin_config in principles.items():
                if prin_key == 'total_points':
                    continue

                weight = prin_config.get('weight', 0)
                principle_total_weight += weight

            expected_prin = principles.get('total_points', 9)

            if abs(principle_total_weight - expected_prin) > tolerance:
                errors.append(
                    f"Test '{test_code}' principles weights sum {principle_total_weight:.4f} != {expected_prin} "
                    f"(tolerance: {tolerance})"
                )

        return len(errors) == 0, errors

    def validate_test_codes(self, rules: Dict) -> Tuple[bool, List[str]]:
        """
        What: テストコードの実装整合性検証
        Why: test_rules.json のテストコードが実装コードと一致することを確認
        Design Decision: 7種目全てが定義されていることを確認

        Args:
            rules: ルール定義辞書

        Returns:
            Tuple[bool, List[str]]: (検証結果, エラーメッセージリスト)

        CRITICAL: 実装コード（single_leg_squat等）が全て定義されていること
        """
        errors = []

        # CRITICAL: 実装済み7種目の実装コード
        expected_codes = {
            'single_leg_squat',
            'skater_lunge',
            'stride_mimic',
            'jump_landing',
            'upper_body_swing',
            'push_pull',
            'cross_step'
        }

        tests = rules.get('tests', {})
        defined_codes = set(tests.keys())

        # 不足しているコード
        missing = expected_codes - defined_codes
        if missing:
            errors.append(f"Missing required test codes: {', '.join(sorted(missing))}")

        # 余分なコード（警告のみ）
        extra = defined_codes - expected_codes
        if extra:
            errors.append(f"Warning: Extra test codes not in implementation: {', '.join(sorted(extra))}")

        # test_id の整合性チェック
        for code, test_config in tests.items():
            test_id = test_config.get('test_id', '')
            expected_prefix = code.upper().replace('_', '')[:3]  # 例: single_leg_squat -> SIN

            # test_id が T01-T07 の形式であることを確認
            if not test_id.startswith('T0') or not test_id[2].isdigit():
                errors.append(f"Test '{code}' has invalid test_id format: {test_id} (expected: T01-T07)")

        return len(errors) == 0, errors

    def validate(self) -> Tuple[bool, List[str]]:
        """
        What: 統合検証（ファイル読み込み→全検証実行）
        Why: ワンストップで完全な検証実施
        Design Decision: スキーマ→重み→テストコードの順で検証

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

        # 3. テストコード整合性検証
        code_ok, code_errors = self.validate_test_codes(self.rules)
        all_errors.extend(code_errors)

        return len(all_errors) == 0, all_errors

    def get_test_rule(self, test_code: str) -> Optional[Dict]:
        """
        What: 特定テストコードのルール取得
        Why: Evaluator での閾値参照用

        Args:
            test_code: テストコード（例: 'single_leg_squat'）

        Returns:
            Optional[Dict]: テストルール（存在しない場合は None）

        CRITICAL: validate() 実行済み前提
        """
        if self.rules is None:
            return None

        return self.rules.get('tests', {}).get(test_code)

    def get_score_system(self) -> Optional[Dict]:
        """
        What: スコアシステム設定取得
        Why: 共通設定の参照用

        Returns:
            Optional[Dict]: スコアシステム設定（読み込み前は None）

        CRITICAL: validate() 実行済み前提
        """
        if self.rules is None:
            return None

        return self.rules.get('score_system')


def load_test_rules(rules_path: str = 'processing/config/test_rules.json') -> Dict:
    """
    What: ルール定義ファイルのロードと検証（12点満点システム対応）
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
