"""
Purpose: クライアントID形式のテスト
Responsibility: FirstLast-yymmdd形式のパース・表示機能を検証
Dependencies: pytest, dashboard.app
Created: 2025-10-26 by Claude
Decision Log: ADR-015（予定）

CRITICAL: 正規表現パターンと日付変換ロジックを検証
"""
import sys
from pathlib import Path

# dashboard/app.py をインポート
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "dashboard"))

from app import parse_client_id, format_client_id_display


def test_parse_client_id_valid():
    """
    What: 有効なクライアントIDのパーステスト
    Why: FirstLast-yymmdd形式が正しく解析されることを確認
    Design Decision: 2000年代/1900年代の判定ロジックを検証（ADR-015予定）
    """
    # 2010年代生まれ（00-30）
    video_id = "bucket/videos/test/TaroYamada-100315.mp4"
    result = parse_client_id(video_id)

    assert result is not None
    assert result['first_name'] == 'Taro'
    assert result['last_name'] == 'Yamada'
    assert result['birth_date'] == '2010-03-15'
    assert result['raw'] == 'TaroYamada-100315'


def test_parse_client_id_1990s():
    """
    What: 1990年代生まれのクライアントIDパーステスト
    Why: yy > 30 の場合に1900年代と判定されることを確認
    """
    video_id = "bucket/videos/test/KenjiTanaka-910512.mp4"
    result = parse_client_id(video_id)

    assert result is not None
    assert result['first_name'] == 'Kenji'
    assert result['last_name'] == 'Tanaka'
    assert result['birth_date'] == '1991-05-12'


def test_parse_client_id_invalid():
    """
    What: 無効なクライアントIDのパーステスト
    Why: 旧形式（demo_athlete_001等）ではNoneを返すことを確認
    """
    # 旧形式
    video_id = "bucket/videos/test/demo_athlete_001.mp4"
    result = parse_client_id(video_id)

    assert result is None


def test_format_client_id_display_valid():
    """
    What: クライアントID表示フォーマットテスト
    Why: FirstLast-yymmdd → "First Last (yyyy-mm-dd生)" 変換を確認
    """
    video_id = "bucket/videos/test/YukiSato-110822.mp4"
    formatted = format_client_id_display(video_id)

    assert formatted == "Yuki Sato (2011-08-22生)"


def test_format_client_id_display_invalid():
    """
    What: 無効なクライアントIDの表示フォーマットテスト
    Why: パース失敗時は元のvideo_idを返すことを確認
    """
    video_id = "bucket/videos/test/demo_athlete_001.mp4"
    formatted = format_client_id_display(video_id)

    # パース失敗時は元のvideo_idを返す
    assert formatted == video_id


def test_all_demo_clients():
    """
    What: デモクライアント全件のパーステスト
    Why: scripts/generate_demo_data.py で定義された全クライアントIDを検証
    """
    demo_clients = [
        ('TaroYamada-100315', 'Taro Yamada (2010-03-15生)'),
        ('YukiSato-110822', 'Yuki Sato (2011-08-22生)'),
        ('KenjiTanaka-091201', 'Kenji Tanaka (2009-12-01生)'),
        ('AikoWatanabe-120510', 'Aiko Watanabe (2012-05-10生)'),
        ('RyoSuzuki-100730', 'Ryo Suzuki (2010-07-30生)'),
        ('MaiNakamura-110915', 'Mai Nakamura (2011-09-15生)'),
        ('SotaKobayashi-091105', 'Sota Kobayashi (2009-11-05生)')
    ]

    for client_id, expected_display in demo_clients:
        video_id = f"bucket/videos/test/{client_id}.mp4"
        formatted = format_client_id_display(video_id)
        assert formatted == expected_display, f"Failed for {client_id}: expected '{expected_display}', got '{formatted}'"


if __name__ == "__main__":
    # 簡易テスト実行
    test_parse_client_id_valid()
    test_parse_client_id_1990s()
    test_parse_client_id_invalid()
    test_format_client_id_display_valid()
    test_format_client_id_display_invalid()
    test_all_demo_clients()

    print("✅ All client ID format tests passed!")
