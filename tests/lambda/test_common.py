"""
Purpose: Lambda共通モジュールのユニットテスト
Responsibility: response_utils, validators, jwt_utilsのテスト
Dependencies: pytest, sys, os
Created: 2025-10-27 by Claude Code
Decision Log: ADR-018

CRITICAL: JWT_SECRET_KEYはテスト環境変数で設定
"""

import os
import sys
import json
import pytest
from datetime import datetime, timedelta

# lambdaモジュールのパス追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../lambda'))

from common.response_utils import success_response, error_response, cors_headers
from common.validators import (
    validate_required_fields,
    validate_email,
    validate_player_id,
    validate_team_id,
    validate_jersey_number,
    validate_password,
    validate_kana_name,
    validate_lateral_characteristic,
    validate_height
)
from common.jwt_utils import generate_jwt, verify_jwt, extract_bearer_token


# ========================================
# response_utils tests
# ========================================

def test_cors_headers():
    """
    What: CORSヘッダーの生成テスト
    Why: CORS対応の動作保証
    """
    headers = cors_headers()

    assert headers['Content-Type'] == 'application/json'
    assert headers['Access-Control-Allow-Origin'] == '*'
    assert 'Access-Control-Allow-Headers' in headers
    assert 'Access-Control-Allow-Methods' in headers


def test_success_response():
    """
    What: 成功レスポンスの生成テスト
    Why: API Gateway統合レスポンス形式の保証
    """
    response = success_response(
        data={'result': 'ok'},
        status_code=200,
        message='Success'
    )

    assert response['statusCode'] == 200
    assert 'headers' in response
    assert 'body' in response

    body = json.loads(response['body'])
    assert body['success'] is True
    assert body['message'] == 'Success'
    assert body['data']['result'] == 'ok'


def test_error_response():
    """
    What: エラーレスポンスの生成テスト
    Why: エラーハンドリングの統一保証
    """
    response = error_response(
        error_message='Invalid input',
        status_code=400,
        error_code='VALIDATION_ERROR',
        details={'field': 'email'}
    )

    assert response['statusCode'] == 400
    assert 'headers' in response
    assert 'body' in response

    body = json.loads(response['body'])
    assert body['success'] is False
    assert body['error'] == 'Invalid input'
    assert body['errorCode'] == 'VALIDATION_ERROR'
    assert body['details']['field'] == 'email'


# ========================================
# validators tests
# ========================================

def test_validate_required_fields_success():
    """
    What: 必須フィールド検証（成功ケース）
    Why: 正常データの通過保証
    """
    data = {'name': 'test', 'age': 25}
    is_valid, error_msg = validate_required_fields(data, ['name', 'age'])

    assert is_valid is True
    assert error_msg is None


def test_validate_required_fields_missing():
    """
    What: 必須フィールド検証（失敗ケース）
    Why: 不足フィールドの検出保証
    """
    data = {'name': 'test'}
    is_valid, error_msg = validate_required_fields(data, ['name', 'age'])

    assert is_valid is False
    assert 'age' in error_msg


def test_validate_email_valid():
    """
    What: メールアドレス検証（有効ケース）
    Why: 正しいメール形式の通過保証
    """
    is_valid, error_msg = validate_email('test@example.com')

    assert is_valid is True
    assert error_msg is None


def test_validate_email_invalid():
    """
    What: メールアドレス検証（無効ケース）
    Why: 不正なメール形式の検出保証
    """
    is_valid, error_msg = validate_email('invalid-email')

    assert is_valid is False
    assert 'Invalid email format' in error_msg


def test_validate_player_id_valid():
    """
    What: 選手ID検証（有効ケース）
    Why: plr_{teamSlug}_{jerseyNumber}形式の保証
    """
    is_valid, error_msg = validate_player_id('plr_sakae_19')

    assert is_valid is True
    assert error_msg is None


def test_validate_player_id_invalid():
    """
    What: 選手ID検証（無効ケース）
    Why: 不正な形式の検出保証
    """
    is_valid, error_msg = validate_player_id('invalid_id')

    assert is_valid is False
    assert 'Invalid player ID format' in error_msg


