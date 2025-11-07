"""
Purpose: セッショングルーピング機能のテスト
Responsibility: 7種目をathlete_id + session_idでグルーピングして1セッションにまとめる
Dependencies: pytest
Created: 2025-11-01 by Claude Code
Decision Log: Phase 5 - Stage 1

CRITICAL: TDD Red → テストを先に書いて失敗を確認
"""
import pytest
from datetime import datetime
from decimal import Decimal


def test_group_by_session_7tests_complete():
    """
    What: 7種目完全データのグルーピングテスト
    Why: 1セッション = 7種目すべてを含む1レコード
    Design Decision: athlete_id + session_id でグルーピング（ADR-023）

    CRITICAL: 560点満点（7種目×80点）
    """
    # テストデータ: 7種目分のDynamoDBレコード
    from dashboard.session_dao import group_tests_by_session

    test_data = [
        {
            'video_id': 'bucket/videos/single_leg_squat/test1.mp4',
            'processed_at': '2025-10-31T15:19:50.454967',
            'athlete_id': 'athlete_001',
            'session_id': '20251031-1518-X',
            'test_type': 'single_leg_squat',
            'score': Decimal('56.4'),
            'max_score': Decimal('80'),
            'evaluation': {'version': 'v2.1'}
        },
        {
            'video_id': 'bucket/videos/skater_lunge/test2.mp4',
            'processed_at': '2025-10-31T15:20:00.123456',
            'athlete_id': 'athlete_001',
            'session_id': '20251031-1518-X',
            'test_type': 'skater_lunge',
            'score': Decimal('60.0'),
            'max_score': Decimal('80'),
            'evaluation': {'version': 'v2.1'}
        },
        {
            'video_id': 'bucket/videos/stride_mimic/test3.mp4',
            'processed_at': '2025-10-31T15:21:00.123456',
            'athlete_id': 'athlete_001',
            'session_id': '20251031-1518-X',
            'test_type': 'stride_mimic',
            'score': Decimal('70.0'),
            'max_score': Decimal('80'),
            'evaluation': {'version': 'v2.1'}
        },
        {
            'video_id': 'bucket/videos/jump_landing/test4.mp4',
            'processed_at': '2025-10-31T15:22:00.123456',
            'athlete_id': 'athlete_001',
            'session_id': '20251031-1518-X',
            'test_type': 'jump_landing',
            'score': Decimal('65.0'),
            'max_score': Decimal('80'),
            'evaluation': {'version': 'v2.1'}
        },
        {
            'video_id': 'bucket/videos/upper_body_swing/test5.mp4',
            'processed_at': '2025-10-31T15:23:00.123456',
            'athlete_id': 'athlete_001',
            'session_id': '20251031-1518-X',
            'test_type': 'upper_body_swing',
            'score': Decimal('72.0'),
            'max_score': Decimal('80'),
            'evaluation': {'version': 'v2.1'}
        },
        {
            'video_id': 'bucket/videos/push_pull/test6.mp4',
            'processed_at': '2025-10-31T15:24:00.123456',
            'athlete_id': 'athlete_001',
            'session_id': '20251031-1518-X',
            'test_type': 'push_pull',
            'score': Decimal('68.0'),
            'max_score': Decimal('80'),
            'evaluation': {'version': 'v2.1'}
        },
        {
            'video_id': 'bucket/videos/cross_step/test7.mp4',
            'processed_at': '2025-10-31T15:25:00.123456',
            'athlete_id': 'athlete_001',
            'session_id': '20251031-1518-X',
            'test_type': 'cross_step',
            'score': Decimal('75.0'),
            'max_score': Decimal('80'),
            'evaluation': {'version': 'v2.1'}
        }
    ]

    # グルーピング実行
    sessions = group_tests_by_session(test_data)

    # 検証
    assert len(sessions) == 1, "7種目は1セッションにグルーピングされる"

    session = sessions[0]
    assert session['athlete_id'] == 'athlete_001'
    assert session['session_id'] == '20251031-1518-X'
    assert session['grand_total'] == 466.4, "総合スコア = 56.4+60+70+65+72+68+75"
    assert session['grand_max'] == 560, "最大スコア = 7種目×80点"
    assert abs(session['percentage'] - 83.29) < 0.01, "達成率 = (466.4/560)*100"
    assert len(session['tests']) == 7, "7種目分のデータが含まれる"
    assert session['rules_version'] == 'v2.1', "全種目のrules_versionが同一"


