"""
Purpose: T05 Upper Body Swing evaluation using 2-axis system (A: 3pts, B: 9pts)
Responsibility: Evaluate trunk rotation, arm swing, and kinetic chain timing
Dependencies: numpy, config.json (T05_upper_body_swing thresholds)
Created: 2025-10-27 by Claude Code
Decision Log: ADR-010 (2-axis evaluation system)

CRITICAL: All metrics are objective - angles (degrees), distances (normalized), time (seconds)
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class UpperBodySwingEvaluator:
    """
    What: Evaluates Upper Body Swing test (T05) with 2-axis scoring
    Why: Measure trunk rotation quality, arm swing range, and kinetic chain timing
    Design Decision: A (3pts: execution) + B (9pts: principles) = 12 points total

    CRITICAL: All measurements use objective metrics only
    """

    # MediaPipe Pose landmark indices
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28

    def __init__(self, config_path: str = None):
        """
        What: Initialize evaluator with config thresholds
        Why: Load all thresholds from config.json (no hardcoding)
        Design Decision: Config-driven evaluation
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / 'config.json'

        with open(config_path, 'r') as f:
            self.config = json.load(f)

        self.thresholds = self.config['thresholds']['T05_upper_body_swing']

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float, leg_length: float,
                 body_height: float = None, fps: float = 30.0) -> Dict:
        """
        What: Main evaluation entry point returning 12-point structure
        Why: Orchestrate A + B evaluation and return complete results
        Design Decision: Follow same pattern as T01-T04

        Args:
            landmarks_data: List of frame data with MediaPipe landmarks
            base_width: Normalization factor (max of shoulder/pelvis width)
            shoulder_width: Shoulder width for normalization
            body_height: Body height for normalization (estimated if None)
            fps: Frame rate for timing calculations

        Returns:
            Dict with structure: {test_id, execution, principles, total, max_score}
        """
        # Input validation
        if not landmarks_data or len(landmarks_data) < 10:
            return {
                'test_id': 'T05_upper_body_swing',
                'error': 'Insufficient data',
                'execution': {'total': 0.0},
                'principles': {'total': 0.0},
                'total': 0.0,
                'max_score': 12.0
            }

        if base_width <= 0 or shoulder_width <= 0:
            return {
                'test_id': 'T05_upper_body_swing',
                'error': 'Invalid normalization factors',
                'execution': {'total': 0.0},
                'principles': {'total': 0.0},
                'total': 0.0,
                'max_score': 12.0
            }

        # Estimate body height if not provided
        if body_height is None or body_height <= 0:
            body_height = self._estimate_body_height(landmarks_data)

        # A. Execution evaluation (3 points)
        execution = self.evaluate_execution(
            landmarks_data, base_width, shoulder_width, body_height, fps
        )

        # B. Principles evaluation (9 points)
        principles = self.evaluate_principles(
            landmarks_data, base_width, shoulder_width, body_height, fps
        )

        return {
            'test_id': 'T05_upper_body_swing',
            'execution': execution,
            'principles': principles,
            'total': execution['total'] + principles['total'],
            'max_score': 12.0
        }

    def evaluate_execution(self, landmarks_data: List[Dict], base_width: float,
                          shoulder_width: float, body_height: float,
                          fps: float = 30.0) -> Dict:
        """
        What: A-axis evaluation (Execution/Completion) - 3 points
        Why: Measure objective execution quality
        Design Decision: A1 (trunk rotation) + A2 (arm swing) + A3 (symmetry)

        CRITICAL: A1 (1.0pt), A2 (1.0pt), A3 (1.0pt) = 3.0 points total
        """
        # A1: Trunk rotation range (1.0 point)
        a1_trunk_rotation = self._score_trunk_rotation_range(landmarks_data)

        # A2: Arm swing range (1.0 point)
        a2_arm_swing = self._score_arm_swing_range(landmarks_data, body_height)

        # A3: Left-right symmetry (1.0 point)
        a3_symmetry = self._score_left_right_symmetry(landmarks_data)

        return {
            'A1_trunk_rotation_range': a1_trunk_rotation,
            'A2_arm_swing_range': a2_arm_swing,
            'A3_left_right_symmetry': a3_symmetry,
            'total': (a1_trunk_rotation['score'] +
                     a2_arm_swing['score'] +
                     a3_symmetry['score'])
        }

    def evaluate_principles(self, landmarks_data: List[Dict], base_width: float,
                           shoulder_width: float, body_height: float,
                           fps: float = 30.0) -> Dict:
        """
        What: B-axis evaluation (Principles Achievement) - 9 points
        Why: Measure adherence to movement principles
        Design Decision: P7 (kinetic chain) + P4 (joint angles) + P6 (force direction)

        CRITICAL: P7 (3.0pts), P4 (3.0pts), P6 (3.0pts) = 9.0 points total
        """
        # P7: Kinetic chain (3.0 points) - hip→shoulder→elbow→wrist timing
        p7_kinetic_chain = self._evaluate_kinetic_chain(landmarks_data, fps)

        # P4: Joint angles (3.0 points) - shoulder ROM, elbow extension, trunk flexion
        p4_joint_angles = self._evaluate_joint_angles(landmarks_data)

        # P6: Force direction control (3.0 points) - wrist trajectory, COM stability
        p6_force_direction = self._evaluate_force_direction(
            landmarks_data, shoulder_width, body_height
        )

        return {
            'P7_kinetic_chain': p7_kinetic_chain,
            'P4_joint_angles': p4_joint_angles,
            'P6_force_direction': p6_force_direction,
            'total': (p7_kinetic_chain['score'] +
                     p4_joint_angles['score'] +
                     p6_force_direction['score'])
        }

    # ==================== A. Execution Scoring Methods ====================

    def _score_trunk_rotation_range(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: Score A1 - trunk rotation range (total left + right)
        Why: Measure ability to rotate trunk in both directions
        Design Decision: Calculate max rotation angles in each direction and sum

        Returns:
            Dict with score (0-1.0), max_score (1.0), value (degrees), grade
        """
        thresholds = self.thresholds['execution']['trunk_rotation_range']

        # Detect swing cycles and measure rotation
        cycles = self._detect_swing_cycles(landmarks_data)

        if not cycles:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'value': 0.0,
                'grade': 'poor',
                'details': 'No swing cycles detected'
            }

        # Calculate max rotation in each direction across all cycles
        max_right_rotation = 0.0  # Positive values
        max_left_rotation = 0.0   # Absolute value of negative

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            for frame in cycle_data:
                rotation_angle = self._calculate_trunk_rotation_angle(frame['landmarks'])

                if rotation_angle is not None:
                    if rotation_angle > 0:
                        max_right_rotation = max(max_right_rotation, rotation_angle)
                    else:
                        max_left_rotation = max(max_left_rotation, abs(rotation_angle))

        # Total rotation range (sum of both directions)
        total_rotation = max_right_rotation + max_left_rotation

        # Grade based on thresholds
        if total_rotation >= thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif total_rotation >= thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'max_score': 1.0,
            'value': round(total_rotation, 1),
            'grade': grade,
            'right_rotation': round(max_right_rotation, 1),
            'left_rotation': round(max_left_rotation, 1)
        }

    def _score_arm_swing_range(self, landmarks_data: List[Dict],
                               body_height: float) -> Dict:
        """
        What: Score A2 - arm swing range (normalized trajectory length)
        Why: Measure arm movement amplitude
        Design Decision: Calculate wrist trajectory length normalized by body_height

        Returns:
            Dict with score (0-1.0), max_score (1.0), value (ratio), grade
        """
        thresholds = self.thresholds['execution']['arm_swing_range']

        # Detect swing cycles
        cycles = self._detect_swing_cycles(landmarks_data)

        if not cycles:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'value': 0.0,
                'grade': 'poor',
                'details': 'No swing cycles detected'
            }

        # Calculate wrist trajectory length for each cycle
        trajectory_lengths = []

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            # Calculate average of left and right wrist trajectories
            left_length = self._calculate_wrist_trajectory_length(cycle_data, 'left')
            right_length = self._calculate_wrist_trajectory_length(cycle_data, 'right')

            if left_length is not None and right_length is not None:
                avg_length = (left_length + right_length) / 2
                trajectory_lengths.append(avg_length)

        if not trajectory_lengths:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'value': 0.0,
                'grade': 'poor',
                'details': 'Could not calculate trajectory'
            }

        # Use average trajectory length across cycles
        avg_trajectory = np.mean(trajectory_lengths)

        # Normalize by body height
        normalized_range = avg_trajectory / body_height if body_height > 0 else 0

        # Grade based on thresholds
        if normalized_range >= thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif normalized_range >= thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'max_score': 1.0,
            'value': round(normalized_range, 3),
            'grade': grade,
            'trajectory_length': round(avg_trajectory, 3)
        }

    def _score_left_right_symmetry(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: Score A3 - left-right rotation symmetry
        Why: Measure bilateral balance of trunk rotation
        Design Decision: Calculate ratio of rotation angle difference

        Returns:
            Dict with score (0-1.0), max_score (1.0), value (ratio), grade
        """
        thresholds = self.thresholds['execution']['left_right_symmetry']

        # Detect swing cycles
        cycles = self._detect_swing_cycles(landmarks_data)

        if not cycles:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'value': 0.0,
                'grade': 'poor',
                'details': 'No swing cycles detected'
            }

        # Calculate max rotation in each direction
        max_right_rotation = 0.0
        max_left_rotation = 0.0

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            for frame in cycle_data:
                rotation_angle = self._calculate_trunk_rotation_angle(frame['landmarks'])

                if rotation_angle is not None:
                    if rotation_angle > 0:
                        max_right_rotation = max(max_right_rotation, rotation_angle)
                    else:
                        max_left_rotation = max(max_left_rotation, abs(rotation_angle))

        # Calculate symmetry (ratio of difference to average)
        if max_right_rotation == 0 and max_left_rotation == 0:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'value': 0.0,
                'grade': 'poor',
                'details': 'No rotation detected'
            }

        avg_rotation = (max_right_rotation + max_left_rotation) / 2
        difference_ratio = abs(max_right_rotation - max_left_rotation) / avg_rotation if avg_rotation > 0 else 0

        # Grade based on thresholds (lower is better)
        if difference_ratio <= thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif difference_ratio <= thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'max_score': 1.0,
            'value': round(difference_ratio, 3),
            'grade': grade,
            'right_rotation': round(max_right_rotation, 1),
            'left_rotation': round(max_left_rotation, 1)
        }

    # ==================== B. Principles Evaluation Methods ====================

    def _evaluate_kinetic_chain(self, landmarks_data: List[Dict],
                                fps: float) -> Dict:
        """
        What: Evaluate P7 - kinetic chain timing (hip→shoulder→elbow→wrist)
        Why: Measure proximal-to-distal coordination
        Design Decision: 3 sub-metrics × 1 point each = 3 points

        CRITICAL: P7-1 (hip-shoulder), P7-2 (shoulder-elbow), P7-3 (elbow-wrist)
        """
        thresholds = self.thresholds['principles']['P7_kinetic_chain']

        # Detect swing cycles
        cycles = self._detect_swing_cycles(landmarks_data)

        if not cycles:
            return {
                'score': 0.0,
                'max_score': 3.0,
                'hip_shoulder_timing': {'score': 0.0, 'value': None},
                'shoulder_elbow_timing': {'score': 0.0, 'value': None},
                'elbow_wrist_timing': {'score': 0.0, 'value': None},
                'details': 'No swing cycles detected'
            }

        # P7-1: Hip-shoulder timing
        p71_result = self._evaluate_hip_shoulder_timing(landmarks_data, cycles, fps, thresholds)

        # P7-2: Shoulder-elbow timing
        p72_result = self._evaluate_shoulder_elbow_timing(landmarks_data, cycles, fps, thresholds)

        # P7-3: Elbow-wrist timing
        p73_result = self._evaluate_elbow_wrist_timing(landmarks_data, cycles, fps, thresholds)

        total_score = p71_result['score'] + p72_result['score'] + p73_result['score']

        return {
            'score': total_score,
            'max_score': 3.0,
            'hip_shoulder_timing': p71_result,
            'shoulder_elbow_timing': p72_result,
            'elbow_wrist_timing': p73_result
        }

    def _evaluate_joint_angles(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: Evaluate P4 - joint angles (shoulder ROM, elbow extension, trunk flexion)
        Why: Measure joint positioning quality
        Design Decision: 3 sub-metrics × 1 point each = 3 points

        CRITICAL: P4-1 (shoulder ROM), P4-2 (elbow extension), P4-3 (trunk flexion)
        """
        thresholds = self.thresholds['principles']['P4_joint_angles']

        # Detect swing cycles
        cycles = self._detect_swing_cycles(landmarks_data)

        if not cycles:
            return {
                'score': 0.0,
                'max_score': 3.0,
                'shoulder_rom': {'score': 0.0, 'value': None},
                'elbow_extension': {'score': 0.0, 'value': None},
                'trunk_lateral_flexion': {'score': 0.0, 'value': None},
                'details': 'No swing cycles detected'
            }

        # P4-1: Shoulder ROM (angle at swing maximum)
        p41_result = self._evaluate_shoulder_rom(landmarks_data, cycles, thresholds)

        # P4-2: Elbow extension (minimum elbow angle)
        p42_result = self._evaluate_elbow_extension(landmarks_data, cycles, thresholds)

        # P4-3: Trunk lateral flexion (maximum trunk lean)
        p43_result = self._evaluate_trunk_lateral_flexion(landmarks_data, cycles, thresholds)

        total_score = p41_result['score'] + p42_result['score'] + p43_result['score']

        return {
            'score': total_score,
            'max_score': 3.0,
            'shoulder_rom': p41_result,
            'elbow_extension': p42_result,
            'trunk_lateral_flexion': p43_result
        }

    def _evaluate_force_direction(self, landmarks_data: List[Dict],
                                  shoulder_width: float, body_height: float) -> Dict:
        """
        What: Evaluate P6 - force direction control
        Why: Measure trajectory control and stability
        Design Decision: 3 sub-metrics × 1 point each = 3 points

        CRITICAL: P6-1 (wrist horizontality), P6-2 (COM stability), P6-3 (reproducibility)
        """
        thresholds = self.thresholds['principles']['P6_force_direction']

        # Detect swing cycles
        cycles = self._detect_swing_cycles(landmarks_data)

        if not cycles:
            return {
                'score': 0.0,
                'max_score': 3.0,
                'wrist_horizontality': {'score': 0.0, 'value': None},
                'com_stability': {'score': 0.0, 'value': None},
                'trajectory_reproducibility': {'score': 0.0, 'value': None},
                'details': 'No swing cycles detected'
            }

        # P6-1: Wrist trajectory horizontality
        p61_result = self._evaluate_wrist_horizontality(landmarks_data, cycles, body_height, thresholds)

        # P6-2: COM stability during swing
        p62_result = self._evaluate_com_stability(landmarks_data, cycles, shoulder_width, thresholds)

        # P6-3: Trajectory reproducibility (cycle-to-cycle consistency)
        p63_result = self._evaluate_trajectory_reproducibility(landmarks_data, cycles, thresholds)

        total_score = p61_result['score'] + p62_result['score'] + p63_result['score']

        return {
            'score': total_score,
            'max_score': 3.0,
            'wrist_horizontality': p61_result,
            'com_stability': p62_result,
            'trajectory_reproducibility': p63_result
        }

    # ==================== Helper Methods: Phase Detection ====================

    def _detect_swing_cycles(self, landmarks_data: List[Dict]) -> List[Dict]:
        """
        What: Detect swing cycles using trunk rotation angle
        Why: Identify complete left-right swing repetitions
        Design Decision: Use zero-crossing of rotation angle to detect cycles

        Returns:
            List of cycles: [{'start': frame_idx, 'end': frame_idx, 'direction': 'right'/'left'}, ...]
        """
        # Calculate trunk rotation for all frames
        rotations = []
        for frame in landmarks_data:
            rotation = self._calculate_trunk_rotation_angle(frame['landmarks'])
            rotations.append(rotation if rotation is not None else 0.0)

        if not rotations:
            return []

        # Detect cycles using zero-crossing
        cycles = []
        current_cycle_start = 0
        previous_sign = np.sign(rotations[0]) if rotations[0] != 0 else 0

        MIN_CYCLE_DURATION = 10  # Minimum frames per cycle

        for i in range(1, len(rotations)):
            current_sign = np.sign(rotations[i]) if rotations[i] != 0 else previous_sign

            # Detect zero-crossing (sign change)
            if current_sign != previous_sign and previous_sign != 0:
                cycle_duration = i - current_cycle_start

                if cycle_duration >= MIN_CYCLE_DURATION:
                    direction = 'right' if previous_sign > 0 else 'left'
                    cycles.append({
                        'start': current_cycle_start,
                        'end': i,
                        'direction': direction
                    })
                    current_cycle_start = i

                previous_sign = current_sign

        # Add final cycle if long enough
        if len(rotations) - current_cycle_start >= MIN_CYCLE_DURATION:
            direction = 'right' if previous_sign > 0 else 'left'
            cycles.append({
                'start': current_cycle_start,
                'end': len(rotations),
                'direction': direction
            })

        return cycles

    def _calculate_trunk_rotation_angle(self, landmarks: List[Dict]) -> Optional[float]:
        """
        What: Calculate trunk rotation angle in horizontal plane
        Why: Measure rotation around vertical axis
        Design Decision: Use shoulder line projection on horizontal plane (x, z)

        Returns:
            Rotation angle in degrees (positive = right rotation, negative = left rotation)
        """
        try:
            left_shoulder = landmarks[self.LEFT_SHOULDER]
            right_shoulder = landmarks[self.RIGHT_SHOULDER]

            # Check visibility
            if left_shoulder['visibility'] < 0.5 or right_shoulder['visibility'] < 0.5:
                return None

            # Calculate shoulder vector in horizontal plane (x, z)
            dx = right_shoulder['x'] - left_shoulder['x']
            dz = right_shoulder['z'] - left_shoulder['z']

            # Calculate angle from forward direction (positive z-axis)
            # atan2(dx, dz) gives angle where 0 = facing forward
            rotation_angle = np.degrees(np.arctan2(dx, dz))

            return rotation_angle

        except (KeyError, IndexError, TypeError):
            return None

    def _estimate_body_height(self, landmarks_data: List[Dict]) -> float:
        """
        What: Estimate body height from nose to ankle distance
        Why: Needed for normalization when not provided
        Design Decision: Use median of first 10 frames
        """
        heights = []

        for frame in landmarks_data[:10]:
            try:
                nose = frame['landmarks'][self.NOSE]
                left_ankle = frame['landmarks'][self.LEFT_ANKLE]
                right_ankle = frame['landmarks'][self.RIGHT_ANKLE]

                if nose['visibility'] < 0.5:
                    continue

                # Calculate to both ankles and average
                left_height = abs(nose['y'] - left_ankle['y'])
                right_height = abs(nose['y'] - right_ankle['y'])

                avg_height = (left_height + right_height) / 2
                heights.append(avg_height)

            except (KeyError, IndexError, TypeError):
                continue

        return np.median(heights) if heights else 1.0

    def _calculate_wrist_trajectory_length(self, cycle_data: List[Dict],
                                          side: str) -> Optional[float]:
        """
        What: Calculate total wrist trajectory length for one cycle
        Why: Measure arm swing amplitude
        Design Decision: Sum 3D Euclidean distances between consecutive frames
        """
        wrist_idx = self.LEFT_WRIST if side == 'left' else self.RIGHT_WRIST

        positions = []
        for frame in cycle_data:
            try:
                wrist = frame['landmarks'][wrist_idx]
                if wrist['visibility'] >= 0.5:
                    positions.append([wrist['x'], wrist['y'], wrist['z']])
            except (KeyError, IndexError, TypeError):
                continue

        if len(positions) < 2:
            return None

        # Calculate total trajectory length
        total_length = 0.0
        for i in range(1, len(positions)):
            distance = np.linalg.norm(np.array(positions[i]) - np.array(positions[i-1]))
            total_length += distance

        return total_length

    # ==================== Helper Methods: P7 Kinetic Chain ====================

    def _evaluate_hip_shoulder_timing(self, landmarks_data: List[Dict],
                                     cycles: List[Dict], fps: float,
                                     thresholds: Dict) -> Dict:
        """
        What: Evaluate P7-1 - hip-shoulder rotation onset timing
        Why: Measure if rotation initiates from hips
        Design Decision: Detect rotation onset for hip and shoulder, measure time difference
        """
        timing_differences = []

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            # Detect hip rotation onset (when hip rotation exceeds threshold)
            hip_onset = self._detect_hip_rotation_onset(cycle_data)

            # Detect shoulder rotation onset
            shoulder_onset = self._detect_shoulder_rotation_onset(cycle_data)

            if hip_onset is not None and shoulder_onset is not None:
                time_diff = abs(shoulder_onset - hip_onset) / fps
                timing_differences.append(time_diff)

        if not timing_differences:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        avg_timing = np.mean(timing_differences)

        # Grade based on thresholds
        t = thresholds['hip_shoulder_timing']
        if t['excellent_min'] <= avg_timing <= t['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif t['good_min'] <= avg_timing <= t['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(avg_timing, 3),
            'grade': grade
        }

    def _evaluate_shoulder_elbow_timing(self, landmarks_data: List[Dict],
                                       cycles: List[Dict], fps: float,
                                       thresholds: Dict) -> Dict:
        """
        What: Evaluate P7-2 - shoulder-elbow peak velocity timing
        Why: Measure kinetic chain propagation from shoulder to elbow
        Design Decision: Detect peak angular velocity timing
        """
        timing_differences = []

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            # Detect peak velocity timing for shoulder and elbow
            shoulder_peak = self._detect_peak_velocity_frame(cycle_data, 'shoulder')
            elbow_peak = self._detect_peak_velocity_frame(cycle_data, 'elbow')

            if shoulder_peak is not None and elbow_peak is not None:
                time_diff = abs(elbow_peak - shoulder_peak) / fps
                timing_differences.append(time_diff)

        if not timing_differences:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        avg_timing = np.mean(timing_differences)

        # Grade based on thresholds
        t = thresholds['shoulder_elbow_timing']
        if t['excellent_min'] <= avg_timing <= t['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif t['good_min'] <= avg_timing <= t['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(avg_timing, 3),
            'grade': grade
        }

    def _evaluate_elbow_wrist_timing(self, landmarks_data: List[Dict],
                                    cycles: List[Dict], fps: float,
                                    thresholds: Dict) -> Dict:
        """
        What: Evaluate P7-3 - elbow-wrist peak velocity timing
        Why: Measure final kinetic chain propagation to wrist
        Design Decision: Detect peak angular velocity timing
        """
        timing_differences = []

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            # Detect peak velocity timing for elbow and wrist
            elbow_peak = self._detect_peak_velocity_frame(cycle_data, 'elbow')
            wrist_peak = self._detect_peak_velocity_frame(cycle_data, 'wrist')

            if elbow_peak is not None and wrist_peak is not None:
                time_diff = abs(wrist_peak - elbow_peak) / fps
                timing_differences.append(time_diff)

        if not timing_differences:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        avg_timing = np.mean(timing_differences)

        # Grade based on thresholds
        t = thresholds['elbow_wrist_timing']
        if t['excellent_min'] <= avg_timing <= t['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif t['good_min'] <= avg_timing <= t['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(avg_timing, 3),
            'grade': grade
        }

    def _detect_hip_rotation_onset(self, cycle_data: List[Dict]) -> Optional[int]:
        """
        What: Detect when hip rotation begins
        Why: Identify kinetic chain initiation point
        Design Decision: Use hip landmark horizontal velocity
        """
        hip_positions = []

        for frame in cycle_data:
            try:
                left_hip = frame['landmarks'][self.LEFT_HIP]
                right_hip = frame['landmarks'][self.RIGHT_HIP]

                # Calculate hip center in horizontal plane
                hip_center_x = (left_hip['x'] + right_hip['x']) / 2
                hip_center_z = (left_hip['z'] + right_hip['z']) / 2

                hip_positions.append([hip_center_x, hip_center_z])
            except (KeyError, IndexError, TypeError):
                hip_positions.append(None)

        # Calculate velocities
        velocities = []
        for i in range(1, len(hip_positions)):
            if hip_positions[i] is not None and hip_positions[i-1] is not None:
                velocity = np.linalg.norm(np.array(hip_positions[i]) - np.array(hip_positions[i-1]))
                velocities.append(velocity)
            else:
                velocities.append(0.0)

        if not velocities:
            return None

        # Detect onset: when velocity exceeds threshold
        max_velocity = max(velocities)
        threshold = max_velocity * 0.2

        for i, velocity in enumerate(velocities):
            if velocity > threshold:
                return i

        return None

    def _detect_shoulder_rotation_onset(self, cycle_data: List[Dict]) -> Optional[int]:
        """
        What: Detect when shoulder rotation begins
        Why: Measure shoulder rotation timing relative to hip
        Design Decision: Use shoulder line angular velocity
        """
        rotation_angles = []

        for frame in cycle_data:
            angle = self._calculate_trunk_rotation_angle(frame['landmarks'])
            rotation_angles.append(angle if angle is not None else 0.0)

        # Calculate angular velocities
        angular_velocities = []
        for i in range(1, len(rotation_angles)):
            ang_vel = abs(rotation_angles[i] - rotation_angles[i-1])
            angular_velocities.append(ang_vel)

        if not angular_velocities:
            return None

        # Detect onset: when angular velocity exceeds threshold
        max_ang_vel = max(angular_velocities)
        threshold = max_ang_vel * 0.2

        for i, ang_vel in enumerate(angular_velocities):
            if ang_vel > threshold:
                return i

        return None

    def _detect_peak_velocity_frame(self, cycle_data: List[Dict],
                                   joint: str) -> Optional[int]:
        """
        What: Detect frame with peak velocity for specified joint
        Why: Identify timing of maximum joint movement
        Design Decision: Calculate position changes and find maximum

        Args:
            joint: 'shoulder', 'elbow', or 'wrist'
        """
        if joint == 'shoulder':
            # Use trunk rotation angular velocity
            rotation_angles = []
            for frame in cycle_data:
                angle = self._calculate_trunk_rotation_angle(frame['landmarks'])
                rotation_angles.append(angle if angle is not None else 0.0)

            angular_velocities = [abs(rotation_angles[i] - rotation_angles[i-1])
                                 for i in range(1, len(rotation_angles))]

            if not angular_velocities:
                return None

            return np.argmax(angular_velocities)

        elif joint == 'elbow':
            # Use average of left and right elbow velocities
            left_velocities = self._calculate_joint_velocities(cycle_data, self.LEFT_ELBOW)
            right_velocities = self._calculate_joint_velocities(cycle_data, self.RIGHT_ELBOW)

            if left_velocities and right_velocities:
                avg_velocities = [(l + r) / 2 for l, r in zip(left_velocities, right_velocities)]
                return np.argmax(avg_velocities) if avg_velocities else None

            return None

        elif joint == 'wrist':
            # Use average of left and right wrist velocities
            left_velocities = self._calculate_joint_velocities(cycle_data, self.LEFT_WRIST)
            right_velocities = self._calculate_joint_velocities(cycle_data, self.RIGHT_WRIST)

            if left_velocities and right_velocities:
                avg_velocities = [(l + r) / 2 for l, r in zip(left_velocities, right_velocities)]
                return np.argmax(avg_velocities) if avg_velocities else None

            return None

        return None

    def _calculate_joint_velocities(self, cycle_data: List[Dict],
                                   joint_idx: int) -> List[float]:
        """
        What: Calculate 3D velocity for a specific joint across cycle
        Why: Needed for peak velocity detection
        Design Decision: Euclidean distance between consecutive frames
        """
        positions = []

        for frame in cycle_data:
            try:
                joint = frame['landmarks'][joint_idx]
                if joint['visibility'] >= 0.5:
                    positions.append([joint['x'], joint['y'], joint['z']])
                else:
                    positions.append(None)
            except (KeyError, IndexError, TypeError):
                positions.append(None)

        velocities = []
        for i in range(1, len(positions)):
            if positions[i] is not None and positions[i-1] is not None:
                velocity = np.linalg.norm(np.array(positions[i]) - np.array(positions[i-1]))
                velocities.append(velocity)
            else:
                velocities.append(0.0)

        return velocities

    # ==================== Helper Methods: P4 Joint Angles ====================

    def _evaluate_shoulder_rom(self, landmarks_data: List[Dict],
                              cycles: List[Dict], thresholds: Dict) -> Dict:
        """
        What: Evaluate P4-1 - shoulder ROM at swing maximum
        Why: Measure shoulder joint range of motion
        Design Decision: Calculate shoulder angle at peak of swing
        """
        shoulder_angles = []

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            # Find frame with maximum wrist distance from body (peak of swing)
            max_distance = 0
            peak_frame = None

            for frame in cycle_data:
                try:
                    left_wrist = frame['landmarks'][self.LEFT_WRIST]
                    right_wrist = frame['landmarks'][self.RIGHT_WRIST]
                    left_shoulder = frame['landmarks'][self.LEFT_SHOULDER]
                    right_shoulder = frame['landmarks'][self.RIGHT_SHOULDER]

                    # Average wrist distance from corresponding shoulder
                    left_dist = np.linalg.norm([
                        left_wrist['x'] - left_shoulder['x'],
                        left_wrist['y'] - left_shoulder['y'],
                        left_wrist['z'] - left_shoulder['z']
                    ])
                    right_dist = np.linalg.norm([
                        right_wrist['x'] - right_shoulder['x'],
                        right_wrist['y'] - right_shoulder['y'],
                        right_wrist['z'] - right_shoulder['z']
                    ])

                    avg_dist = (left_dist + right_dist) / 2

                    if avg_dist > max_distance:
                        max_distance = avg_dist
                        peak_frame = frame

                except (KeyError, IndexError, TypeError):
                    continue

            if peak_frame:
                # Calculate shoulder angle at peak
                left_angle = self._calculate_shoulder_angle(peak_frame['landmarks'], 'left')
                right_angle = self._calculate_shoulder_angle(peak_frame['landmarks'], 'right')

                if left_angle is not None and right_angle is not None:
                    avg_angle = (left_angle + right_angle) / 2
                    shoulder_angles.append(avg_angle)

        if not shoulder_angles:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        avg_shoulder_rom = np.mean(shoulder_angles)

        # Grade based on thresholds
        t = thresholds['shoulder_rom']
        if t['excellent_min'] <= avg_shoulder_rom <= t['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif t['good_min'] <= avg_shoulder_rom <= t['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(avg_shoulder_rom, 1),
            'grade': grade
        }

    def _evaluate_elbow_extension(self, landmarks_data: List[Dict],
                                 cycles: List[Dict], thresholds: Dict) -> Dict:
        """
        What: Evaluate P4-2 - elbow extension during swing
        Why: Measure if arms are properly extended
        Design Decision: Find minimum elbow angle across all cycles
        """
        min_elbow_angles = []

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            cycle_angles = []
            for frame in cycle_data:
                left_angle = self._calculate_elbow_angle(frame['landmarks'], 'left')
                right_angle = self._calculate_elbow_angle(frame['landmarks'], 'right')

                if left_angle is not None:
                    cycle_angles.append(left_angle)
                if right_angle is not None:
                    cycle_angles.append(right_angle)

            if cycle_angles:
                min_elbow_angles.append(min(cycle_angles))

        if not min_elbow_angles:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        avg_min_elbow = np.mean(min_elbow_angles)

        # Grade based on thresholds
        t = thresholds['elbow_extension']
        if t['excellent_min'] <= avg_min_elbow <= t['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif t['good_min'] <= avg_min_elbow <= t['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(avg_min_elbow, 1),
            'grade': grade
        }

    def _evaluate_trunk_lateral_flexion(self, landmarks_data: List[Dict],
                                       cycles: List[Dict], thresholds: Dict) -> Dict:
        """
        What: Evaluate P4-3 - trunk lateral flexion
        Why: Measure if trunk stays upright (lower is better)
        Design Decision: Calculate max trunk lean angle from vertical
        """
        max_flexion_angles = []

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            cycle_angles = []
            for frame in cycle_data:
                flexion_angle = self._calculate_trunk_lateral_flexion_angle(frame['landmarks'])
                if flexion_angle is not None:
                    cycle_angles.append(flexion_angle)

            if cycle_angles:
                max_flexion_angles.append(max(cycle_angles))

        if not max_flexion_angles:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        avg_max_flexion = np.mean(max_flexion_angles)

        # Grade based on thresholds (lower is better)
        t = thresholds['trunk_lateral_flexion']
        if avg_max_flexion <= t['excellent']:
            score = 1.0
            grade = 'excellent'
        elif avg_max_flexion <= t['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(avg_max_flexion, 1),
            'grade': grade
        }

    def _calculate_shoulder_angle(self, landmarks: List[Dict], side: str) -> Optional[float]:
        """
        What: Calculate shoulder angle (shoulder-elbow-wrist)
        Why: Measure shoulder joint position
        Design Decision: 3D angle calculation using vectors
        """
        try:
            if side == 'left':
                shoulder = landmarks[self.LEFT_SHOULDER]
                elbow = landmarks[self.LEFT_ELBOW]
                wrist = landmarks[self.LEFT_WRIST]
            else:
                shoulder = landmarks[self.RIGHT_SHOULDER]
                elbow = landmarks[self.RIGHT_ELBOW]
                wrist = landmarks[self.RIGHT_WRIST]

            # Check visibility
            if shoulder['visibility'] < 0.5 or elbow['visibility'] < 0.5 or wrist['visibility'] < 0.5:
                return None

            # Vectors: shoulder→elbow and shoulder→wrist
            v1 = np.array([
                elbow['x'] - shoulder['x'],
                elbow['y'] - shoulder['y'],
                elbow['z'] - shoulder['z']
            ])
            v2 = np.array([
                wrist['x'] - shoulder['x'],
                wrist['y'] - shoulder['y'],
                wrist['z'] - shoulder['z']
            ])

            # Calculate angle
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            angle = np.degrees(np.arccos(cos_angle))

            return angle

        except (KeyError, IndexError, TypeError, ValueError):
            return None

    def _calculate_elbow_angle(self, landmarks: List[Dict], side: str) -> Optional[float]:
        """
        What: Calculate elbow angle (shoulder-elbow-wrist)
        Why: Measure elbow extension
        Design Decision: 3D angle calculation using vectors
        """
        try:
            if side == 'left':
                shoulder = landmarks[self.LEFT_SHOULDER]
                elbow = landmarks[self.LEFT_ELBOW]
                wrist = landmarks[self.LEFT_WRIST]
            else:
                shoulder = landmarks[self.RIGHT_SHOULDER]
                elbow = landmarks[self.RIGHT_ELBOW]
                wrist = landmarks[self.RIGHT_WRIST]

            # Check visibility
            if shoulder['visibility'] < 0.5 or elbow['visibility'] < 0.5 or wrist['visibility'] < 0.5:
                return None

            # Vectors: shoulder→elbow and wrist→elbow
            v1 = np.array([
                shoulder['x'] - elbow['x'],
                shoulder['y'] - elbow['y'],
                shoulder['z'] - elbow['z']
            ])
            v2 = np.array([
                wrist['x'] - elbow['x'],
                wrist['y'] - elbow['y'],
                wrist['z'] - elbow['z']
            ])

            # Calculate angle
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            angle = np.degrees(np.arccos(cos_angle))

            return angle

        except (KeyError, IndexError, TypeError, ValueError):
            return None

    def _calculate_trunk_lateral_flexion_angle(self, landmarks: List[Dict]) -> Optional[float]:
        """
        What: Calculate trunk lateral flexion angle from vertical
        Why: Measure if trunk leans sideways
        Design Decision: Calculate angle between shoulder line and horizontal plane
        """
        try:
            left_shoulder = landmarks[self.LEFT_SHOULDER]
            right_shoulder = landmarks[self.RIGHT_SHOULDER]

            # Check visibility
            if left_shoulder['visibility'] < 0.5 or right_shoulder['visibility'] < 0.5:
                return None

            # Calculate shoulder height difference
            height_diff = abs(left_shoulder['y'] - right_shoulder['y'])

            # Calculate shoulder distance in horizontal plane
            horizontal_dist = np.sqrt(
                (right_shoulder['x'] - left_shoulder['x'])**2 +
                (right_shoulder['z'] - left_shoulder['z'])**2
            )

            if horizontal_dist == 0:
                return 0.0

            # Calculate angle from horizontal
            flexion_angle = np.degrees(np.arctan(height_diff / horizontal_dist))

            return flexion_angle

        except (KeyError, IndexError, TypeError, ValueError):
            return None

    # ==================== Helper Methods: P6 Force Direction ====================

    def _evaluate_wrist_horizontality(self, landmarks_data: List[Dict],
                                     cycles: List[Dict], body_height: float,
                                     thresholds: Dict) -> Dict:
        """
        What: Evaluate P6-1 - wrist trajectory horizontality
        Why: Measure if wrist moves in horizontal plane (less vertical variation is better)
        Design Decision: Calculate normalized vertical wrist variation
        """
        vertical_variations = []

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            # Collect wrist Y positions (average of left and right)
            wrist_y_positions = []

            for frame in cycle_data:
                try:
                    left_wrist = frame['landmarks'][self.LEFT_WRIST]
                    right_wrist = frame['landmarks'][self.RIGHT_WRIST]

                    if left_wrist['visibility'] >= 0.5 and right_wrist['visibility'] >= 0.5:
                        avg_y = (left_wrist['y'] + right_wrist['y']) / 2
                        wrist_y_positions.append(avg_y)

                except (KeyError, IndexError, TypeError):
                    continue

            if len(wrist_y_positions) >= 3:
                # Calculate vertical variation (max - min)
                variation = max(wrist_y_positions) - min(wrist_y_positions)
                vertical_variations.append(variation)

        if not vertical_variations:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        avg_variation = np.mean(vertical_variations)

        # Normalize by body height
        normalized_variation = avg_variation / body_height if body_height > 0 else 0

        # Grade based on thresholds (lower is better)
        t = thresholds['wrist_horizontality']
        if normalized_variation <= t['excellent']:
            score = 1.0
            grade = 'excellent'
        elif normalized_variation <= t['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(normalized_variation, 3),
            'grade': grade
        }

    def _evaluate_com_stability(self, landmarks_data: List[Dict],
                               cycles: List[Dict], shoulder_width: float,
                               thresholds: Dict) -> Dict:
        """
        What: Evaluate P6-2 - COM stability during swing
        Why: Measure if center of mass stays stable
        Design Decision: Calculate total COM movement distance normalized by shoulder_width
        """
        com_movements = []

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            # Calculate COM positions (average of hips)
            com_positions = []

            for frame in cycle_data:
                try:
                    left_hip = frame['landmarks'][self.LEFT_HIP]
                    right_hip = frame['landmarks'][self.RIGHT_HIP]

                    com_x = (left_hip['x'] + right_hip['x']) / 2
                    com_y = (left_hip['y'] + right_hip['y']) / 2
                    com_z = (left_hip['z'] + right_hip['z']) / 2

                    com_positions.append([com_x, com_y, com_z])

                except (KeyError, IndexError, TypeError):
                    continue

            if len(com_positions) >= 2:
                # Calculate total movement distance
                total_distance = 0.0
                for i in range(1, len(com_positions)):
                    distance = np.linalg.norm(np.array(com_positions[i]) - np.array(com_positions[i-1]))
                    total_distance += distance

                com_movements.append(total_distance)

        if not com_movements:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        avg_movement = np.mean(com_movements)

        # Normalize by shoulder_width
        normalized_movement = avg_movement / shoulder_width if shoulder_width > 0 else 0

        # Grade based on thresholds (lower is better)
        t = thresholds['com_stability']
        if normalized_movement <= t['excellent']:
            score = 1.0
            grade = 'excellent'
        elif normalized_movement <= t['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(normalized_movement, 3),
            'grade': grade
        }

    def _evaluate_trajectory_reproducibility(self, landmarks_data: List[Dict],
                                            cycles: List[Dict],
                                            thresholds: Dict) -> Dict:
        """
        What: Evaluate P6-3 - trajectory reproducibility
        Why: Measure cycle-to-cycle consistency
        Design Decision: Calculate CV of wrist displacement across cycles
        """
        cycle_displacements = []

        for cycle in cycles:
            cycle_data = landmarks_data[cycle['start']:cycle['end']]

            # Calculate total wrist displacement for this cycle
            left_displacement = self._calculate_total_displacement(cycle_data, self.LEFT_WRIST)
            right_displacement = self._calculate_total_displacement(cycle_data, self.RIGHT_WRIST)

            if left_displacement is not None and right_displacement is not None:
                avg_displacement = (left_displacement + right_displacement) / 2
                cycle_displacements.append(avg_displacement)

        if len(cycle_displacements) < 2:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        # Calculate coefficient of variation
        mean_displacement = np.mean(cycle_displacements)
        std_displacement = np.std(cycle_displacements)

        cv = std_displacement / mean_displacement if mean_displacement > 0 else 0

        # Grade based on thresholds (lower is better)
        t = thresholds['trajectory_reproducibility']
        if cv <= t['excellent']:
            score = 1.0
            grade = 'excellent'
        elif cv <= t['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(cv, 3),
            'grade': grade
        }

    def _calculate_total_displacement(self, cycle_data: List[Dict],
                                     joint_idx: int) -> Optional[float]:
        """
        What: Calculate total 3D displacement for a joint during cycle
        Why: Measure movement extent
        Design Decision: Euclidean distance from start to end position
        """
        positions = []

        for frame in cycle_data:
            try:
                joint = frame['landmarks'][joint_idx]
                if joint['visibility'] >= 0.5:
                    positions.append([joint['x'], joint['y'], joint['z']])
            except (KeyError, IndexError, TypeError):
                continue

        if len(positions) < 2:
            return None

        # Calculate displacement from start to end
        displacement = np.linalg.norm(np.array(positions[-1]) - np.array(positions[0]))

        return displacement
