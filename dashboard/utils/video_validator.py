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

    def _calculate_angle(self, point1: dict, point2: dict, point3: dict) -> float:
        """
        What: 3点から角度を計算
        Why: 膝や肘の屈曲角度を計算するため

        Args:
            point1, point2, point3: ランドマーク座標（{'x': float, 'y': float}）
            point2が頂点（例: 膝の角度なら、point1=腰、point2=膝、point3=足首）

        Returns:
            float: 角度（度）

        CRITICAL: point2が頂点
        """
        # ベクトル計算
        v1 = np.array([point1['x'] - point2['x'], point1['y'] - point2['y']])
        v2 = np.array([point3['x'] - point2['x'], point3['y'] - point2['y']])

        # 内積とノルム
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 数値誤差対策
        angle = np.arccos(cos_angle) * 180 / np.pi

        return angle

    def _check_stride_mimic(self, landmarks_list: List[dict]) -> Tuple[bool, str, dict]:
        """
        What: スケートストライド模倣の特徴チェック（姿勢ベース）
        Why: 撮影角度に依存しない姿勢の特徴で検出
        Design Decision: 膝屈曲 + 片足荷重切り替え + 低い姿勢をチェック（2025-11-01修正v3）

        CRITICAL:
        - スケーティング姿勢の特徴を検出（動きの方向に依存しない）
        - 1. 膝の屈曲（90-140度のスクワット姿勢）
        - 2. 片足荷重の切り替え（左右足首のy座標差が変化）
        - 3. 低い姿勢（腰の平均高さが低い）
        """
        knee_angles = []
        ankle_y_diffs = []
        hip_y_positions = []

        for lm in landmarks_list:
            # 1. 膝の屈曲角度（左膝）
            if 'LEFT_HIP' in lm and 'LEFT_KNEE' in lm and 'LEFT_ANKLE' in lm:
                angle = self._calculate_angle(lm['LEFT_HIP'], lm['LEFT_KNEE'], lm['LEFT_ANKLE'])
                knee_angles.append(angle)

            # 2. 片足荷重の切り替え（左右足首のy座標差）
            if 'LEFT_ANKLE' in lm and 'RIGHT_ANKLE' in lm:
                y_diff = abs(lm['LEFT_ANKLE']['y'] - lm['RIGHT_ANKLE']['y'])
                ankle_y_diffs.append(y_diff)

            # 3. 低い姿勢（腰の高さ）
            if 'LEFT_HIP' in lm and 'RIGHT_HIP' in lm:
                hip_y = (lm['LEFT_HIP']['y'] + lm['RIGHT_HIP']['y']) / 2
                hip_y_positions.append(hip_y)

        if len(knee_angles) < 10 or len(ankle_y_diffs) < 10 or len(hip_y_positions) < 10:
            return (True, "ランドマーク検出不可", {})

        # 姿勢チェック1: 膝の屈曲（スケーティングは90-140度）
        avg_knee_angle = np.mean(knee_angles)
        min_knee_angle = min(knee_angles)
        is_knee_bent = 90 <= avg_knee_angle <= 140 or min_knee_angle < 120

        # 姿勢チェック2: 片足荷重の切り替え（y座標差の変化）
        ankle_y_diff_range = max(ankle_y_diffs) - min(ankle_y_diffs)
        is_weight_shift = ankle_y_diff_range > 0.08  # 画面高さの8%以上変化

        # 姿勢チェック3: 低い姿勢（腰の平均高さが0.6以上 = 画面下半分）
        avg_hip_y = np.mean(hip_y_positions)
        is_low_posture = avg_hip_y > 0.5  # y座標は上が0、下が1

        details = {
            'avg_knee_angle': float(avg_knee_angle),
            'min_knee_angle': float(min_knee_angle),
            'ankle_y_diff_range': float(ankle_y_diff_range),
            'avg_hip_y': float(avg_hip_y),
            'is_knee_bent': is_knee_bent,
            'is_weight_shift': is_weight_shift,
            'is_low_posture': is_low_posture,
            'note': '姿勢ベース検出（撮影角度非依存）'
        }

        # スケーティング姿勢判定（3つのうち2つ以上満たせばOK）
        posture_score = sum([is_knee_bent, is_weight_shift, is_low_posture])

        if posture_score >= 2:
            return (True, "", details)
        else:
            reasons = []
            if not is_knee_bent:
                reasons.append(f"膝の屈曲不足（平均{avg_knee_angle:.1f}度）")
            if not is_weight_shift:
                reasons.append("片足荷重の切り替えが検出されませんでした")
            if not is_low_posture:
                reasons.append("低い姿勢（スクワット）が検出されませんでした")

            return (False, "スケーティング姿勢が検出されませんでした: " + "、".join(reasons), details)

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
        Why: 手首の前後動（z座標）または横動き（x座標）+ 肩の回旋が小さい
        Design Decision: アームスイングとの区別のため肩回旋チェック追加（ADR-026）

        CRITICAL:
        - プッシュプル = 上体を捻らず腕を伸ばす動き（両肩が同じように前後に動く）
        - アームスイング = 上体を捻る動き（片方の肩が前、片方が後ろ）
        - 肩の回旋 = 左右肩のz座標の差（上体の捻り具合）
        - 肩ラインの傾き（高さの違い）はプッシュプルでもOK
        """
        wrist_x_positions = []
        wrist_z_positions = []
        shoulder_angles = []

        for lm in landmarks_list:
            if 'LEFT_WRIST' in lm and 'RIGHT_WRIST' in lm:
                # x座標（横方向）: 横向き撮影でのプッシュプル
                avg_x = (lm['LEFT_WRIST']['x'] + lm['RIGHT_WRIST']['x']) / 2
                wrist_x_positions.append(avg_x)

                # z座標（奥行き）: 正面撮影でのプッシュプル
                avg_z = (lm['LEFT_WRIST']['z'] + lm['RIGHT_WRIST']['z']) / 2
                wrist_z_positions.append(avg_z)

            # 肩の回旋（アームスイングとの区別）
            # 左右肩のz座標の差 = 上体の捻り具合
            if 'LEFT_SHOULDER' in lm and 'RIGHT_SHOULDER' in lm:
                z_diff = abs(lm['RIGHT_SHOULDER']['z'] - lm['LEFT_SHOULDER']['z'])
                shoulder_angles.append(z_diff)

        if len(wrist_z_positions) < 10 or len(shoulder_angles) < 10:
            return (True, "手首または肩の検出不可", {})

        wrist_x_range = max(wrist_x_positions) - min(wrist_x_positions)
        wrist_z_range = max(wrist_z_positions) - min(wrist_z_positions)

        # 肩の回旋の最大値（左右肩のz座標差）
        # プッシュプル: 両肩が同じように動く → z差が小さい
        # アームスイング: 片方の肩が前、片方が後ろ → z差が大きい
        max_shoulder_twist = max(shoulder_angles)

        wrist_threshold = 0.2
        has_side_motion = wrist_x_range > wrist_threshold
        has_front_motion = wrist_z_range > wrist_threshold

        if not has_side_motion:
            details = {
                'wrist_x_range': float(wrist_x_range),
                'wrist_z_range': float(wrist_z_range),
                'shoulder_twist': float(max_shoulder_twist),
                'wrist_threshold': float(wrist_threshold),
                'required_orientation': 'side',
                'detected_axis': 'z' if has_front_motion else 'insufficient',
                'camera_angle': 'front' if has_front_motion else 'undetermined'
            }

            if has_front_motion:
                return (
                    False,
                    f"この種目は横方向での撮影が必須です。手首の動きが前後方向に大きく検出されています（x変化:{wrist_x_range:.2f}, z変化:{wrist_z_range:.2f}）。カメラを横に配置して再撮影してください。",
                    details,
                )

            return (
                False,
                f"手首の動きが不足しています（x変化:{wrist_x_range:.2f}, z変化:{wrist_z_range:.2f}）。横方向から撮影し、腕を前後に押し引きしてください。",
                details,
            )

        # 横方向撮影が確認できた場合のみ肩の回旋をチェック
        shoulder_threshold = 0.5
        shoulder_stable = max_shoulder_twist < shoulder_threshold

        details = {
            'wrist_x_range': float(wrist_x_range),
            'wrist_z_range': float(wrist_z_range),
            'shoulder_twist': float(max_shoulder_twist),
            'wrist_threshold': float(wrist_threshold),
            'shoulder_threshold': float(shoulder_threshold),
            'detected_axis': 'x',
            'camera_angle': 'side',
            'required_orientation': 'side',
        }

        is_push_pull = shoulder_stable

        if is_push_pull:
            return (True, "", details)
        else:
            return (
                False,
                f"肩の回旋が大きすぎます（左右差:{max_shoulder_twist:.2f}, 閾値:{shoulder_threshold}）。アームスイングの可能性があります。胸郭を正面に保ったまま腕を押し引きしてください。",
                details,
            )

    def _check_cross_step(self, landmarks_list: List[dict]) -> Tuple[bool, str, dict]:
        """
        What: クロスステップ模倣の特徴チェック
        Why: 足が接近・交差する動き
        Design Decision: 左右足の接近度 + フレーム間での交差をチェック（2025-11-01修正）

        CRITICAL:
        - クロスステップ = 足が接近する（x座標の差が小さい）瞬間がある
        - 静的な位置関係ではなく、動的な接近を検出
        """
        ankle_x_diffs = []
        cross_transitions = 0
        prev_left_is_left = None  # 前フレームでの左右関係

        for lm in landmarks_list:
            if 'LEFT_ANKLE' in lm and 'RIGHT_ANKLE' in lm:
                left_x = lm['LEFT_ANKLE']['x']
                right_x = lm['RIGHT_ANKLE']['x']

                # 左右足のx座標の差（接近度）
                x_diff = abs(left_x - right_x)
                ankle_x_diffs.append(x_diff)

                # フレーム間での左右関係の逆転（交差）を検出
                current_left_is_left = left_x < right_x
                if prev_left_is_left is not None and prev_left_is_left != current_left_is_left:
                    cross_transitions += 1
                prev_left_is_left = current_left_is_left

        if len(ankle_x_diffs) < 10:
            return (True, "足首検出不可", {})

        # 足の接近度（最小値が小さいほど接近）
        min_x_diff = min(ankle_x_diffs)
        avg_x_diff = np.mean(ankle_x_diffs)

        # クロスステップ判定条件（いずれかを満たせばOK）:
        # 1. 左右足が接近する瞬間がある（x座標差 < 0.15 = 画面幅の15%）
        is_close_approach = min_x_diff < 0.15

        # 2. フレーム間で左右の足が入れ替わる（交差）がある
        has_cross_transition = cross_transitions >= 1

        # 3. 平均的に左右足が近い（横方向の動きが大きい）
        is_narrow_stance = avg_x_diff < 0.25

        is_cross_step = is_close_approach or has_cross_transition or is_narrow_stance

        details = {
            'min_x_diff': float(min_x_diff),
            'avg_x_diff': float(avg_x_diff),
            'cross_transitions': cross_transitions,
            'close_approach_threshold': 0.15,
            'narrow_stance_threshold': 0.25,
            'is_close_approach': is_close_approach,
            'has_cross_transition': has_cross_transition,
            'is_narrow_stance': is_narrow_stance
        }

        if is_cross_step:
            return (True, "", details)
        else:
            return (False, "クロスステップ動作（足の接近・交差）が検出されませんでした", details)
