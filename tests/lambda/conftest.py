"""
Purpose: pytest共通設定
Responsibility: テスト環境変数の一元管理
Dependencies: pytest
Created: 2025-10-29 by Claude Code
Decision Log: Phase 2.5 - Stage 1

CRITICAL: 全テストで共有する環境変数をここで設定
"""

import os
import pytest


# CRITICAL: モジュールインポート前に環境変数を設定
# pytest fixture よりも先に実行される
os.environ['TABLE_NAME'] = 'test-table'
os.environ['QRCODE_BUCKET'] = 'test-qrcode-bucket'
os.environ['VIDEOS_BUCKET'] = 'test-videos-bucket'
os.environ['JWT_SECRET_KEY'] = 'test-secret-key'
os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'
