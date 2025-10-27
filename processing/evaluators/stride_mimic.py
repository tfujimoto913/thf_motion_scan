"""
Purpose: Stride Mimic (T03) evaluator for 2-axis evaluation system
Responsibility:
    - A. Execution evaluation (3 points): Movement range + Bilateral symmetry
    - B. Principles evaluation (9 points): P3 Support base + P2 Center of mass + P4 Joint angles
Dependencies: numpy, config.json (T03_stride_mimic thresholds)
Created: 2025-10-25 by Claude Code
Decision Log: ADR-010 (2-axis evaluation system)

CRITICAL: All metrics are objective only - angles (degrees), distances (normalized ratios),
         time (frames), standard deviation. NO subjective metrics allowed.
"""

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np


class StrideMinicryEvaluator:
    """
    What: Evaluates Stride Mimic movement (skating stride simulation)
    Why: Assesses dynamic balance, support base control, and bilateral symmetry during skating motion
    Design Decision: 2-axis evaluation (A: Execution 3pts, B: Principles 9pts) - ADR-010

    CRITICAL: MediaPipe Pose 33-landmark system required
    """

    # PHASE CORE LOGIC: MediaPipe Pose landmark indices (0-32)
    # CRITICAL: Do not modify without updating all dependent calculations
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
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

        # CRITICAL: All thresholds from config.json T03_stride_mimic section
        self.thresholds = config['thresholds']['T03_stride_mimic']
        self.config = config

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float, leg_length: float) -> Dict:
        """
        What: Main evaluation entry point - returns 12-point structure
        Why: Combines execution (A: 3pts) and principles (B: 9pts) scores
        Design Decision: 2-axis evaluation system - ADR-010

        Args:
            landmarks_data: List of frame data with MediaPipe landmarks
            base_width: Normalization factor (max of shoulder/pelvis width)
            shoulder_width: Distance between landmarks 11-12

        Returns:
            {
                'test_id': 'T03_stride_mimic',
                'execution': {..., 'total': 0-3},
                'principles': {..., 'total': 0-9},
                'total': 0-12,
                'max_score': 12.0
            }

        CRITICAL: Total score = execution + principles (max 12.0)
        """
        if not landmarks_data or base_width <= 0 or shoulder_width <= 0:
            return {
                'test_id': 'T03_stride_mimic',
                'execution': {'total': 0.0, 'details': 'Invalid input data'},
                'principles': {'total': 0.0, 'details': 'Invalid input data'},
                'total': 0.0,
                'max_score': 12.0,
                'error': 'Invalid input: empty landmarks or invalid normalization factors'
            }

        execution = self.evaluate_execution(landmarks_data, shoulder_width)
        principles = self.evaluate_principles(landmarks_data, base_width, shoulder_width)

        return {
            'test_id': 'T03_stride_mimic',
            'execution': execution,
            'principles': principles,
            'total': execution['total'] + principles['total'],
            'max_score': 12.0
        }

    def evaluate_execution(self, landmarks_data: List[Dict],
                           shoulder_width: float) -> Dict:
        """
        What: A. Execution evaluation (3 points total)
        Why: Objective metrics for movement quality and bilateral balance
        Design Decision: Split into A1 (movement range 1.5pts) + A2 (symmetry 1.5pts)

        Returns:
            {
                'A1_movement_range': {'score': 0-1.5, 'knee_flexion': {...}, 'hip_abduction': {...}},
                'A2_bilateral_symmetry': {'score': 0-1.5, 'knee_angle_diff': {...}, 'hip_abduction_diff': {...}},
                'total': 0-3.0
            }

        CRITICAL: All metrics are objective - angles in degrees, distances as ratios
        """
        a1_movement_range = self._score_movement_range(landmarks_data, shoulder_width)
        a2_bilateral_symmetry = self._score_bilateral_symmetry(landmarks_data, shoulder_width)

        return {
            'A1_movement_range': a1_movement_range,
            'A2_bilateral_symmetry': a2_bilateral_symmetry,
            'total': a1_movement_range['score'] + a2_bilateral_symmetry['score']
        }

    def evaluate_principles(self, landmarks_data: List[Dict], base_width: float,
                           shoulder_width: float) -> Dict:
        """
        What: B. Principles evaluation (9 points total)
        Why: Assesses adherence to 3 movement principles (3 points each)
        Design Decision: P3 (support base) + P2 (center of mass) + P4 (joint angles)

        Returns:
            {
                'P3_support_base': {'score': 0-3.0, ...},
                'P2_center_of_mass': {'score': 0-3.0, ...},
                'P4_joint_angles': {'score': 0-3.0, ...},
                'total': 0-9.0
            }

        CRITICAL: Deduction-based scoring - start at 3.0, deduct for violations
        """
        p3_support_base = self._evaluate_principle_3(landmarks_data, base_width, shoulder_width)
        p2_center_of_mass = self._evaluate_principle_2(landmarks_data, base_width, shoulder_width)
        p4_joint_angles = self._evaluate_principle_4(landmarks_data, base_width, shoulder_width)

        return {
            'P3_support_base': p3_support_base,
            'P2_center_of_mass': p2_center_of_mass,
            'P4_joint_angles': p4_joint_angles,
            'total': p3_support_base['score'] + p2_center_of_mass['score'] + p4_joint_angles['score']
        }

    # ============================================================================
    # A. Execution Scoring Methods
    # ============================================================================

    def _score_movement_range(self, landmarks_data: List[Dict],
                              shoulder_width: float) -> Dict:
        """
        What: A1. Movement range scoring (1.5 points)
        Why: Assesses support leg knee flexion and hip abduction width
        Design Decision: 0.75pt knee flexion + 0.75pt hip abduction

        Thresholds (config.json):
            - Knee flexion: 60-90° excellent (0.75), 90-110° good (0.5), else fair (0.25)
            - Hip abduction: ≥1.2× shoulder_width excellent (0.75), ≥1.0× good (0.5), else fair (0.25)

        CRITICAL: MediaPipe landmarks - KNEE (25/26), HIP (23/24) for calculations
        """
        thresholds = self.thresholds['execution']['movement_range']

        # Phase detection: Identify left and right support phases
        support_phases = self._detect_support_phases(landmarks_data)

        # Calculate knee flexion angles during support phases
        knee_angles_left = []
        knee_angles_right = []

        for phase in support_phases:
            if phase['side'] == 'left':
                for frame_idx in range(phase['start'], phase['end']):
                    if frame_idx < len(landmarks_data):
                        angle = self._calculate_knee_angle(
                            landmarks_data[frame_idx]['landmarks'],
                            'left'
                        )
                        if angle is not None:
                            knee_angles_left.append(angle)
            elif phase['side'] == 'right':
                for frame_idx in range(phase['start'], phase['end']):
                    if frame_idx < len(landmarks_data):
                        angle = self._calculate_knee_angle(
                            landmarks_data[frame_idx]['landmarks'],
                            'right'
                        )
                        if angle is not None:
                            knee_angles_right.append(angle)

        # Use minimum knee angle (maximum flexion) across all support phases
        all_knee_angles = knee_angles_left + knee_angles_right
        min_knee_angle = min(all_knee_angles) if all_knee_angles else 180.0

        # Score knee flexion
        knee_thresholds = thresholds['knee_flexion']
        if knee_thresholds['excellent_min'] <= min_knee_angle <= knee_thresholds['excellent_max']:
            knee_score = 0.75
            knee_grade = 'excellent'
        elif knee_thresholds['good_min'] <= min_knee_angle <= knee_thresholds['good_max']:
            knee_score = 0.5
            knee_grade = 'good'
        else:
            knee_score = 0.25
            knee_grade = 'fair'

        # Calculate hip abduction width (max left-right hip X-distance)
        hip_abduction_width = self._calculate_hip_abduction_width(landmarks_data)
        hip_abduction_ratio = hip_abduction_width / shoulder_width if shoulder_width > 0 else 0.0

        # Score hip abduction
        abduction_thresholds = thresholds['hip_abduction']
        if hip_abduction_ratio >= abduction_thresholds['excellent']:
            abduction_score = 0.75
            abduction_grade = 'excellent'
        elif hip_abduction_ratio >= abduction_thresholds['good']:
            abduction_score = 0.5
            abduction_grade = 'good'
        else:
            abduction_score = 0.25
            abduction_grade = 'fair'

        total_score = knee_score + abduction_score

        return {
            'score': total_score,
            'max_score': 1.5,
            'knee_flexion': {
                'value': float(min_knee_angle),
                'score': knee_score,
                'grade': knee_grade,
                'unit': 'degrees'
            },
            'hip_abduction': {
                'value': float(hip_abduction_ratio),
                'score': abduction_score,
                'grade': abduction_grade,
                'unit': 'ratio_to_shoulder_width'
            }
        }

    def _score_bilateral_symmetry(self, landmarks_data: List[Dict],
                                   shoulder_width: float) -> Dict:
        """
        What: A2. Bilateral symmetry scoring (1.5 points)
        Why: Assesses left-right balance in knee angles and hip abduction
        Design Decision: 0.75pt knee angle symmetry + 0.75pt hip abduction symmetry

        Thresholds (config.json):
            - Knee angle diff: <10° excellent (0.75), <20° good (0.5), else fair (0.25)
            - Hip abduction diff: <0.15 ratio excellent (0.75), <0.30 good (0.5), else fair (0.25)

        CRITICAL: Compare maximum flexion angles and abduction widths between sides
        """
        thresholds = self.thresholds['execution']['bilateral_symmetry']

        # Detect support phases for each side
        support_phases = self._detect_support_phases(landmarks_data)

        # Calculate representative knee angles for each side
        knee_angles_left = []
        knee_angles_right = []

        for phase in support_phases:
            if phase['side'] == 'left':
                for frame_idx in range(phase['start'], phase['end']):
                    if frame_idx < len(landmarks_data):
                        angle = self._calculate_knee_angle(
                            landmarks_data[frame_idx]['landmarks'],
                            'left'
                        )
                        if angle is not None:
                            knee_angles_left.append(angle)
            elif phase['side'] == 'right':
                for frame_idx in range(phase['start'], phase['end']):
                    if frame_idx < len(landmarks_data):
                        angle = self._calculate_knee_angle(
                            landmarks_data[frame_idx]['landmarks'],
                            'right'
                        )
                        if angle is not None:
                            knee_angles_right.append(angle)

        # Use minimum angles (maximum flexion)
        min_left_angle = min(knee_angles_left) if knee_angles_left else 180.0
        min_right_angle = min(knee_angles_right) if knee_angles_right else 180.0
        knee_angle_diff = abs(min_left_angle - min_right_angle)

        # Score knee angle symmetry
        knee_threshold = thresholds['knee_angle']
        if knee_angle_diff < knee_threshold['excellent']:
            knee_score = 0.75
            knee_grade = 'excellent'
        elif knee_angle_diff < knee_threshold['good']:
            knee_score = 0.5
            knee_grade = 'good'
        else:
            knee_score = 0.25
            knee_grade = 'fair'

        # Calculate hip abduction widths for each side
        hip_abduction_left = []
        hip_abduction_right = []

        for phase in support_phases:
            if phase['side'] == 'left':
                phase_data = landmarks_data[phase['start']:phase['end']]
                width = self._calculate_hip_abduction_width(phase_data)
                hip_abduction_left.append(width)
            elif phase['side'] == 'right':
                phase_data = landmarks_data[phase['start']:phase['end']]
                width = self._calculate_hip_abduction_width(phase_data)
                hip_abduction_right.append(width)

        max_left_abduction = max(hip_abduction_left) if hip_abduction_left else 0.0
        max_right_abduction = max(hip_abduction_right) if hip_abduction_right else 0.0

        # Calculate relative difference
        avg_abduction = (max_left_abduction + max_right_abduction) / 2
        abduction_diff_ratio = abs(max_left_abduction - max_right_abduction) / avg_abduction if avg_abduction > 0 else 0.0

        # Score hip abduction symmetry
        abduction_threshold = thresholds['hip_abduction']
        if abduction_diff_ratio < abduction_threshold['excellent']:
            abduction_score = 0.75
            abduction_grade = 'excellent'
        elif abduction_diff_ratio < abduction_threshold['good']:
            abduction_score = 0.5
            abduction_grade = 'good'
        else:
            abduction_score = 0.25
            abduction_grade = 'fair'

        total_score = knee_score + abduction_score

        return {
            'score': total_score,
            'max_score': 1.5,
            'knee_angle_diff': {
                'value': float(knee_angle_diff),
                'score': knee_score,
                'grade': knee_grade,
                'unit': 'degrees',
                'left_angle': float(min_left_angle),
                'right_angle': float(min_right_angle)
            },
            'hip_abduction_diff': {
                'value': float(abduction_diff_ratio),
                'score': abduction_score,
                'grade': abduction_grade,
                'unit': 'ratio',
                'left_width': float(max_left_abduction),
                'right_width': float(max_right_abduction)
            }
        }

    # ============================================================================
    # B. Principles Evaluation Methods
    # ============================================================================

    def _evaluate_principle_3(self, landmarks_data: List[Dict], base_width: float,
                              shoulder_width: float) -> Dict:
        """
        What: P3. Support base evaluation (3 points)
        Why: Assesses ankle stability, kick leg abduction, and support time symmetry
        Design Decision: Deduction-based - 1pt per sub-metric

        Sub-metrics:
            - Ankle stability: Std dev of ankle angle during support phase
            - Kick leg hip abduction: Hip abduction angle of non-support leg
            - Support time symmetry: Left-right support time difference ratio

        Thresholds (config.json):
            - Ankle stability: <5° excellent (1.0), <10° good (0.5), else poor (0.0)
            - Kick leg abduction: 30-50° excellent (1.0), 20-60° good (0.5), else poor (0.0)
            - Support time symmetry: <0.15 ratio excellent (1.0), <0.30 good (0.5), else poor (0.0)

        CRITICAL: MediaPipe landmarks - ANKLE (27/28), FOOT_INDEX (31/32), HEEL (29/30)
        """
        thresholds = self.thresholds['principles']['P3_support_base']

        support_phases = self._detect_support_phases(landmarks_data)

        # 1. Ankle stability during support phases
        ankle_stabilities = []
        for phase in support_phases:
            phase_data = landmarks_data[phase['start']:phase['end']]
            stability = self._calculate_ankle_stability(phase_data, phase['side'])
            if stability is not None:
                ankle_stabilities.append(stability)

        avg_ankle_stability = np.mean(ankle_stabilities) if ankle_stabilities else 180.0

        stability_threshold = thresholds['ankle_stability']
        if avg_ankle_stability < stability_threshold['excellent']:
            ankle_score = 1.0
            ankle_grade = 'excellent'
        elif avg_ankle_stability < stability_threshold['good']:
            ankle_score = 0.5
            ankle_grade = 'good'
        else:
            ankle_score = 0.0
            ankle_grade = 'poor'

        # 2. Kick leg hip abduction angles
        kick_leg_abductions = []
        for phase in support_phases:
            phase_data = landmarks_data[phase['start']:phase['end']]
            # Kick leg is opposite of support leg
            kick_side = 'right' if phase['side'] == 'left' else 'left'
            abduction = self._calculate_kick_leg_abduction(phase_data, kick_side)
            if abduction is not None:
                kick_leg_abductions.append(abduction)

        avg_kick_abduction = np.mean(kick_leg_abductions) if kick_leg_abductions else 0.0

        kick_threshold = thresholds['kick_leg_abduction']
        if kick_threshold['excellent_min'] <= avg_kick_abduction <= kick_threshold['excellent_max']:
            kick_score = 1.0
            kick_grade = 'excellent'
        elif kick_threshold['good_min'] <= avg_kick_abduction <= kick_threshold['good_max']:
            kick_score = 0.5
            kick_grade = 'good'
        else:
            kick_score = 0.0
            kick_grade = 'poor'

        # 3. Support time symmetry
        left_support_time = sum(p['end'] - p['start'] for p in support_phases if p['side'] == 'left')
        right_support_time = sum(p['end'] - p['start'] for p in support_phases if p['side'] == 'right')

        total_support_time = left_support_time + right_support_time
        time_diff_ratio = abs(left_support_time - right_support_time) / total_support_time if total_support_time > 0 else 0.0

        time_threshold = thresholds['support_time_symmetry']
        if time_diff_ratio < time_threshold['excellent']:
            time_score = 1.0
            time_grade = 'excellent'
        elif time_diff_ratio < time_threshold['good']:
            time_score = 0.5
            time_grade = 'good'
        else:
            time_score = 0.0
            time_grade = 'poor'

        total_score = ankle_score + kick_score + time_score

        return {
            'score': total_score,
            'max_score': 3.0,
            'ankle_stability': {
                'value': float(avg_ankle_stability),
                'score': ankle_score,
                'grade': ankle_grade,
                'unit': 'degrees_std_dev'
            },
            'kick_leg_abduction': {
                'value': float(avg_kick_abduction),
                'score': kick_score,
                'grade': kick_grade,
                'unit': 'degrees'
            },
            'support_time_symmetry': {
                'value': float(time_diff_ratio),
                'score': time_score,
                'grade': time_grade,
                'unit': 'ratio',
                'left_frames': left_support_time,
                'right_frames': right_support_time
            }
        }

    def _evaluate_principle_2(self, landmarks_data: List[Dict], base_width: float,
                             shoulder_width: float) -> Dict:
        """
        What: P2. Center of mass evaluation (3 points)
        Why: Assesses COM height stability, forward movement, and projection offset
        Design Decision: Deduction-based - 1pt per sub-metric

        Sub-metrics:
            - Height stability: Std dev of COM height during support phase
            - Forward movement: COM horizontal movement per cycle
            - Projection offset: COM-ankle horizontal distance during support

        Thresholds (config.json):
            - Height stability: <0.1 ratio excellent (1.0), <0.2 good (0.5), else poor (0.0)
            - Forward movement: ≥2.0× shoulder_width excellent (1.0), ≥1.5× good (0.5), else poor (0.0)
            - Projection offset: <0.3 ratio excellent (1.0), <0.5 good (0.5), else poor (0.0)

        CRITICAL: COM calculated as midpoint of left_HIP and right_HIP
        """
        thresholds = self.thresholds['principles']['P2_center_of_mass']

        support_phases = self._detect_support_phases(landmarks_data)

        # 1. COM height stability during support phases
        com_height_variations = []
        for phase in support_phases:
            phase_data = landmarks_data[phase['start']:phase['end']]
            variation = self._calculate_com_height_variation(phase_data, base_width)
            if variation is not None:
                com_height_variations.append(variation)

        avg_height_variation = np.mean(com_height_variations) if com_height_variations else 1.0

        height_threshold = thresholds['height_stability']
        if avg_height_variation < height_threshold['excellent']:
            height_score = 1.0
            height_grade = 'excellent'
        elif avg_height_variation < height_threshold['good']:
            height_score = 0.5
            height_grade = 'good'
        else:
            height_score = 0.0
            height_grade = 'poor'

        # 2. Forward movement per cycle
        forward_movement = self._calculate_forward_movement(landmarks_data, support_phases)
        forward_movement_ratio = forward_movement / shoulder_width if shoulder_width > 0 else 0.0

        movement_threshold = thresholds['forward_movement']
        if forward_movement_ratio >= movement_threshold['excellent']:
            movement_score = 1.0
            movement_grade = 'excellent'
        elif forward_movement_ratio >= movement_threshold['good']:
            movement_score = 0.5
            movement_grade = 'good'
        else:
            movement_score = 0.0
            movement_grade = 'poor'

        # 3. COM-ankle projection offset during support
        projection_offsets = []
        for phase in support_phases:
            phase_data = landmarks_data[phase['start']:phase['end']]
            offset = self._calculate_projection_offset(phase_data, phase['side'], base_width)
            if offset is not None:
                projection_offsets.append(offset)

        avg_projection_offset = np.mean(projection_offsets) if projection_offsets else 1.0

        projection_threshold = thresholds['projection_offset']
        if avg_projection_offset < projection_threshold['excellent']:
            projection_score = 1.0
            projection_grade = 'excellent'
        elif avg_projection_offset < projection_threshold['good']:
            projection_score = 0.5
            projection_grade = 'good'
        else:
            projection_score = 0.0
            projection_grade = 'poor'

        total_score = height_score + movement_score + projection_score

        return {
            'score': total_score,
            'max_score': 3.0,
            'height_stability': {
                'value': float(avg_height_variation),
                'score': height_score,
                'grade': height_grade,
                'unit': 'ratio_to_base_width'
            },
            'forward_movement': {
                'value': float(forward_movement_ratio),
                'score': movement_score,
                'grade': movement_grade,
                'unit': 'ratio_to_shoulder_width'
            },
            'projection_offset': {
                'value': float(avg_projection_offset),
                'score': projection_score,
                'grade': projection_grade,
                'unit': 'ratio_to_base_width'
            }
        }

    def _evaluate_principle_4(self, landmarks_data: List[Dict], base_width: float,
                             shoulder_width: float) -> Dict:
        """
        What: P4. Joint angles evaluation (3 points)
        Why: Assesses support knee angle, hip extension, and trunk lean
        Design Decision: Deduction-based - 1pt per sub-metric

        Sub-metrics:
            - Support knee: Knee angle during support phase
            - Hip extension: Hip extension angle at kick-off completion
            - Trunk lean: Trunk forward lean angle

        Thresholds (config.json):
            - Support knee: 70-100° excellent (1.0), 60-120° good (0.5), else poor (0.0)
            - Hip extension: ≥20° excellent (1.0), ≥10° good (0.5), else poor (0.0)
            - Trunk lean: 10-25° excellent (1.0), 5-35° good (0.5), else poor (0.0)

        CRITICAL: MediaPipe landmarks - SHOULDER (11/12), HIP (23/24), KNEE (25/26), ANKLE (27/28)
        """
        thresholds = self.thresholds['principles']['P4_joint_angles']

        support_phases = self._detect_support_phases(landmarks_data)

        # 1. Support knee angles during support phases
        support_knee_angles = []
        for phase in support_phases:
            for frame_idx in range(phase['start'], phase['end']):
                if frame_idx < len(landmarks_data):
                    angle = self._calculate_knee_angle(
                        landmarks_data[frame_idx]['landmarks'],
                        phase['side']
                    )
                    if angle is not None:
                        support_knee_angles.append(angle)

        avg_support_knee = np.mean(support_knee_angles) if support_knee_angles else 180.0

        knee_threshold = thresholds['support_knee']
        if knee_threshold['excellent_min'] <= avg_support_knee <= knee_threshold['excellent_max']:
            knee_score = 1.0
            knee_grade = 'excellent'
        elif knee_threshold['good_min'] <= avg_support_knee <= knee_threshold['good_max']:
            knee_score = 0.5
            knee_grade = 'good'
        else:
            knee_score = 0.0
            knee_grade = 'poor'

        # 2. Hip extension at kick-off completion (transition between phases)
        hip_extensions = []
        for i in range(len(support_phases) - 1):
            current_phase = support_phases[i]
            # Kick-off completion is at end of support phase
            frame_idx = current_phase['end'] - 1
            if 0 <= frame_idx < len(landmarks_data):
                extension = self._calculate_hip_extension(
                    landmarks_data[frame_idx]['landmarks'],
                    current_phase['side']
                )
                if extension is not None:
                    hip_extensions.append(extension)

        max_hip_extension = max(hip_extensions) if hip_extensions else 0.0

        extension_threshold = thresholds['hip_extension']
        if max_hip_extension >= extension_threshold['excellent']:
            extension_score = 1.0
            extension_grade = 'excellent'
        elif max_hip_extension >= extension_threshold['good']:
            extension_score = 0.5
            extension_grade = 'good'
        else:
            extension_score = 0.0
            extension_grade = 'poor'

        # 3. Trunk lean throughout movement
        trunk_leans = []
        for frame_data in landmarks_data:
            lean = self._calculate_trunk_lean(frame_data['landmarks'])
            if lean is not None:
                trunk_leans.append(lean)

        avg_trunk_lean = np.mean(trunk_leans) if trunk_leans else 0.0

        lean_threshold = thresholds['trunk_lean']
        if lean_threshold['excellent_min'] <= avg_trunk_lean <= lean_threshold['excellent_max']:
            lean_score = 1.0
            lean_grade = 'excellent'
        elif lean_threshold['good_min'] <= avg_trunk_lean <= lean_threshold['good_max']:
            lean_score = 0.5
            lean_grade = 'good'
        else:
            lean_score = 0.0
            lean_grade = 'poor'

        total_score = knee_score + extension_score + lean_score

        return {
            'score': total_score,
            'max_score': 3.0,
            'support_knee': {
                'value': float(avg_support_knee),
                'score': knee_score,
                'grade': knee_grade,
                'unit': 'degrees'
            },
            'hip_extension': {
                'value': float(max_hip_extension),
                'score': extension_score,
                'grade': extension_grade,
                'unit': 'degrees'
            },
            'trunk_lean': {
                'value': float(avg_trunk_lean),
                'score': lean_score,
                'grade': lean_grade,
                'unit': 'degrees'
            }
        }

    # ============================================================================
    # Helper Functions
    # ============================================================================

    def _detect_support_phases(self, landmarks_data: List[Dict]) -> List[Dict]:
        """
        What: Detect left and right support phases using knee Y-coordinates
        Why: Support phase = when support leg KNEE.y > opposite leg KNEE.y
        Design Decision: State machine with minimum phase duration (5 frames)

        Returns:
            [{'side': 'left'|'right', 'start': int, 'end': int}, ...]

        CRITICAL: MediaPipe Y-coordinate increases downward (higher value = lower position)
        """
        phases = []
        current_phase = None
        min_phase_duration = 5  # Minimum frames to consider a valid phase

        for frame_idx, frame_data in enumerate(landmarks_data):
            landmarks = frame_data['landmarks']

            left_knee = landmarks[self.LEFT_KNEE]
            right_knee = landmarks[self.RIGHT_KNEE]

            # Support leg has HIGHER Y value (lower position)
            if left_knee['y'] > right_knee['y']:
                support_side = 'left'
            else:
                support_side = 'right'

            if current_phase is None:
                # Start new phase
                current_phase = {
                    'side': support_side,
                    'start': frame_idx,
                    'end': frame_idx + 1
                }
            elif current_phase['side'] == support_side:
                # Continue current phase
                current_phase['end'] = frame_idx + 1
            else:
                # Phase transition
                if current_phase['end'] - current_phase['start'] >= min_phase_duration:
                    phases.append(current_phase)
                current_phase = {
                    'side': support_side,
                    'start': frame_idx,
                    'end': frame_idx + 1
                }

        # Add last phase
        if current_phase and current_phase['end'] - current_phase['start'] >= min_phase_duration:
            phases.append(current_phase)

        return phases

    def _calculate_knee_angle(self, landmarks: List[Dict], side: str) -> Optional[float]:
        """
        What: Calculate knee flexion angle using 3D vectors
        Why: Angle between HIP→KNEE and KNEE→ANKLE vectors
        Design Decision: 3D dot product method (ADR-010)

        Args:
            landmarks: Single frame MediaPipe landmarks
            side: 'left' or 'right'

        Returns:
            Angle in degrees (0-180), or None if calculation fails

        CRITICAL: Uses HIP (23/24), KNEE (25/26), ANKLE (27/28) landmarks
        """
        if side == 'left':
            hip = landmarks[self.LEFT_HIP]
            knee = landmarks[self.LEFT_KNEE]
            ankle = landmarks[self.LEFT_ANKLE]
        else:
            hip = landmarks[self.RIGHT_HIP]
            knee = landmarks[self.RIGHT_KNEE]
            ankle = landmarks[self.RIGHT_ANKLE]

        # Vector from knee to hip
        vec1 = np.array([
            hip['x'] - knee['x'],
            hip['y'] - knee['y'],
            hip['z'] - knee['z']
        ])

        # Vector from knee to ankle
        vec2 = np.array([
            ankle['x'] - knee['x'],
            ankle['y'] - knee['y'],
            ankle['z'] - knee['z']
        ])

        # Calculate angle using dot product
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return None

        cos_angle = np.dot(vec1, vec2) / (norm1 * norm2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.arccos(cos_angle) * 180.0 / np.pi

        return float(angle)

    def _calculate_hip_abduction_width(self, landmarks_data: List[Dict]) -> float:
        """
        What: Calculate maximum left-right hip X-distance
        Why: Measures lateral stride width during movement
        Design Decision: Use max distance across all frames

        Returns:
            Maximum hip X-distance (normalized units)

        CRITICAL: MediaPipe X-coordinate for lateral distance
        """
        max_width = 0.0

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            left_hip = landmarks[self.LEFT_HIP]
            right_hip = landmarks[self.RIGHT_HIP]

            width = abs(right_hip['x'] - left_hip['x'])
            max_width = max(max_width, width)

        return float(max_width)

    def _calculate_ankle_stability(self, landmarks_data: List[Dict], side: str) -> Optional[float]:
        """
        What: Calculate ankle angle standard deviation during support phase
        Why: Measures ankle stability (low std dev = stable)
        Design Decision: Ankle angle = KNEE→ANKLE→FOOT_INDEX angle

        Args:
            landmarks_data: Phase-specific frames
            side: 'left' or 'right'

        Returns:
            Standard deviation in degrees, or None if insufficient data

        CRITICAL: MediaPipe landmarks - KNEE (25/26), ANKLE (27/28), FOOT_INDEX (31/32)
        """
        ankle_angles = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']

            if side == 'left':
                knee = landmarks[self.LEFT_KNEE]
                ankle = landmarks[self.LEFT_ANKLE]
                foot = landmarks[self.LEFT_FOOT_INDEX]
            else:
                knee = landmarks[self.RIGHT_KNEE]
                ankle = landmarks[self.RIGHT_ANKLE]
                foot = landmarks[self.RIGHT_FOOT_INDEX]

            # Vector from ankle to knee
            vec1 = np.array([
                knee['x'] - ankle['x'],
                knee['y'] - ankle['y'],
                knee['z'] - ankle['z']
            ])

            # Vector from ankle to foot index
            vec2 = np.array([
                foot['x'] - ankle['x'],
                foot['y'] - ankle['y'],
                foot['z'] - ankle['z']
            ])

            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 > 0 and norm2 > 0:
                cos_angle = np.dot(vec1, vec2) / (norm1 * norm2)
                cos_angle = np.clip(cos_angle, -1.0, 1.0)
                angle = np.arccos(cos_angle) * 180.0 / np.pi
                ankle_angles.append(angle)

        if len(ankle_angles) < 2:
            return None

        return float(np.std(ankle_angles))

    def _calculate_kick_leg_abduction(self, landmarks_data: List[Dict],
                                      kick_side: str) -> Optional[float]:
        """
        What: Calculate kick leg hip abduction angle
        Why: Measures lateral leg lift during kick phase
        Design Decision: Hip abduction angle using frontal plane projection

        Args:
            landmarks_data: Phase-specific frames
            kick_side: 'left' or 'right'

        Returns:
            Average abduction angle in degrees, or None if calculation fails

        CRITICAL: Angle between vertical and HIP→KNEE vector in frontal plane
        """
        abduction_angles = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']

            if kick_side == 'left':
                hip = landmarks[self.LEFT_HIP]
                knee = landmarks[self.LEFT_KNEE]
            else:
                hip = landmarks[self.RIGHT_HIP]
                knee = landmarks[self.RIGHT_KNEE]

            # Frontal plane projection (X-Y only, ignore Z)
            dx = knee['x'] - hip['x']
            dy = knee['y'] - hip['y']

            # Angle from vertical (Y-axis)
            angle = np.arctan2(abs(dx), abs(dy)) * 180.0 / np.pi
            abduction_angles.append(angle)

        if not abduction_angles:
            return None

        return float(np.mean(abduction_angles))

    def _calculate_com_height_variation(self, landmarks_data: List[Dict],
                                        base_width: float) -> Optional[float]:
        """
        What: Calculate COM height variation during phase
        Why: Measures vertical stability (low variation = stable)
        Design Decision: COM = midpoint of left_HIP and right_HIP

        Args:
            landmarks_data: Phase-specific frames
            base_width: Normalization factor

        Returns:
            Std dev of COM Y-coordinate normalized by base_width, or None

        CRITICAL: MediaPipe Y increases downward
        """
        com_heights = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']
            left_hip = landmarks[self.LEFT_HIP]
            right_hip = landmarks[self.RIGHT_HIP]

            com_y = (left_hip['y'] + right_hip['y']) / 2
            com_heights.append(com_y)

        if len(com_heights) < 2 or base_width <= 0:
            return None

        std_dev = np.std(com_heights)
        normalized_variation = std_dev / base_width

        return float(normalized_variation)

    def _calculate_forward_movement(self, landmarks_data: List[Dict],
                                    support_phases: List[Dict]) -> float:
        """
        What: Calculate COM horizontal movement per cycle
        Why: Measures forward propulsion effectiveness
        Design Decision: Use COM Z-coordinate (depth) movement between cycles

        Args:
            landmarks_data: All frame data
            support_phases: Detected support phases

        Returns:
            Average forward movement per cycle (normalized units)

        CRITICAL: MediaPipe Z-coordinate for forward/backward movement
        """
        if len(support_phases) < 2:
            return 0.0

        cycle_movements = []

        for i in range(len(support_phases) - 1):
            start_idx = support_phases[i]['start']
            end_idx = support_phases[i + 1]['start']

            if start_idx < len(landmarks_data) and end_idx < len(landmarks_data):
                start_frame = landmarks_data[start_idx]['landmarks']
                end_frame = landmarks_data[end_idx]['landmarks']

                start_com_z = (start_frame[self.LEFT_HIP]['z'] + start_frame[self.RIGHT_HIP]['z']) / 2
                end_com_z = (end_frame[self.LEFT_HIP]['z'] + end_frame[self.RIGHT_HIP]['z']) / 2

                movement = abs(end_com_z - start_com_z)
                cycle_movements.append(movement)

        if not cycle_movements:
            return 0.0

        return float(np.mean(cycle_movements))

    def _calculate_projection_offset(self, landmarks_data: List[Dict],
                                     support_side: str, base_width: float) -> Optional[float]:
        """
        What: Calculate COM-ankle horizontal distance during support
        Why: Measures balance control (COM should be over support foot)
        Design Decision: Use X-coordinate distance normalized by base_width

        Args:
            landmarks_data: Phase-specific frames
            support_side: 'left' or 'right'
            base_width: Normalization factor

        Returns:
            Average normalized offset, or None if calculation fails

        CRITICAL: MediaPipe X-coordinate for lateral offset
        """
        offsets = []

        for frame_data in landmarks_data:
            landmarks = frame_data['landmarks']

            left_hip = landmarks[self.LEFT_HIP]
            right_hip = landmarks[self.RIGHT_HIP]
            com_x = (left_hip['x'] + right_hip['x']) / 2

            if support_side == 'left':
                ankle = landmarks[self.LEFT_ANKLE]
            else:
                ankle = landmarks[self.RIGHT_ANKLE]

            offset = abs(com_x - ankle['x'])
            normalized_offset = offset / base_width if base_width > 0 else 0.0
            offsets.append(normalized_offset)

        if not offsets:
            return None

        return float(np.mean(offsets))

    def _calculate_hip_extension(self, landmarks: List[Dict], side: str) -> Optional[float]:
        """
        What: Calculate hip extension angle at kick-off
        Why: Measures hip extension power generation
        Design Decision: Angle between SHOULDER→HIP and HIP→KNEE vectors

        Args:
            landmarks: Single frame landmarks
            side: 'left' or 'right'

        Returns:
            Extension angle in degrees, or None if calculation fails

        CRITICAL: Extension = deviation from 180° (straight line)
        """
        if side == 'left':
            shoulder = landmarks[self.LEFT_SHOULDER]
            hip = landmarks[self.LEFT_HIP]
            knee = landmarks[self.LEFT_KNEE]
        else:
            shoulder = landmarks[self.RIGHT_SHOULDER]
            hip = landmarks[self.RIGHT_HIP]
            knee = landmarks[self.RIGHT_KNEE]

        # Vector from hip to shoulder
        vec1 = np.array([
            shoulder['x'] - hip['x'],
            shoulder['y'] - hip['y'],
            shoulder['z'] - hip['z']
        ])

        # Vector from hip to knee
        vec2 = np.array([
            knee['x'] - hip['x'],
            knee['y'] - hip['y'],
            knee['z'] - hip['z']
        ])

        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return None

        cos_angle = np.dot(vec1, vec2) / (norm1 * norm2)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.arccos(cos_angle) * 180.0 / np.pi

        # Extension = how much it deviates from 180° (straight)
        extension = 180.0 - angle

        return float(extension)

    def _calculate_trunk_lean(self, landmarks: List[Dict]) -> Optional[float]:
        """
        What: Calculate trunk forward lean angle
        Why: Measures body posture during movement
        Design Decision: Angle between vertical and shoulder→hip midpoint vector

        Args:
            landmarks: Single frame landmarks

        Returns:
            Lean angle in degrees from vertical, or None if calculation fails

        CRITICAL: Uses midpoints of shoulders and hips for trunk axis
        """
        left_shoulder = landmarks[self.LEFT_SHOULDER]
        right_shoulder = landmarks[self.RIGHT_SHOULDER]
        left_hip = landmarks[self.LEFT_HIP]
        right_hip = landmarks[self.RIGHT_HIP]

        # Calculate midpoints
        shoulder_mid_y = (left_shoulder['y'] + right_shoulder['y']) / 2
        shoulder_mid_z = (left_shoulder['z'] + right_shoulder['z']) / 2
        hip_mid_y = (left_hip['y'] + right_hip['y']) / 2
        hip_mid_z = (left_hip['z'] + right_hip['z']) / 2

        # Trunk vector (sagittal plane: Y-Z)
        dy = hip_mid_y - shoulder_mid_y
        dz = hip_mid_z - shoulder_mid_z

        # Angle from vertical (Y-axis)
        angle = np.arctan2(abs(dz), abs(dy)) * 180.0 / np.pi

        return float(angle)