def test_group_by_session_incomplete_tests():
    """
    What: 種目不足時（7種目未満）のグルーピングテスト
    Why: 撮影途中・処理中のセッションも表示する
    Design Decision: 種目不足時はis_complete=Falseフラグを付与

    CRITICAL: 5種目しかなくても1セッションとしてカウント
    """
    from dashboard.session_dao import group_tests_by_session

    test_data = [
        {
            'video_id': 'bucket/videos/single_leg_squat/test1.mp4',
            'processed_at': '2025-10-31T15:19:50.454967',
            'athlete_id': 'athlete_002',
            'session_id': '20251031-1600-Y',
            'test_type': 'single_leg_squat',
            'score': Decimal('50.0'),
            'max_score': Decimal('80'),
            'evaluation': {'version': 'v2.1'}
        },
        {
            'video_id': 'bucket/videos/skater_lunge/test2.mp4',
            'processed_at': '2025-10-31T15:20:00.123456',
            'athlete_id': 'athlete_002',
            'session_id': '20251031-1600-Y',
            'test_type': 'skater_lunge',
            'score': Decimal('55.0'),
            'max_score': Decimal('80'),
            'evaluation': {'version': 'v2.1'}
        },
        {
            'video_id': 'bucket/videos/stride_mimic/test3.mp4',
            'processed_at': '2025-10-31T15:21:00.123456',
            'athlete_id': 'athlete_002',
            'session_id': '20251031-1600-Y',
            'test_type': 'stride_mimic',
            'score': Decimal('60.0'),
            'max_score': Decimal('80'),
            'evaluation': {'version': 'v2.1'}
        }
    ]

    # グルーピング実行
    sessions = group_tests_by_session(test_data)

    # 検証
    assert len(sessions) == 1, "3種目でも1セッションにグルーピング"

    session = sessions[0]
    assert session['athlete_id'] == 'athlete_002'
    assert session['is_complete'] == False, "7種目未満はis_complete=False"
    assert session['grand_total'] == 165.0, "3種目の合計"
    assert session['grand_max'] == 560, "最大スコアは常に560点"
    assert len(session['tests']) == 3, "3種目分のデータが含まれる"


def test_group_by_session_multiple_sessions():
    """
    What: 複数セッション（複数athlete_id、複数session_id）のグルーピングテスト
    Why: セッション一覧画面で複数セッションを表示
    Design Decision: athlete_id + session_id の組み合わせごとに1セッション

    CRITICAL: session_idが異なれば別セッション
    """
    from dashboard.session_dao import group_tests_by_session

    test_data = [
        # athlete_001, session_1
        {
            'athlete_id': 'athlete_001',
            'session_id': '20251031-1518-X',
            'test_type': 'single_leg_squat',
            'score': Decimal('56.4'),
            'max_score': Decimal('80'),
            'processed_at': '2025-10-31T15:19:50',
            'video_id': 'bucket/videos/test1.mp4',
            'evaluation': {'version': 'v2.1'}
        },
        # athlete_001, session_2（別日）
        {
            'athlete_id': 'athlete_001',
            'session_id': '20251101-1000-Z',
            'test_type': 'single_leg_squat',
            'score': Decimal('60.0'),
            'max_score': Decimal('80'),
            'processed_at': '2025-11-01T10:00:00',
            'video_id': 'bucket/videos/test2.mp4',
            'evaluation': {'version': 'v2.1'}
        },
        # athlete_002, session_1
        {
            'athlete_id': 'athlete_002',
            'session_id': '20251031-1600-Y',
            'test_type': 'single_leg_squat',
            'score': Decimal('50.0'),
            'max_score': Decimal('80'),
            'processed_at': '2025-10-31T16:00:00',
            'video_id': 'bucket/videos/test3.mp4',
            'evaluation': {'version': 'v2.1'}
        }
    ]

    # グルーピング実行
    sessions = group_tests_by_session(test_data)

    # 検証
    assert len(sessions) == 3, "3つの異なるセッション（athlete_id × session_id）"

    # session_id順にソート確認
    session_ids = [s['session_id'] for s in sessions]
    assert '20251031-1518-X' in session_ids
    assert '20251101-1000-Z' in session_ids
    assert '20251031-1600-Y' in session_ids


def test_group_by_session_mixed_rules_version():
    """
    What: 異なるrules_versionが混在するセッションのテスト
    Why: 比較不可能なセッションを検出
    Design Decision: rules_versionが混在する場合はwarningフラグを付与

    CRITICAL: v2.1とv1が混在 → 比較不可
    """
    from dashboard.session_dao import group_tests_by_session

    test_data = [
        {
            'athlete_id': 'athlete_001',
            'session_id': '20251031-1518-X',
            'test_type': 'single_leg_squat',
            'score': Decimal('56.4'),
            'max_score': Decimal('80'),
            'processed_at': '2025-10-31T15:19:50',
            'video_id': 'bucket/videos/test1.mp4',
            'evaluation': {'version': 'v2.1'}
        },
        {
            'athlete_id': 'athlete_001',
            'session_id': '20251031-1518-X',
            'test_type': 'skater_lunge',
            'score': Decimal('10.0'),
            'max_score': Decimal('12'),
            'processed_at': '2025-10-31T15:20:00',
            'video_id': 'bucket/videos/test2.mp4',
            'evaluation': {'version': 'v1'}  # 異なるバージョン
        }
    ]

    # グルーピング実行
    sessions = group_tests_by_session(test_data)

    # 検証
    assert len(sessions) == 1
    session = sessions[0]
    assert session['has_version_mismatch'] == True, "rules_version混在を検出"
    assert session['rules_version'] == 'mixed', "混在時はmixed表示"
