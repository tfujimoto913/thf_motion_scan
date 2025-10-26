"""
Purpose: デモモード用サンプルデータ
Responsibility: UIレビュー・フィードバック収集用の仮データ提供
Dependencies: json, pathlib
Created: 2025-10-26 by Claude
Decision Log: ADR-014（Phase 5: Dashboard実装）

CRITICAL: 本番環境では使用禁止（デモモードOFF時は無視）
"""
import json
from pathlib import Path
from typing import List, Dict, Any


def get_demo_results() -> List[Dict[str, Any]]:
    """
    What: デモモード用サンプル評価結果取得
    Why: AWS環境なしでUI確認を可能にする
    Design Decision: 評価器ベースで生成されたJSONから読み込み（ADR-014）

    Returns:
        List[Dict]: 評価結果リスト（DynamoDB Item形式）

    CRITICAL: 実際の評価器で生成されたデータを使用
    """
    # demo_results.json から読み込み
    demo_file = Path(__file__).parent / "demo_results.json"

    if not demo_file.exists():
        print(f"⚠️  デモデータファイルが見つかりません: {demo_file}")
        print("ℹ️  以下のコマンドで生成してください:")
        print("   python scripts/generate_demo_data.py")
        return []

    try:
        with open(demo_file, 'r', encoding='utf-8') as f:
            demo_results = json.load(f)
        return demo_results
    except Exception as e:
        print(f"❌ デモデータ読み込みエラー: {e}")
        return []


# 以下は旧版（手動作成）- バックアップとして保持
def get_demo_results_legacy() -> List[Dict[str, Any]]:
    """
    What: デモモード用サンプル評価結果取得（旧版・手動作成）
    Why: demo_results.json がない場合のフォールバック
    Design Decision: 手動で作成したサンプルデータ

    CRITICAL: 廃止予定（scripts/generate_demo_data.py使用を推奨）
    """
    from datetime import datetime, timedelta

    # 直近1週間のタイムスタンプ生成
    now = datetime.now()
    timestamps = [
        (now - timedelta(days=6)).isoformat(),
        (now - timedelta(days=4)).isoformat(),
        (now - timedelta(days=2)).isoformat(),
        (now - timedelta(days=1)).isoformat(),
        (now - timedelta(hours=3)).isoformat(),
    ]

    # PHASE CORE LOGIC: DynamoDB Item形式のサンプルデータ（手動作成版）
    # UPDATED: クライアントID形式を FirstLast-yymmdd に変更（ADR-015予定）
    demo_results = [
        {
            'video_id': 'thf-motion-scan-videos-demo/videos/single_leg_squat/TaroYamada-100315.mp4',
            'processed_at': timestamps[0],
            'test_type': 'single_leg_squat',
            'score': 2.8,
            'video_info': {
                'total_frames': 450,
                'fps': 30.0,
                'duration_sec': 15.0,
                'detected_frames': 438,
                'detection_rate': 0.973
            },
            'health_check': {
                'is_valid': True,
                'warnings': [],
                'detection_rate': 0.973,
                'low_confidence_frames': 12
            },
            'evaluation': {
                'pelvic_stability': {
                    'score': 3,
                    'value': 0.025,
                    'unit': 'meters'
                },
                'knee_flexion': {
                    'score': 2,
                    'value': 82.5,
                    'unit': 'degrees'
                }
            },
            'result_s3_key': 'results/2025/10/20/demo_athlete_001_20251020_100000.json',
            'ttl': int((now + timedelta(days=90)).timestamp())
        },
        {
            'video_id': 'thf-motion-scan-videos-demo/videos/skater_lunge/YukiSato-110822.mp4',
            'processed_at': timestamps[1],
            'test_type': 'skater_lunge',
            'score': 1.5,
            'video_info': {
                'total_frames': 360,
                'fps': 30.0,
                'duration_sec': 12.0,
                'detected_frames': 324,
                'detection_rate': 0.900
            },
            'health_check': {
                'is_valid': True,
                'warnings': ['低品質フレーム検出: 36フレーム'],
                'detection_rate': 0.900,
                'low_confidence_frames': 36
            },
            'evaluation': {
                'lateral_stability': {
                    'score': 2,
                    'value': 0.055,
                    'unit': 'meters'
                },
                'depth_control': {
                    'score': 1,
                    'value': 65.2,
                    'unit': 'degrees'
                }
            },
            'result_s3_key': 'results/2025/10/22/demo_athlete_002_20251022_140000.json',
            'ttl': int((now + timedelta(days=90)).timestamp())
        },
        {
            'video_id': 'thf-motion-scan-videos-demo/videos/upper_body_swing/KenjiTanaka-091201.mp4',
            'processed_at': timestamps[2],
            'test_type': 'upper_body_swing',
            'score': 2.3,
            'video_info': {
                'total_frames': 300,
                'fps': 30.0,
                'duration_sec': 10.0,
                'detected_frames': 285,
                'detection_rate': 0.950
            },
            'health_check': {
                'is_valid': True,
                'warnings': [],
                'detection_rate': 0.950,
                'low_confidence_frames': 15
            },
            'evaluation': {
                'shoulder_rotation': {
                    'score': 2,
                    'value': 88.3,
                    'unit': 'degrees'
                },
                'core_stability': {
                    'score': 3,
                    'value': 0.018,
                    'unit': 'meters'
                }
            },
            'result_s3_key': 'results/2025/10/24/demo_athlete_003_20251024_093000.json',
            'ttl': int((now + timedelta(days=90)).timestamp())
        },
        {
            'video_id': 'thf-motion-scan-videos-demo/videos/cross_step/AikoWatanabe-120510.mp4',
            'processed_at': timestamps[3],
            'test_type': 'cross_step',
            'score': 0.5,
            'video_info': {
                'total_frames': 240,
                'fps': 30.0,
                'duration_sec': 8.0,
                'detected_frames': 144,
                'detection_rate': 0.600
            },
            'health_check': {
                'is_valid': False,
                'warnings': ['低検出率: 60%', '推奨: 再撮影'],
                'detection_rate': 0.600,
                'low_confidence_frames': 96
            },
            'evaluation': {
                'step_width': {
                    'score': 1,
                    'value': 0.92,
                    'unit': 'ratio'
                },
                'balance': {
                    'score': 0,
                    'value': 0.145,
                    'unit': 'meters'
                }
            },
            'result_s3_key': 'results/2025/10/25/demo_athlete_004_20251025_110000.json',
            'ttl': int((now + timedelta(days=90)).timestamp())
        },
        {
            'video_id': 'thf-motion-scan-videos-demo/videos/jump_landing/RyoSuzuki-100730.mp4',
            'processed_at': timestamps[4],
            'test_type': 'jump_landing',
            'score': 2.0,
            'video_info': {
                'total_frames': 180,
                'fps': 30.0,
                'duration_sec': 6.0,
                'detected_frames': 171,
                'detection_rate': 0.950
            },
            'health_check': {
                'is_valid': True,
                'warnings': [],
                'detection_rate': 0.950,
                'low_confidence_frames': 9
            },
            'evaluation': {
                'landing_stability': {
                    'score': 2,
                    'value': 0.048,
                    'unit': 'meters'
                },
                'knee_alignment': {
                    'score': 2,
                    'value': 12.5,
                    'unit': 'degrees'
                }
            },
            'result_s3_key': 'results/2025/10/26/demo_athlete_005_20251026_170000.json',
            'ttl': int((now + timedelta(days=90)).timestamp())
        }
    ]

    return demo_results  # レガシー版
