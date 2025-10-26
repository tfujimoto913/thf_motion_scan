"""
Purpose: Jump Landing (T04) evaluator for 2-axis evaluation system
Responsibility:
    - A. Execution evaluation (3 points): Jump height + Landing timing sync + Posture stability
    - B. Principles evaluation (9 points): P2 Center of mass + P4 Joint angles + P1 Joint coordination
Dependencies: numpy, config.json (T04_jump_landing thresholds)
Created: 2025-10-25 by Claude Code
Decision Log: ADR-010 (2-axis evaluation system)

CRITICAL: All metrics are objective only - angles (degrees), distances (normalized ratios),
         time (frames/seconds), standard deviation. NO subjective metrics allowed.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np


class JumpLandingEvaluator:
    """
    What: Evaluates Jump Landing movement (mini jump & landing)
    Why: Assesses jump height, landing control, joint angles, and coordination during landing impact
    Design Decision: 2-axis evaluation (A: Execution 3pts, B: Principles 9pts) - ADR-010

    CRITICAL: MediaPipe Pose 33-landmark system required
    """

    # PHASE CORE LOGIC: MediaPipe Pose landmark indices (0-32)
    # CRITICAL: Do not modify without updating all dependent calculations
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32

    def __init__(self, config_path: Optional[str] = None):
        """
        What: Initialize evaluator with config thresholds
        Why: External config ensures no hardcoded thresholds (CLAUDE.md requirement)
        Design Decision: config.json centralized thresholds - ADR-001
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / 'config.json'

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # CRITICAL: All thresholds from config.json T04_jump_landing section
        self.thresholds = config['thresholds']['T04_jump_landing']
        self.config = config

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float, fps: float = 30.0) -> Dict:
        """
        What: Main evaluation entry point - returns 12-point structure
        Why: Combines execution (A: 3pts) and principles (B: 9pts) scores
        Design Decision: 2-axis evaluation system - ADR-010

        Args:
            landmarks_data: List of frame data with MediaPipe landmarks
            base_width: Normalization factor (max of shoulder/pelvis width)
            shoulder_width: Distance between landmarks 11-12
            fps: Frames per second for timing calculations

        Returns:
            {
                'test_id': 'T04_jump_landing',
                'execution': {..., 'total': 0-3},
                'principles': {..., 'total': 0-9},
                'total': 0-12,
                'max_score': 12.0
            }

        CRITICAL: Total score = execution + principles (max 12.0)
        """
        if not landmarks_data or base_width <= 0 or shoulder_width <= 0:
            return {
                'test_id': 'T04_jump_landing',
                'execution': {'total': 0.0, 'details': 'Invalid input data'},
                'principles': {'total': 0.0, 'details': 'Invalid input data'},
                'total': 0.0,
                'max_score': 12.0,
                'error': 'Invalid input: empty landmarks or invalid normalization factors'
            }

        execution = self.evaluate_execution(landmarks_data, base_width, shoulder_width, fps)
        principles = self.evaluate_principles(landmarks_data, base_width, shoulder_width, fps)

        return {
            'test_id': 'T04_jump_landing',
            'execution': execution,
            'principles': principles,
            'total': execution['total'] + principles['total'],
            'max_score': 12.0
        }

    def evaluate_execution(self, landmarks_data: List[Dict], base_width: float,
                           shoulder_width: float, fps: float = 30.0) -> Dict:
        """
        What: A. Execution evaluation (3 points total)
        Why: Objective metrics for jump height, landing timing, and stability
        Design Decision: Split into A1 (jump height 1pt) + A2 (landing sync 1pt) + A3 (stability 1pt)

        Returns:
            {
                'A1_jump_height': {'score': 0-1.0, ...},
                'A2_landing_timing_sync': {'score': 0-1.0, ...},
                'A3_posture_stability': {'score': 0-1.0, ...},
                'total': 0-3.0
            }

        CRITICAL: All metrics are objective - heights as ratios, timing in seconds, distances normalized
        """
        a1_jump_height = self._score_jump_height(landmarks_data)
        a2_landing_sync = self._score_landing_timing_sync(landmarks_data, fps)
        a3_posture_stability = self._score_posture_stability(landmarks_data, shoulder_width, fps)

        return {
            'A1_jump_height': a1_jump_height,
            'A2_landing_timing_sync': a2_landing_sync,
            'A3_posture_stability': a3_posture_stability,
            'total': a1_jump_height['score'] + a2_landing_sync['score'] + a3_posture_stability['score']
        }

    def evaluate_principles(self, landmarks_data: List[Dict], base_width: float,
                           shoulder_width: float, fps: float = 30.0) -> Dict:
        """
        What: B. Principles evaluation (9 points total)
        Why: Assesses adherence to 3 movement principles (3 points each)
        Design Decision: P2 (center of mass) + P4 (joint angles) + P1 (coordination)

        Returns:
            {
                'P2_center_of_mass': {'score': 0-3.0, ...},
                'P4_joint_angles': {'score': 0-3.0, ...},
                'P1_joint_coordination': {'score': 0-3.0, ...},
                'total': 0-9.0
            }

        CRITICAL: Deduction-based scoring - start at 3.0, deduct for violations
        """
        p2_com = self._evaluate_principle_2(landmarks_data, base_width, shoulder_width, fps)
        p4_joint_angles = self._evaluate_principle_4(landmarks_data, fps)
        p1_coordination = self._evaluate_principle_1(landmarks_data, fps)

        return {
            'P2_center_of_mass': p2_com,
            'P4_joint_angles': p4_joint_angles,
            'P1_joint_coordination': p1_coordination,
            'total': p2_com['score'] + p4_joint_angles['score'] + p1_coordination['score']
        }

    # ============================================================================
    # A. Execution Scoring Methods
    # ============================================================================

    def _score_jump_height(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: A1. Jump height scoring (1 point)
        Why: Assesses hip elevation relative to body height
        Design Decision: Use body height estimate (nose to ankle distance when standing)

        Thresholds (config.json):
            - Jump height ratio: ≥0.15 excellent (1.0), ≥0.10 good (0.5), else poor (0.0)

        CRITICAL: MediaPipe landmarks - HIP (23/24), NOSE (0), ANKLE (27/28)
        """
        thresholds = self.thresholds['execution']['jump_height']

        # Estimate body height from standing position (first 5 frames)
        body_height = self._estimate_body_height(landmarks_data[:min(5, len(landmarks_data))])

        if body_height is None or body_height <= 0:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'jump_height_ratio': None,
                'body_height': None,
                'comment': 'Unable to estimate body height'
            }

        # Calculate hip elevation (center of left and right hips)
        hip_heights = []
        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            left_hip = landmarks[self.LEFT_HIP]
            right_hip = landmarks[self.RIGHT_HIP]
            hip_center_y = (left_hip['y'] + right_hip['y']) / 2
            hip_heights.append(hip_center_y)

        if not hip_heights:
            return {'score': 0.0, 'max_score': 1.0, 'jump_height_ratio': None}

        # Standing hip height (average of first 5 frames)
        standing_hip_height = np.mean(hip_heights[:min(5, len(hip_heights))])
        # Maximum elevation (minimum Y value, as Y increases downward)
        max_elevation_y = min(hip_heights)
        # Jump height in image coordinates
        jump_height = standing_hip_height - max_elevation_y
        # Normalized by body height
        jump_height_ratio = jump_height / body_height

        # Score based on thresholds
        if jump_height_ratio >= thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif jump_height_ratio >= thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'max_score': 1.0,
            'jump_height_ratio': float(jump_height_ratio),
            'jump_height': float(jump_height),
            'body_height': float(body_height),
            'grade': grade,
            'unit': 'ratio_to_body_height'
        }

    def _score_landing_timing_sync(self, landmarks_data: List[Dict], fps: float) -> Dict:
        """
        What: A2. Landing timing synchronization scoring (1 point)
        Why: Assesses bilateral coordination - both feet should land simultaneously
        Design Decision: Detect landing frame for each foot using ankle Y-velocity

        Thresholds (config.json):
            - Time difference: <0.05s excellent (1.0), <0.10s good (0.5), else poor (0.0)

        CRITICAL: MediaPipe Y-coordinate increases downward, landing = velocity decreases to zero
        """
        thresholds = self.thresholds['execution']['landing_timing_sync']

        # Detect landing frames for left and right feet
        left_landing = self._detect_landing_frame(landmarks_data, 'left')
        right_landing = self._detect_landing_frame(landmarks_data, 'right')

        if left_landing is None or right_landing is None:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'time_difference': None,
                'comment': 'Unable to detect landing frames'
            }

        # Calculate time difference
        frame_diff = abs(left_landing - right_landing)
        time_diff = frame_diff / fps

        # Score based on thresholds
        if time_diff < thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif time_diff < thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'max_score': 1.0,
            'time_difference': float(time_diff),
            'frame_difference': int(frame_diff),
            'left_landing_frame': int(left_landing),
            'right_landing_frame': int(right_landing),
            'grade': grade,
            'unit': 'seconds'
        }

    def _score_posture_stability(self, landmarks_data: List[Dict],
                                 shoulder_width: float, fps: float) -> Dict:
        """
        What: A3. Posture stability after landing scoring (1 point)
        Why: Assesses ability to maintain balance after landing impact
        Design Decision: Measure COM sway distance for 2 seconds (60 frames) after landing

        Thresholds (config.json):
            - Sway distance: <1.0× shoulder_width excellent (1.0), <2.0× good (0.5), else poor (0.0)

        CRITICAL: COM = midpoint of hips, sway = total path length traveled
        """
        thresholds = self.thresholds['execution']['posture_stability']

        # Detect landing frame
        landing_frame = self._detect_landing_frame(landmarks_data, 'left')
        if landing_frame is None:
            landing_frame = self._detect_landing_frame(landmarks_data, 'right')

        if landing_frame is None:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'sway_distance_ratio': None,
                'comment': 'Unable to detect landing frame'
            }

        # Extract 2-second stabilization phase (60 frames at 30fps)
        stabilization_frames = int(2.0 * fps)
        end_frame = min(landing_frame + stabilization_frames, len(landmarks_data))
        stability_phase = landmarks_data[landing_frame:end_frame]

        if len(stability_phase) < 10:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'sway_distance_ratio': None,
                'comment': 'Insufficient frames for stability analysis'
            }

        # Calculate COM trajectory and total sway distance
        com_positions = []
        for frame_data in stability_phase:
            landmarks = frame_data['landmarks']
            left_hip = landmarks[self.LEFT_HIP]
            right_hip = landmarks[self.RIGHT_HIP]
            com_x = (left_hip['x'] + right_hip['x']) / 2
            com_y = (left_hip['y'] + right_hip['y']) / 2
            com_positions.append((com_x, com_y))

        # Total path length
        sway_distance = 0.0
        for i in range(1, len(com_positions)):
            dx = com_positions[i][0] - com_positions[i-1][0]
            dy = com_positions[i][1] - com_positions[i-1][1]
            sway_distance += np.sqrt(dx**2 + dy**2)

        # Normalize by shoulder width
        sway_distance_ratio = sway_distance / shoulder_width if shoulder_width > 0 else 0.0

        # Score based on thresholds
        if sway_distance_ratio < thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif sway_distance_ratio < thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'max_score': 1.0,
            'sway_distance_ratio': float(sway_distance_ratio),
            'sway_distance': float(sway_distance),
            'grade': grade,
            'unit': 'ratio_to_shoulder_width'
        }

    # ============================================================================
    # B. Principles Evaluation Methods
    # ============================================================================

    def _evaluate_principle_2(self, landmarks_data: List[Dict], base_width: float,
                             shoulder_width: float, fps: float) -> Dict:
        """
        What: P2. Center of mass evaluation (3 points)
        Why: Assesses COM control during landing - descent control, horizontal position, height maintenance
        Design Decision: 1pt per sub-metric

        Sub-metrics:
            - Descent control: Max/avg descent speed ratio
            - Horizontal position: COM-foot horizontal distance
            - Height maintenance: Hip descent rate (15-25% optimal)

        CRITICAL: MediaPipe landmarks - HIP (23/24), ANKLE (27/28)
        """
        thresholds = self.thresholds['principles']['P2_center_of_mass']

        # Detect landing phase
        landing_frame = self._detect_landing_frame(landmarks_data, 'left')
        if landing_frame is None:
            landing_frame = self._detect_landing_frame(landmarks_data, 'right')

        if landing_frame is None:
            return {
                'score': 0.0,
                'max_score': 3.0,
                'descent_control': {'score': 0.0},
                'horizontal_position': {'score': 0.0},
                'height_maintenance': {'score': 0.0},
                'comment': 'Unable to detect landing'
            }

        # Find landing nadir (lowest hip point after landing)
        nadir_frame = self._find_landing_nadir(landmarks_data, landing_frame)

        # 1. Descent control
        descent_control = self._evaluate_descent_control(
            landmarks_data, landing_frame, nadir_frame, fps, thresholds['descent_control']
        )

        # 2. Horizontal position
        horizontal_position = self._evaluate_horizontal_position(
            landmarks_data, landing_frame, nadir_frame, shoulder_width, thresholds['horizontal_position']
        )

        # 3. Height maintenance
        height_maintenance = self._evaluate_height_maintenance(
            landmarks_data, nadir_frame, thresholds['height_maintenance']
        )

        total_score = descent_control['score'] + horizontal_position['score'] + height_maintenance['score']

        return {
            'score': total_score,
            'max_score': 3.0,
            'descent_control': descent_control,
            'horizontal_position': horizontal_position,
            'height_maintenance': height_maintenance
        }

    def _evaluate_principle_4(self, landmarks_data: List[Dict], fps: float) -> Dict:
        """
        What: P4. Joint angles evaluation (3 points)
        Why: Assesses joint angles at landing nadir - knee, hip, ankle
        Design Decision: 1pt per joint angle

        Sub-metrics:
            - Knee flexion: 70-100° excellent
            - Hip flexion: 70-100° excellent
            - Ankle angle: 80-100° excellent

        CRITICAL: MediaPipe landmarks - SHOULDER, HIP, KNEE, ANKLE, FOOT_INDEX
        """
        thresholds = self.thresholds['principles']['P4_joint_angles']

        # Detect landing and nadir
        landing_frame = self._detect_landing_frame(landmarks_data, 'left')
        if landing_frame is None:
            landing_frame = self._detect_landing_frame(landmarks_data, 'right')

        if landing_frame is None:
            return {
                'score': 0.0,
                'max_score': 3.0,
                'knee_flexion': {'score': 0.0},
                'hip_flexion': {'score': 0.0},
                'ankle_angle': {'score': 0.0}
            }

        nadir_frame = self._find_landing_nadir(landmarks_data, landing_frame)

        # Calculate joint angles at nadir
        nadir_landmarks = landmarks_data[nadir_frame]['landmarks']

        # 1. Knee flexion
        knee_flexion = self._evaluate_knee_flexion_at_nadir(nadir_landmarks, thresholds['knee_flexion'])

        # 2. Hip flexion
        hip_flexion = self._evaluate_hip_flexion_at_nadir(nadir_landmarks, thresholds['hip_flexion'])

        # 3. Ankle angle during landing phase
        ankle_angle = self._evaluate_ankle_angle_during_landing(
            landmarks_data, landing_frame, nadir_frame, thresholds['ankle_angle']
        )

        total_score = knee_flexion['score'] + hip_flexion['score'] + ankle_angle['score']

        return {
            'score': total_score,
            'max_score': 3.0,
            'knee_flexion': knee_flexion,
            'hip_flexion': hip_flexion,
            'ankle_angle': ankle_angle
        }

    def _evaluate_principle_1(self, landmarks_data: List[Dict], fps: float) -> Dict:
        """
        What: P1. Joint coordination evaluation (3 points)
        Why: Assesses temporal sequencing and consistency of joint flexion
        Design Decision: 1pt per sub-metric

        Sub-metrics:
            - Ankle-knee timing: 0.03-0.10s optimal
            - Knee-hip timing: 0.03-0.10s optimal
            - Coordination consistency: CV <0.4 excellent

        CRITICAL: Proximal-to-distal or distal-to-proximal sequencing both acceptable
        """
        thresholds = self.thresholds['principles']['P1_joint_coordination']

        # Detect landing
        landing_frame = self._detect_landing_frame(landmarks_data, 'left')
        if landing_frame is None:
            landing_frame = self._detect_landing_frame(landmarks_data, 'right')

        if landing_frame is None:
            return {
                'score': 0.0,
                'max_score': 3.0,
                'ankle_knee_timing': {'score': 0.0},
                'knee_hip_timing': {'score': 0.0},
                'coordination_consistency': {'score': 0.0}
            }

        nadir_frame = self._find_landing_nadir(landmarks_data, landing_frame)

        # 1. Ankle-knee timing
        ankle_knee_timing = self._evaluate_ankle_knee_timing(
            landmarks_data, landing_frame, nadir_frame, fps, thresholds['ankle_knee_timing']
        )

        # 2. Knee-hip timing
        knee_hip_timing = self._evaluate_knee_hip_timing(
            landmarks_data, landing_frame, nadir_frame, fps, thresholds['knee_hip_timing']
        )

        # 3. Coordination consistency
        coordination_consistency = self._evaluate_coordination_consistency(
            landmarks_data, landing_frame, nadir_frame, fps, thresholds['coordination_consistency']
        )

        total_score = ankle_knee_timing['score'] + knee_hip_timing['score'] + coordination_consistency['score']

        return {
            'score': total_score,
            'max_score': 3.0,
            'ankle_knee_timing': ankle_knee_timing,
            'knee_hip_timing': knee_hip_timing,
            'coordination_consistency': coordination_consistency
        }

    # ============================================================================
    # Helper Functions - Phase Detection
    # ============================================================================

    def _estimate_body_height(self, standing_frames: List[Dict]) -> Optional[float]:
        """
        What: Estimate body height from standing position
        Why: Normalize jump height relative to individual body size
        Design Decision: Use NOSE to ANKLE distance as body height proxy

        Returns:
            Body height estimate, or None if calculation fails
        """
        if not standing_frames:
            return None

        heights = []
        for frame_data in standing_frames:
            landmarks = frame_data['landmarks']
            nose = landmarks[self.NOSE]
            left_ankle = landmarks[self.LEFT_ANKLE]
            right_ankle = landmarks[self.RIGHT_ANKLE]
            ankle_avg_y = (left_ankle['y'] + right_ankle['y']) / 2

            height = ankle_avg_y - nose['y']  # Y increases downward
            heights.append(height)

        return float(np.mean(heights)) if heights else None

    def _detect_landing_frame(self, landmarks_data: List[Dict], side: str) -> Optional[int]:
        """
        What: Detect landing frame for left or right foot
        Why: Identify moment of ground contact after jump
        Design Decision: Detect when ankle Y-velocity decreases to near zero after descent

        Args:
            landmarks_data: All frame data
            side: 'left' or 'right'

        Returns:
            Frame index of landing, or None if not detected

        CRITICAL: Landing = ankle descending rapidly then suddenly decelerating
        """
        if side == 'left':
            ankle_idx = self.LEFT_ANKLE
        else:
            ankle_idx = self.RIGHT_ANKLE

        # Extract ankle Y positions
        ankle_y_positions = [frame['landmarks'][ankle_idx]['y'] for frame in landmarks_data]

        if len(ankle_y_positions) < 3:
            return None

        # Calculate velocities (positive = descending)
        velocities = []
        for i in range(1, len(ankle_y_positions)):
            velocity = ankle_y_positions[i] - ankle_y_positions[i-1]
            velocities.append(velocity)

        # Find landing: first frame where velocity drops below threshold after peak descent
        peak_descent_velocity = max(velocities) if velocities else 0
        landing_threshold = peak_descent_velocity * 0.2  # 20% of peak descent velocity

        in_descent = False
        for i, velocity in enumerate(velocities):
            if velocity > peak_descent_velocity * 0.5:
                in_descent = True
            elif in_descent and velocity < landing_threshold:
                return i + 1  # Return frame index (+1 because velocities are offset)

        return None

    def _find_landing_nadir(self, landmarks_data: List[Dict], landing_frame: int) -> int:
        """
        What: Find landing nadir (lowest hip point after landing)
        Why: Identify moment of maximum landing flexion
        Design Decision: Search for highest Y value (lowest position) of hip center after landing

        Returns:
            Frame index of landing nadir
        """
        # Search window: 30 frames (1 second) after landing
        search_end = min(landing_frame + 30, len(landmarks_data))

        max_hip_y = -float('inf')
        nadir_frame = landing_frame

        for i in range(landing_frame, search_end):
            landmarks = landmarks_data[i]['landmarks']
            left_hip = landmarks[self.LEFT_HIP]
            right_hip = landmarks[self.RIGHT_HIP]
            hip_center_y = (left_hip['y'] + right_hip['y']) / 2

            if hip_center_y > max_hip_y:
                max_hip_y = hip_center_y
                nadir_frame = i

        return nadir_frame

    # ============================================================================
    # Helper Functions - P2 Center of Mass
    # ============================================================================

    def _evaluate_descent_control(self, landmarks_data: List[Dict], landing_frame: int,
                                  nadir_frame: int, fps: float, thresholds: Dict) -> Dict:
        """
        What: Evaluate descent control using max/avg speed ratio
        Why: Smooth descent indicates controlled landing
        """
        hip_positions = []
        for i in range(landing_frame, nadir_frame + 1):
            if i < len(landmarks_data):
                landmarks = landmarks_data[i]['landmarks']
                left_hip = landmarks[self.LEFT_HIP]
                right_hip = landmarks[self.RIGHT_HIP]
                hip_y = (left_hip['y'] + right_hip['y']) / 2
                hip_positions.append(hip_y)

        if len(hip_positions) < 2:
            return {'score': 0.0, 'speed_ratio': None}

        # Calculate descent speeds
        speeds = []
        for i in range(1, len(hip_positions)):
            speed = abs(hip_positions[i] - hip_positions[i-1]) * fps
            speeds.append(speed)

        if not speeds:
            return {'score': 0.0, 'speed_ratio': None}

        max_speed = max(speeds)
        avg_speed = np.mean(speeds)
        speed_ratio = max_speed / avg_speed if avg_speed > 0 else 0.0

        # Score based on thresholds
        if speed_ratio < thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif speed_ratio < thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'speed_ratio': float(speed_ratio),
            'max_speed': float(max_speed),
            'avg_speed': float(avg_speed),
            'grade': grade,
            'unit': 'ratio'
        }

    def _evaluate_horizontal_position(self, landmarks_data: List[Dict], landing_frame: int,
                                     nadir_frame: int, shoulder_width: float, thresholds: Dict) -> Dict:
        """
        What: Evaluate COM-foot horizontal distance during landing
        Why: COM should be over base of support for stability
        """
        # Average over landing phase
        horizontal_distances = []
        for i in range(landing_frame, min(nadir_frame + 10, len(landmarks_data))):
            landmarks = landmarks_data[i]['landmarks']
            left_hip = landmarks[self.LEFT_HIP]
            right_hip = landmarks[self.RIGHT_HIP]
            com_x = (left_hip['x'] + right_hip['x']) / 2

            left_ankle = landmarks[self.LEFT_ANKLE]
            right_ankle = landmarks[self.RIGHT_ANKLE]
            foot_center_x = (left_ankle['x'] + right_ankle['x']) / 2

            distance = abs(com_x - foot_center_x)
            horizontal_distances.append(distance)

        if not horizontal_distances:
            return {'score': 0.0, 'distance_ratio': None}

        avg_distance = np.mean(horizontal_distances)
        distance_ratio = avg_distance / shoulder_width if shoulder_width > 0 else 0.0

        # Score based on thresholds
        if distance_ratio < thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif distance_ratio < thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'distance_ratio': float(distance_ratio),
            'grade': grade,
            'unit': 'ratio_to_shoulder_width'
        }

    def _evaluate_height_maintenance(self, landmarks_data: List[Dict],
                                    nadir_frame: int, thresholds: Dict) -> Dict:
        """
        What: Evaluate hip descent rate from standing to nadir
        Why: Optimal descent is 15-25% of standing height
        """
        # Standing hip height (first 5 frames)
        standing_hip_heights = []
        for i in range(min(5, len(landmarks_data))):
            landmarks = landmarks_data[i]['landmarks']
            left_hip = landmarks[self.LEFT_HIP]
            right_hip = landmarks[self.RIGHT_HIP]
            hip_y = (left_hip['y'] + right_hip['y']) / 2
            standing_hip_heights.append(hip_y)

        standing_hip_height = np.mean(standing_hip_heights) if standing_hip_heights else 0

        # Nadir hip height
        nadir_landmarks = landmarks_data[nadir_frame]['landmarks']
        left_hip = nadir_landmarks[self.LEFT_HIP]
        right_hip = nadir_landmarks[self.RIGHT_HIP]
        nadir_hip_height = (left_hip['y'] + right_hip['y']) / 2

        # Descent rate
        descent = nadir_hip_height - standing_hip_height
        descent_rate = descent / standing_hip_height if standing_hip_height > 0 else 0.0

        # Score based on thresholds (optimal range)
        if thresholds['excellent_min'] <= descent_rate <= thresholds['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif thresholds['good_min'] <= descent_rate <= thresholds['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'descent_rate': float(descent_rate),
            'grade': grade,
            'unit': 'ratio'
        }

    # ============================================================================
    # Helper Functions - P4 Joint Angles
    # ============================================================================

    def _evaluate_knee_flexion_at_nadir(self, nadir_landmarks: List[Dict], thresholds: Dict) -> Dict:
        """
        What: Evaluate knee flexion angle at landing nadir
        Why: Optimal knee flexion absorbs impact
        """
        # Calculate average knee angle (left and right)
        left_knee_angle = self._calculate_knee_angle(nadir_landmarks, 'left')
        right_knee_angle = self._calculate_knee_angle(nadir_landmarks, 'right')

        if left_knee_angle is None or right_knee_angle is None:
            return {'score': 0.0, 'angle': None}

        avg_knee_angle = (left_knee_angle + right_knee_angle) / 2

        # Score based on thresholds
        if thresholds['excellent_min'] <= avg_knee_angle <= thresholds['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif thresholds['good_min'] <= avg_knee_angle <= thresholds['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'angle': float(avg_knee_angle),
            'left_angle': float(left_knee_angle),
            'right_angle': float(right_knee_angle),
            'grade': grade,
            'unit': 'degrees'
        }

    def _evaluate_hip_flexion_at_nadir(self, nadir_landmarks: List[Dict], thresholds: Dict) -> Dict:
        """
        What: Evaluate hip flexion angle at landing nadir
        Why: Optimal hip flexion lowers COM for stability
        """
        # Calculate average hip angle (left and right)
        left_hip_angle = self._calculate_hip_angle(nadir_landmarks, 'left')
        right_hip_angle = self._calculate_hip_angle(nadir_landmarks, 'right')

        if left_hip_angle is None or right_hip_angle is None:
            return {'score': 0.0, 'angle': None}

        avg_hip_angle = (left_hip_angle + right_hip_angle) / 2

        # Score based on thresholds
        if thresholds['excellent_min'] <= avg_hip_angle <= thresholds['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif thresholds['good_min'] <= avg_hip_angle <= thresholds['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'angle': float(avg_hip_angle),
            'left_angle': float(left_hip_angle),
            'right_angle': float(right_hip_angle),
            'grade': grade,
            'unit': 'degrees'
        }

    def _evaluate_ankle_angle_during_landing(self, landmarks_data: List[Dict],
                                            landing_frame: int, nadir_frame: int,
                                            thresholds: Dict) -> Dict:
        """
        What: Evaluate ankle angle during landing phase
        Why: Ankle dorsiflexion controls landing impact
        """
        ankle_angles = []
        for i in range(landing_frame, min(nadir_frame + 10, len(landmarks_data))):
            landmarks = landmarks_data[i]['landmarks']
            left_ankle_angle = self._calculate_ankle_angle(landmarks, 'left')
            right_ankle_angle = self._calculate_ankle_angle(landmarks, 'right')

            if left_ankle_angle is not None and right_ankle_angle is not None:
                avg_angle = (left_ankle_angle + right_ankle_angle) / 2
                ankle_angles.append(avg_angle)

        if not ankle_angles:
            return {'score': 0.0, 'angle': None}

        avg_ankle_angle = np.mean(ankle_angles)

        # Score based on thresholds
        if thresholds['excellent_min'] <= avg_ankle_angle <= thresholds['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif thresholds['good_min'] <= avg_ankle_angle <= thresholds['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'angle': float(avg_ankle_angle),
            'grade': grade,
            'unit': 'degrees'
        }

    # ============================================================================
    # Helper Functions - P1 Joint Coordination
    # ============================================================================

    def _evaluate_ankle_knee_timing(self, landmarks_data: List[Dict], landing_frame: int,
                                   nadir_frame: int, fps: float, thresholds: Dict) -> Dict:
        """
        What: Evaluate ankle-knee flexion timing difference
        Why: Sequential joint activation indicates proper coordination
        """
        # Detect flexion start for ankle and knee
        ankle_start = self._detect_joint_flexion_start(
            landmarks_data, landing_frame, nadir_frame, 'ankle'
        )
        knee_start = self._detect_joint_flexion_start(
            landmarks_data, landing_frame, nadir_frame, 'knee'
        )

        if ankle_start is None or knee_start is None:
            return {'score': 0.0, 'time_difference': None}

        frame_diff = abs(knee_start - ankle_start)
        time_diff = frame_diff / fps

        # Score based on thresholds (optimal range)
        if thresholds['excellent_min'] <= time_diff <= thresholds['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif thresholds['good_min'] <= time_diff <= thresholds['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'time_difference': float(time_diff),
            'grade': grade,
            'unit': 'seconds'
        }

    def _evaluate_knee_hip_timing(self, landmarks_data: List[Dict], landing_frame: int,
                                 nadir_frame: int, fps: float, thresholds: Dict) -> Dict:
        """
        What: Evaluate knee-hip flexion timing difference
        Why: Sequential joint activation indicates proper coordination
        """
        knee_start = self._detect_joint_flexion_start(
            landmarks_data, landing_frame, nadir_frame, 'knee'
        )
        hip_start = self._detect_joint_flexion_start(
            landmarks_data, landing_frame, nadir_frame, 'hip'
        )

        if knee_start is None or hip_start is None:
            return {'score': 0.0, 'time_difference': None}

        frame_diff = abs(hip_start - knee_start)
        time_diff = frame_diff / fps

        # Score based on thresholds (optimal range)
        if thresholds['excellent_min'] <= time_diff <= thresholds['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif thresholds['good_min'] <= time_diff <= thresholds['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'time_difference': float(time_diff),
            'grade': grade,
            'unit': 'seconds'
        }

    def _evaluate_coordination_consistency(self, landmarks_data: List[Dict], landing_frame: int,
                                          nadir_frame: int, fps: float, thresholds: Dict) -> Dict:
        """
        What: Evaluate joint velocity consistency (coefficient of variation)
        Why: Consistent velocities indicate coordinated movement
        """
        # Calculate angular velocities for each joint during landing phase
        ankle_velocities = []
        knee_velocities = []
        hip_velocities = []

        for i in range(landing_frame, nadir_frame):
            if i + 1 >= len(landmarks_data):
                break

            # Ankle velocity
            ankle_angle_t0 = self._calculate_ankle_angle(landmarks_data[i]['landmarks'], 'left')
            ankle_angle_t1 = self._calculate_ankle_angle(landmarks_data[i+1]['landmarks'], 'left')
            if ankle_angle_t0 is not None and ankle_angle_t1 is not None:
                ankle_velocity = abs(ankle_angle_t1 - ankle_angle_t0) * fps
                ankle_velocities.append(ankle_velocity)

            # Knee velocity
            knee_angle_t0 = self._calculate_knee_angle(landmarks_data[i]['landmarks'], 'left')
            knee_angle_t1 = self._calculate_knee_angle(landmarks_data[i+1]['landmarks'], 'left')
            if knee_angle_t0 is not None and knee_angle_t1 is not None:
                knee_velocity = abs(knee_angle_t1 - knee_angle_t0) * fps
                knee_velocities.append(knee_velocity)

            # Hip velocity
            hip_angle_t0 = self._calculate_hip_angle(landmarks_data[i]['landmarks'], 'left')
            hip_angle_t1 = self._calculate_hip_angle(landmarks_data[i+1]['landmarks'], 'left')
            if hip_angle_t0 is not None and hip_angle_t1 is not None:
                hip_velocity = abs(hip_angle_t1 - hip_angle_t0) * fps
                hip_velocities.append(hip_velocity)

        # Calculate average velocities
        if not ankle_velocities or not knee_velocities or not hip_velocities:
            return {'score': 0.0, 'cv': None}

        avg_ankle_velocity = np.mean(ankle_velocities)
        avg_knee_velocity = np.mean(knee_velocities)
        avg_hip_velocity = np.mean(hip_velocities)

        velocities = [avg_ankle_velocity, avg_knee_velocity, avg_hip_velocity]
        mean_velocity = np.mean(velocities)
        std_velocity = np.std(velocities)
        cv = std_velocity / mean_velocity if mean_velocity > 0 else 0.0

        # Score based on thresholds
        if cv < thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif cv < thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'cv': float(cv),
            'grade': grade,
            'unit': 'coefficient_of_variation'
        }

    def _detect_joint_flexion_start(self, landmarks_data: List[Dict], landing_frame: int,
                                   nadir_frame: int, joint_type: str) -> Optional[int]:
        """
        What: Detect frame where joint begins flexing (angle decreasing by >5°)
        Why: Identify flexion onset for timing analysis
        """
        # Get pre-landing angle (average of 5 frames before landing)
        pre_landing_angles = []
        for i in range(max(0, landing_frame - 5), landing_frame):
            if joint_type == 'ankle':
                angle = self._calculate_ankle_angle(landmarks_data[i]['landmarks'], 'left')
            elif joint_type == 'knee':
                angle = self._calculate_knee_angle(landmarks_data[i]['landmarks'], 'left')
            elif joint_type == 'hip':
                angle = self._calculate_hip_angle(landmarks_data[i]['landmarks'], 'left')
            else:
                return None

            if angle is not None:
                pre_landing_angles.append(angle)

        if not pre_landing_angles:
            return None

        pre_landing_angle = np.mean(pre_landing_angles)

        # Find first frame where angle decreases by >5°
        for i in range(landing_frame, nadir_frame):
            if joint_type == 'ankle':
                angle = self._calculate_ankle_angle(landmarks_data[i]['landmarks'], 'left')
            elif joint_type == 'knee':
                angle = self._calculate_knee_angle(landmarks_data[i]['landmarks'], 'left')
            elif joint_type == 'hip':
                angle = self._calculate_hip_angle(landmarks_data[i]['landmarks'], 'left')
            else:
                return None

            if angle is not None and (pre_landing_angle - angle) > 5:
                return i

        return None

    # ============================================================================
    # Helper Functions - Joint Angle Calculations
    # ============================================================================

    def _calculate_knee_angle(self, landmarks: List[Dict], side: str) -> Optional[float]:
        """
        What: Calculate knee angle using 3D vectors
        Why: HIP→KNEE→ANKLE angle
        """
        if side == 'left':
            hip = landmarks[self.LEFT_HIP]
            knee = landmarks[self.LEFT_KNEE]
            ankle = landmarks[self.LEFT_ANKLE]
        else:
            hip = landmarks[self.RIGHT_HIP]
            knee = landmarks[self.RIGHT_KNEE]
            ankle = landmarks[self.RIGHT_ANKLE]

        vec1 = np.array([hip['x'] - knee['x'], hip['y'] - knee['y'], hip['z'] - knee['z']])
        vec2 = np.array([ankle['x'] - knee['x'], ankle['y'] - knee['y'], ankle['z'] - knee['z']])

        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return None

        cos_angle = np.dot(vec1, vec2) / (norm1 * norm2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.arccos(cos_angle) * 180.0 / np.pi

        return float(angle)

    def _calculate_hip_angle(self, landmarks: List[Dict], side: str) -> Optional[float]:
        """
        What: Calculate hip angle using 3D vectors
        Why: SHOULDER→HIP→KNEE angle
        """
        if side == 'left':
            shoulder = landmarks[self.LEFT_SHOULDER]
            hip = landmarks[self.LEFT_HIP]
            knee = landmarks[self.LEFT_KNEE]
        else:
            shoulder = landmarks[self.RIGHT_SHOULDER]
            hip = landmarks[self.RIGHT_HIP]
            knee = landmarks[self.RIGHT_KNEE]

        vec1 = np.array([shoulder['x'] - hip['x'], shoulder['y'] - hip['y'], shoulder['z'] - hip['z']])
        vec2 = np.array([knee['x'] - hip['x'], knee['y'] - hip['y'], knee['z'] - hip['z']])

        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return None

        cos_angle = np.dot(vec1, vec2) / (norm1 * norm2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.arccos(cos_angle) * 180.0 / np.pi

        return float(angle)

    def _calculate_ankle_angle(self, landmarks: List[Dict], side: str) -> Optional[float]:
        """
        What: Calculate ankle angle using 3D vectors
        Why: KNEE→ANKLE→FOOT_INDEX angle
        """
        if side == 'left':
            knee = landmarks[self.LEFT_KNEE]
            ankle = landmarks[self.LEFT_ANKLE]
            foot = landmarks[self.LEFT_FOOT_INDEX]
        else:
            knee = landmarks[self.RIGHT_KNEE]
            ankle = landmarks[self.RIGHT_ANKLE]
            foot = landmarks[self.RIGHT_FOOT_INDEX]

        vec1 = np.array([knee['x'] - ankle['x'], knee['y'] - ankle['y'], knee['z'] - ankle['z']])
        vec2 = np.array([foot['x'] - ankle['x'], foot['y'] - ankle['y'], foot['z'] - ankle['z']])

        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return None

        cos_angle = np.dot(vec1, vec2) / (norm1 * norm2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.arccos(cos_angle) * 180.0 / np.pi

        return float(angle)
