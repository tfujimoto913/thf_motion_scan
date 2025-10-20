"""
Purpose: MediaPipe Poseを使用した姿勢ランドマーク抽出
Responsibility: 動画から33キーポイントのランドマークデータを抽出、CLI経由でJSON出力
Dependencies: cv2, mediapipe, argparse, json, datetime
Created: 2025-10-18 by Claude
Decision Log: ADR-005

CRITICAL: MediaPipe Pose初期化・解放処理、RGB変換必須
"""
import cv2
import mediapipe as mp
from typing import List, Dict, Optional
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime


class PoseExtractor:
    """
    What: 動画から姿勢ランドマークを抽出するクラス
    Why: THF評価の入力データ生成
    Design Decision: MediaPipe Pose使用、model_complexity=2でバランス重視（ADR-005）

    CRITICAL: MediaPipe Poseリソース管理必須（__del__で解放）
    """

    def __init__(self,
                 static_image_mode: bool = False,
                 model_complexity: int = 2,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5):
        """
        What: MediaPipe Pose初期化
        Why: ランドマーク抽出エンジン準備
        Design Decision: model_complexity=2で精度と速度のバランス重視（ADR-005）

        Args:
            static_image_mode: 静止画モード（動画の場合False推奨）
            model_complexity: モデルの複雑さ (0=Lite, 1=Full, 2=Heavy)
            min_detection_confidence: 検出の最小信頼度（0.5推奨）
            min_tracking_confidence: トラッキングの最小信頼度（0.5推奨）

        CRITICAL: static_image_mode=Falseで動画最適化、Trueは静止画用
        """
        # CRITICAL: MediaPipe Pose初期化（削除厳禁）
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=static_image_mode,
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )

    def extract_landmarks(self, video_path: str) -> Dict:
        """
        What: 動画からフレームごとのランドマークを抽出
        Why: THF評価器への入力データ生成
        Design Decision: MediaPipe Pose使用、33キーポイント抽出（ADR-005）

        Args:
            video_path: 動画ファイルのパス

        Returns:
            Dict: {
                'landmarks': List[Dict] - フレームごとのランドマークデータ,
                'fps': float - 動画のFPS,
                'frame_count': int - 総フレーム数,
                'duration': float - 動画の長さ（秒）,
                'detected_frames': int - ランドマーク検出成功フレーム数
            }

        Raises:
            ValueError: 動画ファイルが開けない場合

        CRITICAL: RGB変換必須（MediaPipeはRGB入力前提）、cap.release()必須
        """
        # PHASE CORE LOGIC: 動画読み込みと基本情報取得
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"動画を開けません: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0

        all_landmarks = []
        frame_idx = 0

        # PHASE CORE LOGIC: フレームごとのランドマーク抽出
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # CRITICAL: RGB変換（MediaPipeはRGB入力前提、BGRではNG）
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(image)

            # CRITICAL: ランドマーク検出成功時のみデータ保存
            if results.pose_landmarks:
                landmarks = []
                for lm in results.pose_landmarks.landmark:
                    landmarks.append({
                        'x': lm.x,
                        'y': lm.y,
                        'z': lm.z,
                        'visibility': lm.visibility
                    })
                all_landmarks.append({
                    'frame': frame_idx,
                    'timestamp': frame_idx / fps if fps > 0 else 0,
                    'landmarks': landmarks
                })

            frame_idx += 1

        # CRITICAL: リソース解放必須
        cap.release()

        return {
            'landmarks': all_landmarks,
            'fps': fps,
            'frame_count': frame_count,
            'duration': duration,
            'detected_frames': len(all_landmarks)
        }

    def save_to_json(
        self,
        data: Dict,
        output_path: str,
        video_path: Optional[str] = None
    ) -> None:
        """
        What: ランドマークデータをJSON形式で保存（メタデータ拡張版）
        Why: テストフィクスチャ生成、デバッグ容易化
        Design Decision: 提案B（メタデータ拡張版）採用（ADR-005）

        Args:
            data: extract_landmarks()の戻り値
            output_path: 出力JSONファイルパス
            video_path: 動画ファイルパス（メタデータ用）

        Raises:
            IOError: ファイル書き込み失敗時

        CRITICAL: 既存コード互換性維持（data['landmarks']でアクセス可能）
        """
        # PHASE CORE LOGIC: メタデータ生成
        metadata = {
            'video_path': str(video_path) if video_path else 'unknown',
            'total_frames': data['frame_count'],
            'fps': data['fps'],
            'duration_sec': data['duration'],
            'detected_frames': data['detected_frames'],
            'detection_rate': data['detected_frames'] / data['frame_count'] if data['frame_count'] > 0 else 0.0,
            'created_at': datetime.utcnow().isoformat() + 'Z',
            'mediapipe_version': mp.__version__,
            'pose_extractor_version': '1.0.0'
        }

        # CRITICAL: 既存コード互換性維持（data['landmarks']をそのまま保存）
        output_data = {
            'metadata': metadata,
            'landmarks': data['landmarks']
        }

        # PHASE CORE LOGIC: JSON書き込み
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

    def __del__(self):
        """
        What: MediaPipe Poseリソース解放
        Why: メモリリーク防止
        Design Decision: __del__でリソース解放（ADR-005）

        CRITICAL: pose.close()必須（MediaPipeリソース解放）
        """
        # CRITICAL: MediaPipe Poseリソース解放（メモリリーク防止）
        if hasattr(self, 'pose'):
            self.pose.close()


