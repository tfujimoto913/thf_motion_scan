"""
Purpose: Evaluatorsモジュール - 各種モーションテストの評価ロジック
Responsibility: 7種目の評価クラス + BaseEvaluatorをエクスポート
Dependencies: 各evaluatorモジュール
Created: 2025-10-19 by Claude
Decision Log: ADR-002, ADR-003, ADR-012

CRITICAL: 新規評価種目追加時は必ずここにエクスポートを追加
"""
# PHASE CORE LOGIC: BaseEvaluatorをインポート（ADR-012）
from .base_evaluator import BaseEvaluator

# PHASE CORE LOGIC: 7種目すべてのEvaluatorをインポート（ADR-002）
from .single_leg_squat import SingleLegSquatEvaluator
from .cross_step import CrossStepEvaluator
from .jump_landing import JumpLandingEvaluator
from .skater_lunge import SkaterLungeEvaluator
from .stride_mimic import StrideMinicryEvaluator
from .push_pull import PushPullEvaluator
from .upper_body_swing import UpperBodySwingEvaluator

# CRITICAL: __all__定義により外部からのimportを制御
__all__ = [
    'BaseEvaluator',
    'SingleLegSquatEvaluator',
    'CrossStepEvaluator',
    'JumpLandingEvaluator',
    'SkaterLungeEvaluator',
    'StrideMinicryEvaluator',
    'PushPullEvaluator',
    'UpperBodySwingEvaluator',
]
