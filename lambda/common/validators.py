"""
Purpose: 入力検証ユーティリティ
Responsibility: リクエストパラメータの検証とバリデーション
Dependencies: re, typing
Created: 2025-10-27 by Claude Code
Decision Log: ADR-018

CRITICAL: セキュリティ対策として全入力値を検証必須
"""

import re
from typing import Dict, List, Any, Optional, Tuple


def validate_required_fields(
    data: Dict[str, Any],
    required_fields: List[str]
) -> Tuple[bool, Optional[str]]:
    """
    What: 必須フィールドの存在確認
    Why: API入力値の整合性保証
    Design Decision: エラーメッセージに不足フィールド名を含める（ADR-018）

    Args:
        data: 検証対象の辞書
        required_fields: 必須フィールド名のリスト

    Returns:
        (is_valid, error_message) のタプル

    CRITICAL: 全API エンドポイントで入力検証必須
    """
    missing_fields = [field for field in required_fields if field not in data or not data[field]]

    if missing_fields:
        return False, f"Missing required fields: {', '.join(missing_fields)}"

    return True, None


def validate_email(email: str) -> Tuple[bool, Optional[str]]:
    """
    What: メールアドレス形式の検証
    Why: コーチ・管理者アカウントでのメール形式保証
    Design Decision: RFC 5322簡易版の正規表現使用（ADR-018）

    Args:
        email: 検証対象のメールアドレス

    Returns:
        (is_valid, error_message) のタプル

    CRITICAL: SQLインジェクション対策として正規表現検証必須
    """
    if not email:
        return False, "Email is required"

    # RFC 5322簡易版: 一般的なメールアドレス形式
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(email_pattern, email):
        return False, "Invalid email format"

    return True, None


def validate_player_id(player_id: str) -> Tuple[bool, Optional[str]]:
    """
    What: 選手ID形式の検証
    Why: 命名規則統一とセキュリティ確保
    Design Decision: plr_{teamSlug}_{jerseyNumber} 形式強制（ADR-018）

    Args:
        player_id: 検証対象の選手ID

    Returns:
        (is_valid, error_message) のタプル

    Expected format: plr_sakae_19

    CRITICAL: player_id形式は変更禁止（DynamoDB PKに使用）
    """
    if not player_id:
        return False, "Player ID is required"

    # 形式: plr_{teamSlug}_{jerseyNumber}
    # teamSlug: 英数字・ハイフン（3-20文字）
    # jerseyNumber: 1-99
    player_id_pattern = r'^plr_[a-z0-9-]{3,20}_\d{1,2}$'

    if not re.match(player_id_pattern, player_id):
        return False, "Invalid player ID format (expected: plr_{teamSlug}_{jerseyNumber})"

    return True, None


def validate_team_id(team_id: str) -> Tuple[bool, Optional[str]]:
    """
    What: チームID形式の検証
    Why: 命名規則統一とセキュリティ確保
    Design Decision: tm_{teamSlug} 形式強制（ADR-018）

    Args:
        team_id: 検証対象のチームID

    Returns:
        (is_valid, error_message) のタプル

    Expected format: tm_sakae

    CRITICAL: team_id形式は変更禁止（DynamoDB PKに使用）
    """
    if not team_id:
        return False, "Team ID is required"

    # 形式: tm_{teamSlug}
    # teamSlug: 英数字・ハイフン（3-20文字）
    team_id_pattern = r'^tm_[a-z0-9-]{3,20}$'

    if not re.match(team_id_pattern, team_id):
        return False, "Invalid team ID format (expected: tm_{teamSlug})"

    return True, None


def validate_jersey_number(jersey_number: int) -> Tuple[bool, Optional[str]]:
    """
    What: 背番号の範囲検証
    Why: アイスホッケー背番号規則準拠（1-99）
    Design Decision: 1-99の範囲制限（ADR-018）

    Args:
        jersey_number: 検証対象の背番号

    Returns:
        (is_valid, error_message) のタプル

    CRITICAL: 背番号範囲は変更禁止（スポーツ規則準拠）
    """
    if not isinstance(jersey_number, int):
        return False, "Jersey number must be an integer"

    if jersey_number < 1 or jersey_number > 99:
        return False, "Jersey number must be between 1 and 99"

    return True, None


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    What: パスワード強度の検証
    Why: セキュリティ確保（選手ログイン）
    Design Decision: 8文字以上、英数字混在必須（ADR-018）

    Args:
        password: 検証対象のパスワード

    Returns:
        (is_valid, error_message) のタプル

    CRITICAL: パスワード要件は緩和禁止（セキュリティポリシー）
    """
    if not password:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    # 英数字混在チェック
    has_letter = bool(re.search(r'[a-zA-Z]', password))
    has_digit = bool(re.search(r'\d', password))

    if not (has_letter and has_digit):
        return False, "Password must contain both letters and numbers"

    return True, None


def validate_kana_name(kana_name: str, field_name: str = "Kana name") -> Tuple[bool, Optional[str]]:
    """
    What: 日本語振り仮名の検証
    Why: 選手名の正規化とUI表示品質向上
    Design Decision: ひらがな・カタカナのみ許可（ADR-018）

    Args:
        kana_name: 検証対象の振り仮名
        field_name: エラーメッセージ用のフィールド名

    Returns:
        (is_valid, error_message) のタプル

    CRITICAL: 全角ひらがな・カタカナのみ（半角・漢字は不可）
    """
    if not kana_name:
        return False, f"{field_name} is required"

    # 長さチェック（1-20文字）
    if len(kana_name) < 1 or len(kana_name) > 20:
        return False, f"{field_name} must be between 1 and 20 characters"

    # ひらがな（ぁ-んー）またはカタカナ（ァ-ヴー）のみ許可
    kana_pattern = r'^[ぁ-んァ-ヴー]+$'

    if not re.match(kana_pattern, kana_name):
        return False, f"{field_name} must contain only hiragana or katakana characters"

    return True, None


def validate_lateral_characteristic(
    value: str,
    field_name: str = "Lateral characteristic"
) -> Tuple[bool, Optional[str]]:
    """
    What: 利き手・利き足・シュートハンドの検証
    Why: 身体特性の標準化
    Design Decision: "right" or "left" のみ許可（ADR-018）

    Args:
        value: 検証対象の値
        field_name: エラーメッセージ用のフィールド名

    Returns:
        (is_valid, error_message) のタプル

    CRITICAL: 大文字・小文字は正規化するが、入力値は "right" or "left" のみ
    """
    if not value:
        return False, f"{field_name} is required"

    # 大文字・小文字を統一して比較
    normalized_value = value.lower().strip()

    if normalized_value not in ['right', 'left']:
        return False, f"{field_name} must be either 'right' or 'left'"

    return True, None


def validate_height(height: int) -> Tuple[bool, Optional[str]]:
    """
    What: 身長の検証
    Why: 身体特性データの品質保証
    Design Decision: 100-250cmの範囲チェック、オプショナル（ADR-020）

    Args:
        height: 検証対象の身長（cm、int型）

    Returns:
        (is_valid, error_message) のタプル

    Expected range: 100-250cm（ジュニア〜成人アスリート）

    CRITICAL: heightはオプショナルフィールド（既存データとの互換性）
    """
    if not isinstance(height, int):
        return False, "Height must be an integer"

    if height < 100 or height > 250:
        return False, "Height must be between 100 and 250 cm"

    return True, None
