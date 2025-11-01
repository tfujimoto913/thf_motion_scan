"""
Purpose: 動画アップロード前の種目検証（簡易チェック）
Responsibility: MediaPipeで最初の30フレームを解析し、種目の特徴的な動きを検出
Dependencies: mediapipe, opencv-python, numpy
Created: 2025-10-31 by Claude
Decision Log: Phase 5 - UX改善（誤アップロード防止）

CRITICAL: 完全一致は求めない。明らかな間違い（静止画、全く違う動き）のみ検出
"""
import cv2
import mediapipe as mp
import numpy as np
from typing import Tuple, List, Optional


class VideoValidator:
    """
    What: 動画の種目簡易バリデーター
    Why: S3アップロード前に明らかな間違いを検出してユーザーに通知
    Design Decision: MediaPipe Poseで最初の30フレームのみ解析（高速化）

    CRITICAL:
    - 処理時間は10-30秒程度
    - 精度は80%程度（完全一致は不可能）
    - False Positiveを避けるため、閾値は緩め
    """

    def __init__(self):
        self.pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

    def validate(self, video_path: str, expected_test_type: str) -> Tuple[bool, str, dict]:
        """
        What: 動画の種目を簡易チェック
        Why: 誤アップロード防止

        Args:
            video_path: 動画ファイルパス
            expected_test_type: 期待される種目名

        Returns:
            (is_valid, message, details):
                - is_valid: 種目が一致するか（またはチェック不可）
                - message: ユーザーへのメッセージ
                - details: 詳細情報（デバッグ用）

        CRITICAL: チェック失敗時もアップロードは可能（警告のみ）
        """
        try:
            # ランドマーク取得
            landmarks_list = self._extract_landmarks(video_path, max_frames=30)

            if len(landmarks_list) < 10:
                return (True, "⚠️ ランドマーク検出が少ないため、種目チェックをスキップしました",
                       {"landmarks_count": len(landmarks_list)})

            # 種目ごとのチェック
            checker_map = {
                'single_leg_squat': self._check_single_leg_squat,
                'skater_lunge': self._check_skater_lunge,
                'stride_mimic': self._check_stride_mimic,
                'jump_landing': self._check_jump_landing,
                'upper_body_swing': self._check_upper_body_swing,
                'push_pull': self._check_push_pull,
                'cross_step': self._check_cross_step
            }

            if expected_test_type not in checker_map:
                return (True, "⚠️ この種目のバリデーションは未実装です", {})

            checker = checker_map[expected_test_type]
            is_valid, reason, details = checker(landmarks_list)

            if is_valid:
                return (True, f"✅ {expected_test_type} の特徴的な動きが検出されました", details)
            else:
                return (False, f"⚠️ {reason}\n\n続行する場合は「無視してアップロード」を選択してください", details)

        except Exception as e:
            # エラー時はチェックスキップ（アップロードは許可）
            return (True, f"⚠️ 種目チェック中にエラーが発生しました: {str(e)}", {})

        finally:
            self.pose.close()

    def _extract_landmarks(self, video_path: str, max_frames: int = 30) -> List[dict]:
        """
        What: 動画からランドマークを抽出（空白時間スキップ対応）
        Why: 撮影開始時の空白時間を考慮し、ランドマークが検出されたフレームのみカウント

        Args:
            max_frames: 収集するランドマーク数（デフォルト30）

        Returns:
            List[dict]: ランドマーク辞書のリスト（キー: 'LEFT_ANKLE', 'RIGHT_ANKLE'等）

        CRITICAL:
        - ランドマークが検出されたフレームのみカウント
        - 最大300フレーム（約10秒）まで探索して無限ループ防止
        """
        cap = cv2.VideoCapture(video_path)
        landmarks_list = []
        total_frames_read = 0
        max_attempts = 300  # 無限ループ防止（約10秒分）

        while len(landmarks_list) < max_frames and total_frames_read < max_attempts:
            ret, frame = cap.read()
            if not ret:
                break

            total_frames_read += 1

            # MediaPipe処理
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.pose.process(frame_rgb)

            if results.pose_landmarks:
                # ランドマークを辞書形式に変換
                lm_dict = {}
                for idx, lm in enumerate(results.pose_landmarks.landmark):
                    name = mp.solutions.pose.PoseLandmark(idx).name
                    lm_dict[name] = {'x': lm.x, 'y': lm.y, 'z': lm.z, 'visibility': lm.visibility}
                landmarks_list.append(lm_dict)

        cap.release()
        return landmarks_list

    def _check_single_leg_squat(self, landmarks_list: List[dict]) -> Tuple[bool, str, dict]:
        """
        What: 片脚スタンススクワットの特徴チェック
        Why: 片足が浮いている（左右足首のy座標差が大きい）

        CRITICAL: 閾値は緩め（0.15 = 画面高さの15%）
        """
        ankle_diffs = []

        for lm in landmarks_list:
            if 'LEFT_ANKLE' in lm and 'RIGHT_ANKLE' in lm:
                diff = abs(lm['LEFT_ANKLE']['y'] - lm['RIGHT_ANKLE']['y'])
                ankle_diffs.append(diff)

        if not ankle_diffs:
            return (True, "足首検出不可", {})

        max_diff = max(ankle_diffs)
        avg_diff = np.mean(ankle_diffs)

        # 片脚立ちの判定：最大差が15%以上、または平均差が8%以上
        is_single_leg = max_diff > 0.15 or avg_diff > 0.08

        details = {
            'max_ankle_diff': float(max_diff),
            'avg_ankle_diff': float(avg_diff),
            'threshold': 0.15
        }

        if is_single_leg:
            return (True, "", details)
        else:
            return (False, "片脚立ちの動作が検出されませんでした。両足が地面についている可能性があります", details)

    def _check_skater_lunge(self, landmarks_list: List[dict]) -> Tuple[bool, str, dict]:
        """
        What: スケーターランジの特徴チェック
        Why: 左右への大きな重心移動
        """
        hip_x_positions = []

        for lm in landmarks_list:
            if 'LEFT_HIP' in lm and 'RIGHT_HIP' in lm:
                center_x = (lm['LEFT_HIP']['x'] + lm['RIGHT_HIP']['x']) / 2
                hip_x_positions.append(center_x)

        if len(hip_x_positions) < 10:
            return (True, "腰位置検出不可", {})

        x_range = max(hip_x_positions) - min(hip_x_positions)

        # 左右移動の判定：画面幅の20%以上
        is_lateral_movement = x_range > 0.20

        details = {
            'lateral_range': float(x_range),
            'threshold': 0.20
        }

        if is_lateral_movement:
            return (True, "", details)
        else:
            return (False, "左右への大きな動きが検出されませんでした", details)

    def _check_stride_mimic(self, landmarks_list: List[dict]) -> Tuple[bool, str, dict]:
        """
        What: スケートストライド模倣の特徴チェック
        Why: 前後への足の移動
        """
        ankle_z_positions = []

        for lm in landmarks_list:
            if 'LEFT_ANKLE' in lm and 'RIGHT_ANKLE' in lm:
                # z座標（奥行き）の差で前後動を検出
                z_diff = abs(lm['LEFT_ANKLE']['z'] - lm['RIGHT_ANKLE']['z'])
                ankle_z_positions.append(z_diff)

        if len(ankle_z_positions) < 10:
            return (True, "足首検出不可", {})

        max_z_diff = max(ankle_z_positions)

        # 前後動の判定：z座標差が0.3以上
        is_forward_backward = max_z_diff > 0.3

        details = {
            'max_z_diff': float(max_z_diff),
            'threshold': 0.3
        }

        if is_forward_backward:
            return (True, "", details)
        else:
            return (False, "前後への大きな動きが検出されませんでした", details)

    def _check_jump_landing(self, landmarks_list: List[dict]) -> Tuple[bool, str, dict]:
        """
        What: ミニジャンプ＆着地の特徴チェック
        Why: 上下動が大きい
        """
        hip_y_positions = []

        for lm in landmarks_list:
            if 'LEFT_HIP' in lm and 'RIGHT_HIP' in lm:
                center_y = (lm['LEFT_HIP']['y'] + lm['RIGHT_HIP']['y']) / 2
                hip_y_positions.append(center_y)

        if len(hip_y_positions) < 10:
            return (True, "腰位置検出不可", {})

        y_range = max(hip_y_positions) - min(hip_y_positions)

        # ジャンプの判定：画面高さの15%以上の上下動
        is_jump = y_range > 0.15

        details = {
            'vertical_range': float(y_range),
            'threshold': 0.15
        }

        if is_jump:
            return (True, "", details)
        else:
            return (False, "ジャンプ動作（上下動）が検出されませんでした", details)

    def _check_upper_body_swing(self, landmarks_list: List[dict]) -> Tuple[bool, str, dict]:
        """
        What: 上体スイングの特徴チェック
        Why: 肩ラインの回転角度
        """
        shoulder_angles = []

        for lm in landmarks_list:
            if 'LEFT_SHOULDER' in lm and 'RIGHT_SHOULDER' in lm:
                dx = lm['RIGHT_SHOULDER']['x'] - lm['LEFT_SHOULDER']['x']
                dy = lm['RIGHT_SHOULDER']['y'] - lm['LEFT_SHOULDER']['y']
                angle = np.arctan2(dy, dx) * 180 / np.pi
                shoulder_angles.append(angle)

        if len(shoulder_angles) < 10:
            return (True, "肩位置検出不可", {})

        angle_range = max(shoulder_angles) - min(shoulder_angles)

        # 回転の判定：15度以上の角度変化
        is_rotation = angle_range > 15

        details = {
            'angle_range': float(angle_range),
            'threshold': 15
        }

        if is_rotation:
            return (True, "", details)
        else:
            return (False, "肩の回転動作が検出されませんでした", details)

    def _check_push_pull(self, landmarks_list: List[dict]) -> Tuple[bool, str, dict]:
        """
        What: プッシュプル動作の特徴チェック
        Why: 手首の前後動（z座標）
        """
        wrist_z_positions = []

        for lm in landmarks_list:
            if 'LEFT_WRIST' in lm and 'RIGHT_WRIST' in lm:
                avg_z = (lm['LEFT_WRIST']['z'] + lm['RIGHT_WRIST']['z']) / 2
                wrist_z_positions.append(avg_z)

        if len(wrist_z_positions) < 10:
            return (True, "手首検出不可", {})

        z_range = max(wrist_z_positions) - min(wrist_z_positions)

        # プッシュプルの判定：z座標で0.4以上の変化
        is_push_pull = z_range > 0.4

        details = {
            'z_range': float(z_range),
            'threshold': 0.4
        }

        if is_push_pull:
            return (True, "", details)
        else:
            return (False, "プッシュ・プル動作（前後動）が検出されませんでした", details)

    def _check_cross_step(self, landmarks_list: List[dict]) -> Tuple[bool, str, dict]:
        """
        What: クロスステップ模倣の特徴チェック
        Why: 足のクロス（x座標の逆転）
        """
        cross_count = 0

        for lm in landmarks_list:
            if 'LEFT_ANKLE' in lm and 'RIGHT_ANKLE' in lm:
                # 通常は LEFT_ANKLE.x < RIGHT_ANKLE.x
                # クロス時は逆転
                if lm['LEFT_ANKLE']['x'] > lm['RIGHT_ANKLE']['x']:
                    cross_count += 1

        if len(landmarks_list) < 10:
            return (True, "足首検出不可", {})

        cross_ratio = cross_count / len(landmarks_list)

        # クロスの判定：フレームの20%以上でクロス状態
        is_cross = cross_ratio > 0.20

        details = {
            'cross_ratio': float(cross_ratio),
            'threshold': 0.20
        }

        if is_cross:
            return (True, "", details)
        else:
            return (False, "クロスステップ動作が検出されませんでした", details)
