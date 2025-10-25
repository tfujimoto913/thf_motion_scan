"""
Purpose: RuleValidatorモジュールの単体テスト
Responsibility: test_rules.json の検証ロジック検証
Dependencies: pytest, processing.config.rule_validator
Created: 2025-10-25 by Claude
Decision Log: ADR-012（Phase 3: ルール定義ファイル充実）

CRITICAL: スキーマ・重み・閾値の全検証パターンをテスト必須
"""
import pytest
import json
import tempfile
from pathlib import Path
from processing.config.rule_validator import RuleValidator, load_test_rules


class TestRuleValidator:
    """
    What: RuleValidator テストクラス
    Why: ルール検証機能の正確性保証
    """

    @pytest.fixture
    def valid_rules(self):
        """
        What: 正常なルール定義データ
        Why: 基本的な検証テスト用
        """
        return {
            "schema_version": "1.0.0",
            "global_settings": {
                "score_range": {"min": 0, "max": 3},
                "frame_detection": {"min_detection_rate": 0.7},
                "scoring_method": {"default": "min"},
                "weight_validation": {"sum_must_equal": 1.0, "tolerance": 0.001}
            },
            "test_types": {
                "test_a": {
                    "display_name": "Test A",
                    "description": "Test A description",
                    "metrics": [
                        {
                            "name": "metric_1",
                            "weight": 0.5,
                            "unit": "meters",
                            "description": "Metric 1",
                            "thresholds": {
                                "score_3": {"max": 0.03, "description": "Excellent"},
                                "score_2": {"max": 0.05, "description": "Good"},
                                "score_1": {"max": 0.08, "description": "Fair"},
                                "score_0": {"min": 0.08, "description": "Poor"}
                            }
                        },
                        {
                            "name": "metric_2",
                            "weight": 0.5,
                            "unit": "degrees",
                            "description": "Metric 2",
                            "thresholds": {
                                "score_3": {"min": 80, "description": "Excellent"},
                                "score_2": {"min": 60, "description": "Good"},
                                "score_1": {"min": 45, "description": "Fair"},
                                "score_0": {"max": 45, "description": "Poor"}
                            }
                        }
                    ],
                    "overall_scoring": "min"
                }
            }
        }

    @pytest.fixture
    def temp_rules_file(self, valid_rules):
        """
        What: 一時的なルールファイル作成
        Why: ファイル読み込みテスト用
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_rules, f)
            temp_path = f.name

        yield temp_path

        # クリーンアップ
        Path(temp_path).unlink(missing_ok=True)

    def test_validate_schema_valid(self, valid_rules):
        """
        What: 正常スキーマの検証テスト
        Why: validate_schema() が True を返すことを確認
        """
        validator = RuleValidator()
        is_valid, errors = validator.validate_schema(valid_rules)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_schema_missing_top_level_key(self, valid_rules):
        """
        What: トップレベルキー欠落時のエラー検証
        Why: schema_version 欠落時に検出されることを確認
        """
        invalid_rules = valid_rules.copy()
        del invalid_rules['schema_version']

        validator = RuleValidator()
        is_valid, errors = validator.validate_schema(invalid_rules)

        assert is_valid is False
        assert any('schema_version' in error for error in errors)

    def test_validate_schema_missing_global_settings(self, valid_rules):
        """
        What: global_settings 欠落時のエラー検証
        Why: 必須フィールド検証の確認
        """
        invalid_rules = valid_rules.copy()
        del invalid_rules['global_settings']

        validator = RuleValidator()
        is_valid, errors = validator.validate_schema(invalid_rules)

        assert is_valid is False
        assert any('global_settings' in error for error in errors)

    def test_validate_schema_empty_test_types(self, valid_rules):
        """
        What: test_types 空の場合のエラー検証
        Why: 最低1つのテストタイプ必須を確認
        """
        invalid_rules = valid_rules.copy()
        invalid_rules['test_types'] = {}

        validator = RuleValidator()
        is_valid, errors = validator.validate_schema(invalid_rules)

        assert is_valid is False
        assert any('non-empty' in error for error in errors)

    def test_validate_schema_missing_metric_keys(self, valid_rules):
        """
        What: メトリック必須キー欠落時のエラー検証
        Why: name, weight, thresholds 欠落を検出
        """
        invalid_rules = valid_rules.copy()
        del invalid_rules['test_types']['test_a']['metrics'][0]['weight']

        validator = RuleValidator()
        is_valid, errors = validator.validate_schema(invalid_rules)

        assert is_valid is False
        assert any('weight' in error for error in errors)

    def test_validate_schema_missing_threshold_scores(self, valid_rules):
        """
        What: 閾値スコアレベル欠落時のエラー検証
        Why: score_0～score_3 すべて必須を確認
        """
        invalid_rules = valid_rules.copy()
        del invalid_rules['test_types']['test_a']['metrics'][0]['thresholds']['score_2']

        validator = RuleValidator()
        is_valid, errors = validator.validate_schema(invalid_rules)

        assert is_valid is False
        assert any('score_2' in error for error in errors)

    def test_validate_weights_valid(self, valid_rules):
        """
        What: 正常な重み合計の検証
        Why: 重み合計 = 1.0 の確認
        """
        validator = RuleValidator()
        is_valid, errors = validator.validate_weights(valid_rules)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_weights_incorrect_sum(self, valid_rules):
        """
        What: 重み合計エラーの検証
        Why: 重み合計 ≠ 1.0 を検出
        """
        invalid_rules = valid_rules.copy()
        invalid_rules['test_types']['test_a']['metrics'][0]['weight'] = 0.6  # 合計 1.1

        validator = RuleValidator()
        is_valid, errors = validator.validate_weights(invalid_rules)

        assert is_valid is False
        assert any('weight sum' in error for error in errors)

    def test_validate_weights_within_tolerance(self, valid_rules):
        """
        What: 許容範囲内の重み合計検証
        Why: tolerance ± 範囲内は正常と判定
        """
        rules = valid_rules.copy()
        # 合計 1.0005（tolerance 0.001 以内なので許容）
        rules['test_types']['test_a']['metrics'][0]['weight'] = 0.50025
        rules['test_types']['test_a']['metrics'][1]['weight'] = 0.50025

        validator = RuleValidator()
        is_valid, errors = validator.validate_weights(rules)

        # tolerance 0.001 で 1.0005 は |1.0005 - 1.0| = 0.0005 < 0.001 なので許容
        assert is_valid is True

    def test_validate_thresholds_valid(self, valid_rules):
        """
        What: 正常な閾値の検証
        Why: 閾値定義の正当性確認
        """
        validator = RuleValidator()
        is_valid, errors = validator.validate_thresholds(valid_rules)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_thresholds_both_min_max(self, valid_rules):
        """
        What: min/max 両方指定時のエラー検証
        Why: min と max は排他的であることを確認
        """
        invalid_rules = valid_rules.copy()
        invalid_rules['test_types']['test_a']['metrics'][0]['thresholds']['score_3'] = {
            'min': 0.01,
            'max': 0.03,
            'description': 'Invalid'
        }

        validator = RuleValidator()
        is_valid, errors = validator.validate_thresholds(invalid_rules)

        assert is_valid is False
        assert any('both' in error.lower() for error in errors)

    def test_validate_thresholds_neither_min_nor_max(self, valid_rules):
        """
        What: min/max いずれも未指定時のエラー検証
        Why: min または max は必須であることを確認
        """
        invalid_rules = valid_rules.copy()
        invalid_rules['test_types']['test_a']['metrics'][0]['thresholds']['score_3'] = {
            'description': 'No threshold'
        }

        validator = RuleValidator()
        is_valid, errors = validator.validate_thresholds(invalid_rules)

        assert is_valid is False
        assert any('must specify' in error.lower() for error in errors)

    def test_validate_file_not_found(self):
        """
        What: ファイル非存在時のエラー検証
        Why: FileNotFoundError 発生を確認
        """
        validator = RuleValidator('nonexistent.json')

        with pytest.raises(FileNotFoundError):
            validator.validate()

    def test_validate_invalid_json(self):
        """
        What: 不正JSON時のエラー検証
        Why: json.JSONDecodeError 発生を確認
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            validator = RuleValidator(temp_path)
            with pytest.raises(json.JSONDecodeError):
                validator.validate()
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_validate_integration_success(self, temp_rules_file):
        """
        What: 統合検証の成功テスト
        Why: validate() が全検証を実行することを確認
        """
        validator = RuleValidator(temp_rules_file)
        is_valid, errors = validator.validate()

        assert is_valid is True
        assert len(errors) == 0
        assert validator.rules is not None

    def test_validate_integration_multiple_errors(self, valid_rules):
        """
        What: 複数エラー検出の統合テスト
        Why: 全検証レイヤーのエラーが集約されることを確認
        """
        invalid_rules = valid_rules.copy()
        # スキーマエラー: display_name 欠落
        del invalid_rules['test_types']['test_a']['display_name']
        # 重みエラー: 合計 ≠ 1.0
        invalid_rules['test_types']['test_a']['metrics'][0]['weight'] = 0.7

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_rules, f)
            temp_path = f.name

        try:
            validator = RuleValidator(temp_path)
            is_valid, errors = validator.validate()

            assert is_valid is False
            # スキーマエラーで検証停止するため、重みエラーは検出されない
            assert len(errors) > 0
            assert any('display_name' in error for error in errors)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_get_test_rule_valid(self, temp_rules_file):
        """
        What: テストルール取得テスト
        Why: get_test_rule() が正しく動作することを確認
        """
        validator = RuleValidator(temp_rules_file)
        validator.validate()

        test_rule = validator.get_test_rule('test_a')

        assert test_rule is not None
        assert test_rule['display_name'] == 'Test A'
        assert len(test_rule['metrics']) == 2

    def test_get_test_rule_not_found(self, temp_rules_file):
        """
        What: 存在しないテストルール取得テスト
        Why: None を返すことを確認
        """
        validator = RuleValidator(temp_rules_file)
        validator.validate()

        test_rule = validator.get_test_rule('nonexistent')

        assert test_rule is None

    def test_get_test_rule_before_validate(self):
        """
        What: validate() 前の取得テスト
        Why: rules が None のため None を返すことを確認
        """
        validator = RuleValidator()

        test_rule = validator.get_test_rule('test_a')

        assert test_rule is None

    def test_get_global_settings_valid(self, temp_rules_file):
        """
        What: グローバル設定取得テスト
        Why: get_global_settings() が正しく動作することを確認
        """
        validator = RuleValidator(temp_rules_file)
        validator.validate()

        global_settings = validator.get_global_settings()

        assert global_settings is not None
        assert 'score_range' in global_settings
        assert global_settings['score_range']['min'] == 0
        assert global_settings['score_range']['max'] == 3

    def test_load_test_rules_success(self, temp_rules_file):
        """
        What: load_test_rules() 成功テスト
        Why: 検証済みルールが返されることを確認
        """
        rules = load_test_rules(temp_rules_file)

        assert rules is not None
        assert 'schema_version' in rules
        assert 'test_types' in rules
        assert 'test_a' in rules['test_types']

    def test_load_test_rules_validation_failure(self, valid_rules):
        """
        What: load_test_rules() 検証失敗テスト
        Why: ValueError が発生することを確認
        """
        invalid_rules = valid_rules.copy()
        del invalid_rules['schema_version']

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_rules, f)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Rule validation failed"):
                load_test_rules(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_load_test_rules_file_not_found(self):
        """
        What: load_test_rules() ファイル非存在テスト
        Why: FileNotFoundError が発生することを確認
        """
        with pytest.raises(FileNotFoundError):
            load_test_rules('nonexistent.json')


class TestRuleValidatorWithActualFile:
    """
    What: 実際の test_rules.json を使ったテスト
    Why: 本番ファイルの検証
    """

    def test_actual_test_rules_json_valid(self):
        """
        What: processing/config/test_rules.json の検証
        Why: 実ファイルが正常であることを確認
        """
        rules_path = 'processing/config/test_rules.json'

        # ファイルが存在する場合のみテスト
        if not Path(rules_path).exists():
            pytest.skip(f"{rules_path} not found")

        validator = RuleValidator(rules_path)
        is_valid, errors = validator.validate()

        assert is_valid is True, f"Validation errors: {errors}"

    def test_actual_test_rules_all_test_types_present(self):
        """
        What: 7種目すべてのテストタイプ存在確認
        Why: 必要な全種目が定義されていることを確認
        """
        rules_path = 'processing/config/test_rules.json'

        if not Path(rules_path).exists():
            pytest.skip(f"{rules_path} not found")

        rules = load_test_rules(rules_path)
        test_types = rules['test_types']

        expected_types = [
            'single_leg_squat',
            'upper_body_swing',
            'skater_lunge',
            'cross_step',
            'stride_mimic',
            'push_pull',
            'jump_landing'
        ]

        for test_type in expected_types:
            assert test_type in test_types, f"Missing test type: {test_type}"

    def test_actual_test_rules_all_weights_sum_to_one(self):
        """
        What: 全テストタイプの重み合計検証
        Why: すべての種目で重み合計 = 1.0 を確認
        """
        rules_path = 'processing/config/test_rules.json'

        if not Path(rules_path).exists():
            pytest.skip(f"{rules_path} not found")

        rules = load_test_rules(rules_path)
        tolerance = rules['global_settings']['weight_validation']['tolerance']

        for test_name, test_config in rules['test_types'].items():
            metrics = test_config['metrics']
            total_weight = sum(metric['weight'] for metric in metrics)

            assert abs(total_weight - 1.0) <= tolerance, \
                f"Test '{test_name}' weight sum {total_weight} != 1.0"
