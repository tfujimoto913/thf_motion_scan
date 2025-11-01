"""
Purpose: Dashboard設定管理
Responsibility: AWS リソース名、AccountId取得
Dependencies: boto3
Created: 2025-10-26 by Claude
Decision Log: ADR-014（Phase 5: Dashboard実装）

CRITICAL: AccountIdは実行時に自動取得
"""
import boto3
from typing import Dict, Optional


# 環境設定
DEFAULT_ENV = "prod"
AVAILABLE_ENVIRONMENTS = [DEFAULT_ENV]


PERFORMANCE_LIMITS = {
    "max_records": 50,
    "max_months": 12,
    "cache_ttl_seconds": 300,
    "slow_query_threshold_ms": 800,
}


def get_available_environments() -> list[str]:
    """
    What: ダッシュボードで利用可能な環境リストを取得
    Why: サイドバー環境セレクタに反映
    Design Decision: 現状はprodのみを公開（将来拡張の余地を残す）
    """
    return AVAILABLE_ENVIRONMENTS.copy()


def get_aws_account_id() -> Optional[str]:
    """
    What: AWS Account ID取得
    Why: S3バケット名、リソース名に使用
    Design Decision: STS GetCallerIdentityで取得（ADR-014）

    Returns:
        str: AWS Account ID（例: 123456789012）

    CRITICAL: AWS認証情報が設定されていることを前提
    """
    try:
        sts_client = boto3.client('sts')
        response = sts_client.get_caller_identity()
        return response['Account']
    except Exception as e:
        print(f"AWS Account ID取得エラー: {e}")
        return None


def _build_environment_resources(account_id: str, env: str) -> Dict[str, str]:
    """
    What: 環境ごとのAWSリソース名を生成
    Why: dev/staging/prod でリソースパターンが異なるため
    Design Decision: prodは既存の命名を踏襲し、その他は接頭辞にenvを付与
    """
    env = env.lower()

    if env == "prod":
        return {
            "videos_bucket": f"thf-motion-scan-videos-{account_id}",
            "results_bucket": f"thf-motion-scan-results-{account_id}",
            "table_name": "thf-motion-scan-results",
            "sqs_queue": "thf-motion-scan-processing-queue",
            "api_endpoint": "https://api.thf-motion-scan.com",
        }

    prefix = f"thf-motion-scan-{env}"
    return {
        "videos_bucket": f"{prefix}-videos-{account_id}",
        "results_bucket": f"{prefix}-results-{account_id}",
        "table_name": f"{prefix}-results",
        "sqs_queue": f"{prefix}-processing-queue",
        "api_endpoint": f"https://{env}-api.thf-motion-scan.com",
    }


def get_resource_names(env: str = DEFAULT_ENV):
    """
    What: AWSリソース名取得
    Why: S3バケット名、DynamoDBテーブル名を動的生成
    Design Decision: AccountIdを含むリソース名（ADR-007準拠）

    Returns:
        dict: リソース名辞書

    CRITICAL: AccountId取得失敗時はNoneを返す
    """
    account_id = get_aws_account_id()

    if not account_id:
        return None

    resources = _build_environment_resources(account_id, env)
    resources["account_id"] = account_id
    resources["environment"] = env
    return resources


# テストタイプ定義（T01-T07の正式順序）
TEST_TYPES = [
    'single_leg_squat',    # T01
    'skater_lunge',        # T02
    'stride_mimic',        # T03
    'jump_landing',        # T04
    'upper_body_swing',    # T05
    'push_pull',           # T06
    'cross_step'           # T07
]

# テストタイプ表示名（日本語）
TEST_TYPE_DISPLAY = {
    'single_leg_squat': '片脚スタンススクワット',
    'skater_lunge': 'スケーターランジ',
    'stride_mimic': 'スケートストライド模倣',
    'jump_landing': 'ミニジャンプ＆着地',
    'upper_body_swing': '上体スイング',
    'push_pull': 'プッシュプル動作',
    'cross_step': 'クロスステップ模倣'
}
