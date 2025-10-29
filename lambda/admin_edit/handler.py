"""
Purpose: 管理者用編集Lambda関数
Responsibility: チーム・選手情報の編集API
Dependencies: boto3, sys, json
Created: 2025-10-29 by Claude Code
Decision Log: Phase 2.5 - Stage 1

CRITICAL: 認証は Stage 1では未実装（将来実装予定）
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, Any

# 共通モジュールのパス追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from common.response_utils import success_response, error_response
from common.dynamodb_utils import get_item, update_item


# CRITICAL: 編集不可フィールドの定義（Phase 2.5 - Stage 1）
FORBIDDEN_TEAM_FIELDS = ['teamId', 'teamSlug', 'teamCode', 'registrationUrl', 'qrCodeS3Key']
ALLOWED_TEAM_FIELDS = ['teamName']


def update_team(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    What: チーム編集エンドポイント
    Why: 管理者によるチーム情報の編集
    Design Decision: PATCH /admin/teams/{teamId}（Phase 2.5 - Stage 1）

    Request:
        pathParameters: {'teamId': 'tm_sakae'}
        body: {
            'teamName': '栄フレッシュ2025'
        }

    Response:
        {
            "success": true,
            "data": {
                "teamId": "tm_sakae",
                "teamName": "栄フレッシュ2025",
                "updatedAt": "2025-10-29T12:00:00Z"
            }
        }

    CRITICAL: teamName のみ編集可能
    PHASE CORE LOGIC: 編集可能フィールドのホワイトリスト検証
    """
    try:
        # パスパラメータ取得
        team_id = event.get('pathParameters', {}).get('teamId')
        if not team_id:
            return error_response('teamId is required', 400, 'VALIDATION_ERROR')

        # リクエストボディ解析
        body = json.loads(event.get('body', '{}'))

        if not body:
            return error_response('Request body is required', 400, 'VALIDATION_ERROR')

        # CRITICAL: 編集不可フィールドのチェック
        forbidden_fields = [field for field in body.keys() if field in FORBIDDEN_TEAM_FIELDS]
        if forbidden_fields:
            return error_response(
                f"Fields not allowed to update: {', '.join(forbidden_fields)}",
                400,
                'FORBIDDEN_FIELD'
            )

        # CRITICAL: 許可されていないフィールドのチェック
        unknown_fields = [field for field in body.keys() if field not in ALLOWED_TEAM_FIELDS]
        if unknown_fields:
            return error_response(
                f"Unknown fields: {', '.join(unknown_fields)}",
                400,
                'UNKNOWN_FIELD'
            )

        # チーム存在確認
        team = get_item(f"TEAM#{team_id}", "METADATA")
        if not team:
            return error_response(
                f"Team not found: {team_id}",
                404,
                'TEAM_NOT_FOUND'
            )

        # PHASE CORE LOGIC: DynamoDB更新式構築
        update_expression_parts = []
        expression_attribute_values = {}

        if 'teamName' in body:
            update_expression_parts.append('#teamName = :teamName')
            expression_attribute_values[':teamName'] = body['teamName']

        # updatedAt追加
        update_expression_parts.append('#updatedAt = :updatedAt')
        expression_attribute_values[':updatedAt'] = datetime.utcnow().isoformat() + 'Z'

        update_expression = 'SET ' + ', '.join(update_expression_parts)
        expression_attribute_names = {
            '#teamName': 'teamName',
            '#updatedAt': 'updatedAt'
        }

        # DynamoDB更新
        update_item(
            pk=f"TEAM#{team_id}",
            sk="METADATA",
            update_expression=update_expression,
            expression_attribute_values=expression_attribute_values,
            expression_attribute_names=expression_attribute_names
        )

        # 更新後のデータ取得
        updated_team = get_item(f"TEAM#{team_id}", "METADATA")

        # レスポンス
        return success_response(
            data={
                'teamId': updated_team['teamId'],
                'teamName': updated_team['teamName'],
                'updatedAt': updated_team['updatedAt']
            },
            status_code=200,
            message='Team updated successfully'
        )

    except ValueError as e:
        return error_response(str(e), 400, 'VALIDATION_ERROR')

    except Exception as e:
        # CRITICAL: エラーログに個人情報を含めない
        print(f"Error updating team: {str(e)}")
        return error_response(
            'Internal server error',
            500,
            'INTERNAL_ERROR'
        )


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    What: Lambda統合ハンドラー
    Why: API Gatewayからのルーティング
    Design Decision: httpMethodとpathでルーティング（Phase 2.5 - Stage 1）

    CRITICAL: 認証は Stage 1では未実装
    """
    path = event.get('path', '')

    if '/admin/teams/' in path:
        return update_team(event, context)
    elif '/admin/players/' in path:
        # TODO: update_player実装（次のコミット）
        return error_response('Not implemented yet', 501, 'NOT_IMPLEMENTED')
    else:
        return error_response('Invalid path', 404, 'INVALID_PATH')