def main():
    """
    What: CLIエントリーポイント（動画→JSON変換）
    Why: テストフィクスチャ生成、デバッグ容易化
    Design Decision: argparse使用、提案B（メタデータ拡張版）出力（ADR-005）

    Usage:
        python -m processing.pose_extractor \\
          --input tests/test_videos/sample_squat.mp4 \\
          --output tests/fixtures/sample_landmarks.json \\
          --verbose

    CRITICAL: --format 'dict'で既存互換、'json'でメタデータ拡張版
    """
    # PHASE CORE LOGIC: argparse設定
    parser = argparse.ArgumentParser(
        description='MediaPipe Poseを使用して動画からランドマークを抽出し、JSON形式で保存',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
使用例:
  # メタデータ拡張版JSON出力（推奨）
  python -m processing.pose_extractor \\
    --input tests/test_videos/sample_squat.mp4 \\
    --output tests/fixtures/sample_landmarks.json \\
    --verbose

  # 辞書形式出力（既存互換）
  python -m processing.pose_extractor \\
    --input video.mp4 \\
    --output output.json \\
    --format dict
        '''
    )

    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='入力動画ファイルパス（.mp4, .avi, .mov）'
    )

    parser.add_argument(
        '--output',
        type=str,
        required=True,
        help='出力JSONファイルパス'
    )

    parser.add_argument(
        '--format',
        type=str,
        choices=['dict', 'json'],
        default='json',
        help='出力形式（dict: 既存互換, json: メタデータ拡張版、デフォルト: json）'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='詳細ログ出力'
    )

    args = parser.parse_args()

    # PHASE CORE LOGIC: 動画ファイル存在確認
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ エラー: 動画ファイルが見つかりません: {args.input}", file=sys.stderr)
        sys.exit(1)

    # PHASE CORE LOGIC: ランドマーク抽出
    if args.verbose:
        print(f"🎥 動画を解析中: {args.input}")

    try:
        extractor = PoseExtractor()
        data = extractor.extract_landmarks(str(input_path))

        if args.verbose:
            print(f"📊 動画情報:")
            print(f"  - 総フレーム数: {data['frame_count']}")
            print(f"  - FPS: {data['fps']:.1f}")
            print(f"  - 長さ: {data['duration']:.1f}秒")
            print(f"  - 検出フレーム数: {data['detected_frames']}")
            print(f"  - 検出率: {data['detected_frames']/data['frame_count']*100:.1f}%")

    except Exception as e:
        print(f"❌ エラー: ランドマーク抽出失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # PHASE CORE LOGIC: JSON出力
    if args.verbose:
        print(f"💾 JSON保存中: {args.output}")

    try:
        if args.format == 'json':
            # メタデータ拡張版（提案B）
            extractor.save_to_json(data, args.output, args.input)
        else:
            # 既存互換版（提案A）
            output_file = Path(args.output)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        if args.verbose:
            print(f"✅ 完了: {args.output}")

    except Exception as e:
        print(f"❌ エラー: JSON保存失敗: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    """
    What: CLIモード実行
    Why: python -m processing.pose_extractor で動画→JSON変換実行
    Design Decision: main()関数呼び出し（ADR-005）

    CRITICAL: モジュールとしてインポート時は実行されない
    """
    main()
