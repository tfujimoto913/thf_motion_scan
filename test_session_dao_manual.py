"""
簡易テストスクリプト（pytest不要）
"""
import sys
from pathlib import Path
from decimal import Decimal

# dashboardモジュールをパスに追加
sys.path.insert(0, str(Path(__file__).parent / 'dashboard'))

from session_dao import group_tests_by_session


def test_7tests_complete():
    """7種目完全データのグルーピングテスト"""
    print("Test: 7種目完全データのグルーピング...")

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

    sessions = group_tests_by_session(test_data)

    assert len(sessions) == 1, f"Expected 1 session, got {len(sessions)}"

    session = sessions[0]
    assert session['athlete_id'] == 'athlete_001'
    assert session['session_id'] == '20251031-1518-X'
    assert session['grand_total'] == 466.4, f"Expected 466.4, got {session['grand_total']}"
    assert session['grand_max'] == 560, f"Expected 560, got {session['grand_max']}"
    assert abs(session['percentage'] - 83.29) < 0.01, f"Expected ~83.29%, got {session['percentage']}"
    assert len(session['tests']) == 7, f"Expected 7 tests, got {len(session['tests'])}"
    assert session['rules_version'] == 'v2.1'

    print("✅ Pass: 7種目完全データのグルーピング")


def test_incomplete_tests():
    """種目不足時のグルーピングテスト"""
    print("Test: 種目不足時のグルーピング...")

    test_data = [
        {
            'athlete_id': 'athlete_002',
            'session_id': '20251031-1600-Y',
            'test_type': 'single_leg_squat',
            'score': Decimal('50.0'),
            'max_score': Decimal('80'),
            'processed_at': '2025-10-31T15:19:50',
            'video_id': 'bucket/videos/test1.mp4',
            'evaluation': {'version': 'v2.1'}
        },
        {
            'athlete_id': 'athlete_002',
            'session_id': '20251031-1600-Y',
            'test_type': 'skater_lunge',
            'score': Decimal('55.0'),
            'max_score': Decimal('80'),
            'processed_at': '2025-10-31T15:20:00',
            'video_id': 'bucket/videos/test2.mp4',
            'evaluation': {'version': 'v2.1'}
        },
        {
            'athlete_id': 'athlete_002',
            'session_id': '20251031-1600-Y',
            'test_type': 'stride_mimic',
            'score': Decimal('60.0'),
            'max_score': Decimal('80'),
            'processed_at': '2025-10-31T15:21:00',
            'video_id': 'bucket/videos/test3.mp4',
            'evaluation': {'version': 'v2.1'}
        }
    ]

    sessions = group_tests_by_session(test_data)

    assert len(sessions) == 1
    session = sessions[0]
    assert session['is_complete'] == False, f"Expected is_complete=False, got {session['is_complete']}"
    assert session['grand_total'] == 165.0
    assert len(session['tests']) == 3

    print("✅ Pass: 種目不足時のグルーピング")


def test_multiple_sessions():
    """複数セッションのグルーピングテスト"""
    print("Test: 複数セッションのグルーピング...")

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
            'session_id': '20251101-1000-Z',
            'test_type': 'single_leg_squat',
            'score': Decimal('60.0'),
            'max_score': Decimal('80'),
            'processed_at': '2025-11-01T10:00:00',
            'video_id': 'bucket/videos/test2.mp4',
            'evaluation': {'version': 'v2.1'}
        },
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

    sessions = group_tests_by_session(test_data)

    assert len(sessions) == 3, f"Expected 3 sessions, got {len(sessions)}"

    session_ids = [s['session_id'] for s in sessions]
    assert '20251031-1518-X' in session_ids
    assert '20251101-1000-Z' in session_ids
    assert '20251031-1600-Y' in session_ids

    print("✅ Pass: 複数セッションのグルーピング")


def test_mixed_rules_version():
    """異なるrules_version混在テスト"""
    print("Test: 異なるrules_version混在...")

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

    sessions = group_tests_by_session(test_data)

    assert len(sessions) == 1
    session = sessions[0]
    assert session['has_version_mismatch'] == True, f"Expected has_version_mismatch=True"
    assert session['rules_version'] == 'mixed', f"Expected 'mixed', got {session['rules_version']}"

    print("✅ Pass: 異なるrules_version混在")


if __name__ == '__main__':
    try:
        test_7tests_complete()
        test_incomplete_tests()
        test_multiple_sessions()
        test_mixed_rules_version()

        print("\n🎉 全テストPass!")
    except AssertionError as e:
        print(f"\n❌ Test Failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