def test_validate_team_id_valid():
    """
    What: チームID検証（有効ケース）
    Why: tm_{teamSlug}形式の保証
    """
    is_valid, error_msg = validate_team_id('tm_sakae')

    assert is_valid is True
    assert error_msg is None


def test_validate_team_id_invalid():
    """
    What: チームID検証（無効ケース）
    Why: 不正な形式の検出保証
    """
    is_valid, error_msg = validate_team_id('invalid_team')

    assert is_valid is False
    assert 'Invalid team ID format' in error_msg


def test_validate_jersey_number_valid():
    """
    What: 背番号検証（有効ケース）
    Why: 1-99範囲の保証
    """
    is_valid, error_msg = validate_jersey_number(19)

    assert is_valid is True
    assert error_msg is None


def test_validate_jersey_number_out_of_range():
    """
    What: 背番号検証（範囲外ケース）
    Why: 1-99範囲外の検出保証
    """
    is_valid, error_msg = validate_jersey_number(100)

    assert is_valid is False
    assert 'between 1 and 99' in error_msg


def test_validate_password_valid():
    """
    What: パスワード検証（有効ケース）
    Why: 8文字以上、英数字混在の保証
    """
    is_valid, error_msg = validate_password('secure123')

    assert is_valid is True
    assert error_msg is None


def test_validate_password_too_short():
    """
    What: パスワード検証（短すぎるケース）
    Why: 8文字未満の検出保証
    """
    is_valid, error_msg = validate_password('short1')

    assert is_valid is False
    assert 'at least 8 characters' in error_msg


def test_validate_password_no_digit():
    """
    What: パスワード検証（数字なしケース）
    Why: 英数字混在要件の保証
    """
    is_valid, error_msg = validate_password('onlyletters')

    assert is_valid is False
    assert 'letters and numbers' in error_msg


def test_validate_kana_name_hiragana_valid():
    """
    What: Kana名検証（ひらがな有効ケース）
    Why: ひらがな入力の通過保証
    """
    is_valid, error_msg = validate_kana_name('たろう', 'First name kana')

    assert is_valid is True
    assert error_msg is None


def test_validate_kana_name_katakana_valid():
    """
    What: Kana名検証（カタカナ有効ケース）
    Why: カタカナ入力の通過保証
    """
    is_valid, error_msg = validate_kana_name('タロウ', 'First name kana')

    assert is_valid is True
    assert error_msg is None


def test_validate_kana_name_invalid_kanji():
    """
    What: Kana名検証（漢字無効ケース）
    Why: 漢字の検出保証
    """
    is_valid, error_msg = validate_kana_name('太郎', 'First name kana')

    assert is_valid is False
    assert 'hiragana or katakana' in error_msg


def test_validate_kana_name_invalid_alphabet():
    """
    What: Kana名検証（英字無効ケース）
    Why: アルファベットの検出保証
    """
    is_valid, error_msg = validate_kana_name('taro', 'First name kana')

    assert is_valid is False
    assert 'hiragana or katakana' in error_msg


def test_validate_lateral_characteristic_right():
    """
    What: 利き手/足検証（right有効ケース）
    Why: right入力の通過保証
    """
    is_valid, error_msg = validate_lateral_characteristic('right', 'Dominant hand')

    assert is_valid is True
    assert error_msg is None


def test_validate_lateral_characteristic_left():
    """
    What: 利き手/足検証（left有効ケース）
    Why: left入力の通過保証
    """
    is_valid, error_msg = validate_lateral_characteristic('left', 'Dominant foot')

    assert is_valid is True
    assert error_msg is None


def test_validate_lateral_characteristic_uppercase():
    """
    What: 利き手/足検証（大文字入力ケース）
    Why: 大文字の正規化保証
    """
    is_valid, error_msg = validate_lateral_characteristic('RIGHT', 'Shooting hand')

    assert is_valid is True
    assert error_msg is None


def test_validate_lateral_characteristic_invalid():
    """
    What: 利き手/足検証（無効ケース）
    Why: right/left以外の検出保証
    """
    is_valid, error_msg = validate_lateral_characteristic('center', 'Dominant hand')

    assert is_valid is False
    assert "'right' or 'left'" in error_msg


