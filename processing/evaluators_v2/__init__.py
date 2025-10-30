"""
Purpose: 8原則・237点満点評価システム（v2）パッケージ
Responsibility: 新評価体系のエントリーポイント
Dependencies: base_evaluator_v2.py, test_rules_v2.json
Created: 2025-10-30 by Claude
Decision Log: Phase A - 並行動作環境構築, Phase B - 評価器実装

CRITICAL: 既存のevaluators/には一切影響を与えない
"""

from .base_evaluator_v2 import BaseEvaluatorV2
from .single_leg_squat_v2 import SingleLegSquatEvaluatorV2

__all__ = [
    'BaseEvaluatorV2',
    'SingleLegSquatEvaluatorV2'
]
