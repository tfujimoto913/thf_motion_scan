"""
Purpose: セッション単位のデータ集約DAO
Responsibility: DynamoDBから取得した7種目データを1セッションにグルーピング
Dependencies: typing, decimal
Created: 2025-11-01 by Claude Code
Decision Log: Phase 5 - Stage 1 (ADR-023準拠)

CRITICAL:
  - 1セッション = athlete_id + session_id の組み合わせ
  - 総合スコア = 7種目×80点 = 560点満点
  - rules_version混在時は比較不可フラグを付与
"""
from typing import List, Dict, Any
from decimal import Decimal
from collections import defaultdict


def group_tests_by_session(test_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    What: 7種目のテスト結果を athlete_id + session_id でグルーピング
    Why: DynamoDBは1種目=1レコード構造、ダッシュボードは1セッション単位で表示
    Design Decision: Pandas不使用、純粋なPython辞書で集約（ADR-023）

    Args:
        test_results: DynamoDBから取得したテスト結果のリスト
                      各要素は {'athlete_id', 'session_id', 'test_type', 'score', ...}

    Returns:
        List[Dict]: セッションごとに集約されたデータ
        [
            {
                'athlete_id': 'athlete_001',
                'session_id': '20251031-1518-X',
                'grand_total': 466.4,  # 7種目の合計スコア
                'grand_max': 560,      # 最大スコア（7種目×80点）
                'percentage': 83.29,   # 達成率
                'is_complete': True,   # 7種目完了か
                'tests': [...],        # 7種目分のデータ配列
                'rules_version': 'v2.1',  # 全種目で同一の場合
                'has_version_mismatch': False,  # rules_version混在フラグ
                'processed_at': '2025-10-31T15:25:00'  # 最新のprocessed_at
            },
            ...
        ]

    CRITICAL:
      - 7種目未満でも1セッションとしてカウント（is_complete=False）
      - rules_versionが混在する場合は 'mixed' を設定
    """
    # athlete_id + session_id でグルーピング
    grouped = defaultdict(list)

    for test in test_results:
        # キー: athlete_id + session_id の組み合わせ
        key = (test.get('athlete_id', 'Unknown'), test.get('session_id', 'Unknown'))
        grouped[key].append(test)

    # セッションごとに集約
    sessions = []

    for (athlete_id, session_id), tests in grouped.items():
        # 総合スコア計算（Decimal → float変換）
        total_score = sum(float(t.get('score', 0)) for t in tests)
        max_score = 560  # 7種目×80点

        # rules_version チェック
        versions = set(
            t.get('evaluation', {}).get('version', 'unknown')
            for t in tests
        )

        if len(versions) == 1:
            rules_version = versions.pop()
            has_version_mismatch = False
        else:
            rules_version = 'mixed'
            has_version_mismatch = True

        # 最新のprocessed_atを取得
        processed_at_list = [t.get('processed_at', '') for t in tests]
        latest_processed_at = max(processed_at_list) if processed_at_list else ''

        # セッションデータ構築
        session = {
            'athlete_id': athlete_id,
            'session_id': session_id,
            'grand_total': total_score,
            'grand_max': max_score,
            'percentage': (total_score / max_score * 100) if max_score > 0 else 0,
            'is_complete': len(tests) == 7,  # 7種目完了か
            'tests': tests,
            'rules_version': rules_version,
            'has_version_mismatch': has_version_mismatch,
            'processed_at': latest_processed_at
        }

        sessions.append(session)

    # processed_at降順でソート（最新セッションが先頭）
    sessions.sort(key=lambda s: s['processed_at'], reverse=True)

    return sessions


def get_session_by_id(
    test_results: List[Dict[str, Any]],
    athlete_id: str,
    session_id: str
) -> Dict[str, Any]:
    """
    What: 特定のセッションを取得
    Why: セッション詳細画面で使用
    Design Decision: group_tests_by_sessionを再利用してフィルタ

    Args:
        test_results: DynamoDBから取得したテスト結果のリスト
        athlete_id: 選手ID
        session_id: セッションID

    Returns:
        Dict: セッションデータ（見つからない場合はNone）

    CRITICAL: 存在しない場合はNoneを返す
    """
    sessions = group_tests_by_session(test_results)

    for session in sessions:
        if session['athlete_id'] == athlete_id and session['session_id'] == session_id:
            return session

    return None


def get_latest_sessions(
    test_results: List[Dict[str, Any]],
    limit: int = 12
) -> List[Dict[str, Any]]:
    """
    What: 最新のセッション一覧を取得
    Why: セッション一覧画面で最大12件表示
    Design Decision: processed_at降順ソート済みのため上位N件取得

    Args:
        test_results: DynamoDBから取得したテスト結果のリスト
        limit: 最大取得件数（デフォルト12）

    Returns:
        List[Dict]: 最新N件のセッションデータ

    CRITICAL: 既にprocessed_at降順でソート済み
    """
    sessions = group_tests_by_session(test_results)
    return sessions[:limit]


def get_previous_sessions(
    test_results: List[Dict[str, Any]],
    athlete_id: str,
    current_session_id: str,
    limit: int = 12
) -> List[Dict[str, Any]]:
    """
    What: 同一athlete_idの過去セッション一覧を取得
    Why: セッション比較機能（Stage 4）で比較対象セッションを選択するため
    Design Decision: 現在セッションを除外し、processed_at降順でソート（ADR-023 Stage 4）

    Args:
        test_results: DynamoDBから取得したテスト結果のリスト
        athlete_id: 選手ID
        current_session_id: 現在のセッションID（比較元、除外対象）
        limit: 最大取得件数（デフォルト12）

    Returns:
        List[Dict]: 過去N件のセッションデータ（現在セッション除外済み）
        [
            {
                'athlete_id': 'athlete_001',
                'session_id': '20251030-1200-X',
                'grand_total': 450.0,
                'percentage': 80.4,
                'rules_version': 'v2.1',
                ...
            },
            ...
        ]

    CRITICAL:
      - 現在セッション（current_session_id）は除外
      - 同一athlete_idのみフィルタ
      - processed_at降順でソート済み
    """
    sessions = group_tests_by_session(test_results)

    # 同一athlete_idかつ現在セッション以外をフィルタ
    previous_sessions = [
        s for s in sessions
        if s['athlete_id'] == athlete_id and s['session_id'] != current_session_id
    ]

    # 上位N件を返す（既にprocessed_at降順でソート済み）
    return previous_sessions[:limit]