def test_validate_height_valid():
    """
    What: 身長検証（正常ケース）
    Why: 標準的な身長値の受け入れ保証
    """
    is_valid, error_msg = validate_height(170)

    assert is_valid is True
    assert error_msg is None


def test_validate_height_boundary_min():
    """
    What: 身長検証（最小境界値）
    Why: 100cmが受け入れられることを保証
    """
    is_valid, error_msg = validate_height(100)

    assert is_valid is True
    assert error_msg is None


def test_validate_height_boundary_max():
    """
    What: 身長検証（最大境界値）
    Why: 250cmが受け入れられることを保証
    """
    is_valid, error_msg = validate_height(250)

    assert is_valid is True
    assert error_msg is None


def test_validate_height_too_small():
    """
    What: 身長検証（範囲外・小）
    Why: 99cm以下が拒否されることを保証
    """
    is_valid, error_msg = validate_height(99)

    assert is_valid is False
    assert "100 and 250" in error_msg


def test_validate_height_too_large():
    """
    What: 身長検証（範囲外・大）
    Why: 251cm以上が拒否されることを保証
    """
    is_valid, error_msg = validate_height(251)

    assert is_valid is False
    assert "100 and 250" in error_msg


def test_validate_height_invalid_type():
    """
    What: 身長検証（型エラー）
    Why: 非整数値が拒否されることを保証
    """
    is_valid, error_msg = validate_height("170")

    assert is_valid is False
    assert "must be an integer" in error_msg


# ========================================
# jwt_utils tests
# ========================================

@pytest.fixture
def setup_jwt_secret():
    """
    What: JWT_SECRET_KEY環境変数のセットアップ
    Why: JWT生成/検証テストの前提条件
    """
    os.environ['JWT_SECRET_KEY'] = 'test-secret-key-for-unit-testing'
    yield
    del os.environ['JWT_SECRET_KEY']


def test_generate_jwt(setup_jwt_secret):
    """
    What: JWT生成テスト
    Why: 正しいペイロード構造の保証
    """
    token = generate_jwt('plr_sakae_19', 'tm_sakae', expiration_minutes=60)

    assert isinstance(token, str)
    assert len(token) > 0


def test_verify_jwt_valid(setup_jwt_secret):
    """
    What: JWT検証テスト（有効トークン）
    Why: 正常トークンの検証成功保証
    """
    token = generate_jwt('plr_sakae_19', 'tm_sakae', expiration_minutes=60)

    is_valid, payload, error_msg = verify_jwt(token)

    assert is_valid is True
    assert payload['playerId'] == 'plr_sakae_19'
    assert payload['teamId'] == 'tm_sakae'
    assert error_msg is None


def test_verify_jwt_invalid_signature(setup_jwt_secret):
    """
    What: JWT検証テスト（無効シグネチャ）
    Why: 改ざんトークンの検出保証
    """
    token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid.signature'

    is_valid, payload, error_msg = verify_jwt(token)

    assert is_valid is False
    assert payload is None
    assert error_msg is not None


def test_extract_bearer_token_valid():
    """
    What: Bearerトークン抽出テスト（有効ケース）
    Why: 正しいAuthorization形式の保証
    """
    auth_header = 'Bearer test-token-12345'

    is_valid, token, error_msg = extract_bearer_token(auth_header)

    assert is_valid is True
    assert token == 'test-token-12345'
    assert error_msg is None


def test_extract_bearer_token_missing():
    """
    What: Bearerトークン抽出テスト（ヘッダーなし）
    Why: Authorization不足の検出保証
    """
    is_valid, token, error_msg = extract_bearer_token(None)

    assert is_valid is False
    assert token is None
    assert 'missing' in error_msg


def test_extract_bearer_token_invalid_format():
    """
    What: Bearerトークン抽出テスト（無効形式）
    Why: Bearer形式以外の検出保証
    """
    auth_header = 'Basic invalid-format'

    is_valid, token, error_msg = extract_bearer_token(auth_header)

    assert is_valid is False
    assert token is None
    assert 'Bearer' in error_msg
