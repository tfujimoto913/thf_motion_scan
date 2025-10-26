"""
Purpose: Dashboard設定管理
Responsibility: AWS リソース名、AccountId取得
Dependencies: boto3
Created: 2025-10-26 by Claude
Decision Log: ADR-014（Phase 5: Dashboard実装）

CRITICAL: AccountIdは実行時に自動取得
"""
import boto3
from typing import Optional


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


def get_resource_names():
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

    return {
        'videos_bucket': f'thf-motion-scan-videos-{account_id}',
        'results_bucket': f'thf-motion-scan-results-{account_id}',
        'table_name': 'thf-motion-scan-results',
        'account_id': account_id
    }


# テストタイプ定義
TEST_TYPES = [
    'single_leg_squat',
    'upper_body_swing',
    'skater_lunge',
    'cross_step',
    'stride_mimic',
    'push_pull',
    'jump_landing'
]

# テストタイプ表示名（日本語）
TEST_TYPE_DISPLAY = {
    'single_leg_squat': '片脚スタンススクワット',
    'upper_body_swing': '上体スイング',
    'skater_lunge': 'スケーターランジ',
    'cross_step': 'クロスステップ模倣',
    'stride_mimic': 'スケートストライド模倣',
    'push_pull': 'プッシュプル動作',
    'jump_landing': 'ミニジャンプ＆着地'
}
