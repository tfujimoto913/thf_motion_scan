"""
Purpose: Configモジュール - ルール定義とバリデーション
Responsibility: RuleValidator と load_test_rules をエクスポート
Dependencies: rule_validator
Created: 2025-10-25 by Claude
Decision Log: ADR-012（Phase 3: ルール定義ファイル充実）

CRITICAL: 新規バリデーター追加時は必ずここにエクスポートを追加
"""
# PHASE CORE LOGIC: ルールバリデーター関連をインポート（ADR-012）
from .rule_validator import RuleValidator, load_test_rules

# CRITICAL: __all__定義により外部からのimportを制御
__all__ = [
    'RuleValidator',
    'load_test_rules',
]
