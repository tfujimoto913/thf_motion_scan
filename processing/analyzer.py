"""
Purpose: THF Motion Scanのメインエントリーポイント
Responsibility: 動画解析・スコアリング・結果保存の統合処理
Dependencies: mediapipe, opencv, config.json
Created: 2025-10-19 by Claude
Decision Log: ADR-002

CRITICAL: config.json閾値参照必須、ハードコード禁止
"""
import cv2
import mediapipe as mp
import numpy as np
import json
import argparse
from pathlib import Path
from datetime import datetime

class MotionAnalyzer:
    """
    What: THF Motion Scan 分析クラス
    Why: 動画から姿勢データを抽出し、テスト種別に応じたスコアリングを実行
    Design Decision: MediaPipe Poseを使用（ADR-002）

    CRITICAL: config.json依存、初期化時に設定読み込み必須
    """
    def __init__(self, config_path='config.json'):
        """
        What: MediaPipe初期化とconfig.json読み込み
        Why: 閾値外部化によるデータ整合性保証（ADR-002）
        Design Decision: config.json一元管理

        CRITICAL: config_path変更時は全テスト更新必須
        """
        # PHASE CORE LOGIC: config.json読み込み
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils
        
    def analyze_video(self, video_path, test_type):
        """
        What: 動画から姿勢ランドマークを抽出し評価
        Why: テスト種別に応じたスコアリング実行
        Design Decision: フレーム単位処理後に集計評価（ADR-002）

        CRITICAL: test_type不一致時はエラー、新規テスト追加時はconfig.json更新必須
        """
        print(f"🎥 動画を解析中: {video_path}")
        print(f"📋 テストタイプ: {test_type}")
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"動画を開けません: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0
        
        print(f"📊 動画情報: {frame_count}フレーム, {fps:.1f}fps, {duration:.1f}秒")
        
        # フレームごとのランドマークを保存
        all_landmarks = []
        frame_idx = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            
            # RGB変換
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(image)
            
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
                    'timestamp': frame_idx / fps,
                    'landmarks': landmarks
                })
            
            frame_idx += 1
            
            # 進捗表示（10%ごと）
            if frame_idx % max(1, frame_count // 10) == 0:
                progress = (frame_idx / frame_count) * 100
                print(f"⏳ 進捗: {progress:.0f}%")
        
        cap.release()
        print(f"✅ 解析完了: {len(all_landmarks)}フレーム検出")
        
        # テストタイプに応じてスコアリング
        score = self.calculate_score(all_landmarks, test_type)
        
        return {
            'video_path': str(video_path),
            'test_type': test_type,
            'frame_count': frame_count,
            'fps': fps,
            'duration': duration,
            'detected_frames': len(all_landmarks),
            'score': score,
            'landmarks': all_landmarks,
            'analyzed_at': datetime.now().isoformat()
        }
    
    def calculate_score(self, landmarks_data, test_type):
        """
        What: テスト種別に応じたスコアリングロジック振り分け
        Why: 各テストで評価基準が異なるため
        Design Decision: Strategy Pattern採用（ADR-002）

        CRITICAL: 新規テスト追加時は対応メソッド実装必須
        """
        if not landmarks_data:
            return {'total': 0, 'details': '姿勢が検出できませんでした'}
        
        if test_type == 'pelvic_stability':
            return self.score_pelvic_stability(landmarks_data)
        else:
            return {'total': 0, 'details': f'未実装のテスト: {test_type}'}
    
    def score_pelvic_stability(self, landmarks_data):
        """
        What: 骨盤安定性テストのスコアリング（左右hip Y座標差で評価）
        Why: 片脚立位時の骨盤水平性を定量評価
        Design Decision: config.json閾値参照でスコア判定（ADR-002）

        CRITICAL: 閾値変更はconfig.jsonのみ、ここでのハードコード禁止
        """
        # PHASE CORE LOGIC: 骨盤傾き計算（landmarks 23, 24）
        hip_angles = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            if len(landmarks) > 24:
                left_hip = landmarks[23]
                right_hip = landmarks[24]

                # 骨盤の傾き（Y座標の差）を計算
                hip_tilt = abs(left_hip['y'] - right_hip['y'])
                hip_angles.append(hip_tilt)

        if not hip_angles:
            return {'total': 0, 'details': '腰のランドマークが検出できませんでした'}

        # 統計値計算
        avg_tilt = np.mean(hip_angles)
        max_tilt = np.max(hip_angles)
        std_tilt = np.std(hip_angles)

        # CRITICAL: config.json閾値参照（ハードコード禁止）
        thresholds = self.config['thresholds']['pelvic_stability']
        tilt_excellent = thresholds['tilt_excellent']
        tilt_good = thresholds['tilt_good']
        tilt_improvement = thresholds['tilt_improvement']

        # スコアリング（0-3点）
        if avg_tilt < tilt_excellent:
            score = 3
            level = "優秀"
        elif avg_tilt < tilt_good:
            score = 2
            level = "良好"
        elif avg_tilt < tilt_improvement:
            score = 1
            level = "改善の余地あり"
        else:
            score = 0
            level = "要トレーニング"
        
        return {
            'total': score,
            'level': level,
            'details': {
                'avg_tilt': float(avg_tilt),
                'max_tilt': float(max_tilt),
                'std_tilt': float(std_tilt),
                'frames_analyzed': len(hip_angles)
            }
        }
    
    def save_results(self, results, output_dir='processing/output'):
        """
        What: 解析結果をJSONファイルに保存
        Why: 結果の永続化と後続処理での参照
        Design Decision: タイムスタンプ付きファイル名で重複回避（ADR-002）

        CRITICAL: 個人情報含む場合は匿名化処理後に保存
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{results['test_type']}_{timestamp}.json"
        filepath = output_path / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"💾 結果を保存: {filepath}")
        return filepath

def main():
    parser = argparse.ArgumentParser(description='THF Motion Scan - 動画解析ツール')
    parser.add_argument('--input', required=True, help='入力動画のパス')
    parser.add_argument('--test', required=True, help='テストタイプ (例: pelvic_stability)')
    parser.add_argument('--output', default='processing/output', help='出力ディレクトリ')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🏒 THF Motion Scan - 動画解析ツール")
    print("=" * 60)
    
    analyzer = MotionAnalyzer()
    
    try:
        results = analyzer.analyze_video(args.input, args.test)
        analyzer.save_results(results, args.output)
        
        print("\n" + "=" * 60)
        print("📊 解析結果サマリー")
        print("=" * 60)
        print(f"スコア: {results['score']['total']}/3")
        print(f"レベル: {results['score'].get('level', 'N/A')}")
        print(f"詳細: {json.dumps(results['score']['details'], indent=2, ensure_ascii=False)}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()