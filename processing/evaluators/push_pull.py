"""
Purpose: T06 Push-Pull evaluation using 2-axis system (A: 3pts, B: 9pts)
Responsibility: Evaluate push/pull distances, compensation, trajectory linearity, and kinetic chain
Dependencies: numpy, config.json (T06_push_pull thresholds)
Created: 2025-10-27 by Claude Code
Decision Log: ADR-010 (2-axis evaluation system)

CRITICAL: All metrics are objective - distances (normalized), angles (degrees), time (seconds)
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class PushPullEvaluator:
    """
    What: Evaluates Push-Pull test (T06) with 2-axis scoring
    Why: Measure push/pull movement quality, compensation, and kinetic chain timing
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

        self.thresholds = self.config['thresholds']['T06_push_pull']

    def evaluate(self, landmarks_data: List[Dict], base_width: float,
                 shoulder_width: float, leg_length: float,
                 fps: float = 30.0) -> Dict:
        """
        What: Main evaluation entry point returning 12-point structure
        Why: Orchestrate A + B evaluation and return complete results
        Design Decision: Follow same pattern as other evaluators

        Args:
            landmarks_data: List of frame data with MediaPipe landmarks
            base_width: Normalization factor (max of shoulder/pelvis width)
            shoulder_width: Shoulder width for normalization
            fps: Frame rate for timing calculations

        Returns:
            Dict with structure: {test_id, execution, principles, total, max_score}
        """
        # Input validation
        if not landmarks_data or len(landmarks_data) < 10:
            return {
                'test_id': 'T06_push_pull',
                'error': 'Insufficient data',
                'execution': {'total': 0.0},
                'principles': {'total': 0.0},
                'total': 0.0,
                'max_score': 12.0
            }

        if base_width <= 0 or shoulder_width <= 0:
            return {
                'test_id': 'T06_push_pull',
                'error': 'Invalid normalization factors',
                'execution': {'total': 0.0},
                'principles': {'total': 0.0},
                'total': 0.0,
                'max_score': 12.0
            }

        # A. Execution evaluation (3 points)
        execution = self.evaluate_execution(
            landmarks_data, base_width, shoulder_width, fps
        )

        # B. Principles evaluation (9 points)
        principles = self.evaluate_principles(
            landmarks_data, base_width, shoulder_width, fps
        )

        return {
            'test_id': 'T06_push_pull',
            'execution': execution,
            'principles': principles,
            'total': execution['total'] + principles['total'],
            'max_score': 12.0
        }

    def evaluate_execution(self, landmarks_data: List[Dict], base_width: float,
                          shoulder_width: float, fps: float = 30.0) -> Dict:
        """
        What: A-axis evaluation (Execution/Completion) - 3 points
        Why: Measure objective execution quality
        Design Decision: A1 (push distance) + A2 (pull distance) + A3 (symmetry)

        CRITICAL: A1 (1.0pt), A2 (1.0pt), A3 (1.0pt) = 3.0 points total
        """
        # Detect push and pull phases
        phases = self._detect_push_pull_phases(landmarks_data)

        # A1: Push distance (1.0 point)
        a1_push_distance = self._score_push_distance(landmarks_data, phases, shoulder_width)

        # A2: Pull distance (1.0 point)
        a2_pull_distance = self._score_pull_distance(landmarks_data, phases, shoulder_width)

        # A3: Left-right symmetry (1.0 point)
        a3_symmetry = self._score_left_right_symmetry(landmarks_data, phases, shoulder_width)

        return {
            'A1_push_distance': a1_push_distance,
            'A2_pull_distance': a2_pull_distance,
            'A3_left_right_symmetry': a3_symmetry,
            'total': (a1_push_distance['score'] +
                     a2_pull_distance['score'] +
                     a3_symmetry['score'])
        }

    def evaluate_principles(self, landmarks_data: List[Dict], base_width: float,
                           shoulder_width: float, fps: float = 30.0) -> Dict:
        """
        What: B-axis evaluation (Principles Achievement) - 9 points
        Why: Measure adherence to movement principles
        Design Decision: P1 (compensation) + P6 (force direction) + P7 (kinetic chain)

        CRITICAL: P1 (3.0pts), P6 (3.0pts), P7 (3.0pts) = 9.0 points total
        """
        # Detect push and pull phases
        phases = self._detect_push_pull_phases(landmarks_data)

        # P1: Compensation patterns (3.0 points)
        p1_compensation = self._evaluate_compensation(
            landmarks_data, phases, base_width, shoulder_width
        )

        # P6: Force direction control (3.0 points)
        p6_force_direction = self._evaluate_force_direction(
            landmarks_data, phases, shoulder_width
        )

        # P7: Kinetic chain optimization (3.0 points)
        p7_kinetic_chain = self._evaluate_kinetic_chain(
            landmarks_data, phases, fps
        )

        return {
            'P1_compensation': p1_compensation,
            'P6_force_direction': p6_force_direction,
            'P7_kinetic_chain': p7_kinetic_chain,
            'total': (p1_compensation['score'] +
                     p6_force_direction['score'] +
                     p7_kinetic_chain['score'])
        }

    # ==================== A. Execution Scoring Methods ====================

    def _score_push_distance(self, landmarks_data: List[Dict],
                            phases: Dict, shoulder_width: float) -> Dict:
        """
        What: Score A1 - push distance (forward wrist movement)
        Why: Measure push action range
        Design Decision: Calculate max forward wrist displacement in z-axis

        Returns:
            Dict with score (0-1.0), max_score (1.0), value (ratio), grade
        """
        thresholds = self.thresholds['execution']['push_distance']

        if 'push' not in phases or not phases['push']:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'value': 0.0,
                'grade': 'poor',
                'details': 'No push phase detected'
            }

        # Get push phase data
        push_phase = phases['push']
        push_data = landmarks_data[push_phase['start']:push_phase['end']]

        # Calculate wrist center displacement
        wrist_z_positions = []
        for frame in push_data:
            try:
                left_wrist = frame['landmarks'][self.LEFT_WRIST]
                right_wrist = frame['landmarks'][self.RIGHT_WRIST]

                if left_wrist['visibility'] >= 0.5 and right_wrist['visibility'] >= 0.5:
                    wrist_center_z = (left_wrist['z'] + right_wrist['z']) / 2
                    wrist_z_positions.append(wrist_center_z)
            except (KeyError, IndexError, TypeError):
                continue

        if len(wrist_z_positions) < 2:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'value': 0.0,
                'grade': 'poor',
                'details': 'Insufficient push data'
            }

        # Calculate forward displacement (z increases = forward)
        push_distance = max(wrist_z_positions) - min(wrist_z_positions)

        # Normalize by shoulder width
        normalized_distance = push_distance / shoulder_width if shoulder_width > 0 else 0

        # Grade based on thresholds
        if normalized_distance >= thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif normalized_distance >= thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'max_score': 1.0,
            'value': round(normalized_distance, 3),
            'grade': grade,
            'distance': round(push_distance, 3)
        }

    def _score_pull_distance(self, landmarks_data: List[Dict],
                            phases: Dict, shoulder_width: float) -> Dict:
        """
        What: Score A2 - pull distance (backward elbow movement)
        Why: Measure pull action range
        Design Decision: Calculate max backward elbow displacement in z-axis

        Returns:
            Dict with score (0-1.0), max_score (1.0), value (ratio), grade
        """
        thresholds = self.thresholds['execution']['pull_distance']

        if 'pull' not in phases or not phases['pull']:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'value': 0.0,
                'grade': 'poor',
                'details': 'No pull phase detected'
            }

        # Get pull phase data
        pull_phase = phases['pull']
        pull_data = landmarks_data[pull_phase['start']:pull_phase['end']]

        # Calculate elbow center displacement
        elbow_z_positions = []
        for frame in pull_data:
            try:
                left_elbow = frame['landmarks'][self.LEFT_ELBOW]
                right_elbow = frame['landmarks'][self.RIGHT_ELBOW]

                if left_elbow['visibility'] >= 0.5 and right_elbow['visibility'] >= 0.5:
                    elbow_center_z = (left_elbow['z'] + right_elbow['z']) / 2
                    elbow_z_positions.append(elbow_center_z)
            except (KeyError, IndexError, TypeError):
                continue

        if len(elbow_z_positions) < 2:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'value': 0.0,
                'grade': 'poor',
                'details': 'Insufficient pull data'
            }

        # Calculate backward displacement (z decreases = backward)
        pull_distance = max(elbow_z_positions) - min(elbow_z_positions)

        # Normalize by shoulder width
        normalized_distance = pull_distance / shoulder_width if shoulder_width > 0 else 0

        # Grade based on thresholds
        if normalized_distance >= thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif normalized_distance >= thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'max_score': 1.0,
            'value': round(normalized_distance, 3),
            'grade': grade,
            'distance': round(pull_distance, 3)
        }

    def _score_left_right_symmetry(self, landmarks_data: List[Dict],
                                   phases: Dict, shoulder_width: float) -> Dict:
        """
        What: Score A3 - left-right symmetry
        Why: Measure bilateral balance
        Design Decision: Calculate average of push and pull symmetry ratios

        Returns:
            Dict with score (0-1.0), max_score (1.0), value (ratio), grade
        """
        thresholds = self.thresholds['execution']['left_right_symmetry']

        symmetry_ratios = []

        # Push symmetry
        if 'push' in phases and phases['push']:
            push_symmetry = self._calculate_push_symmetry(landmarks_data, phases['push'])
            if push_symmetry is not None:
                symmetry_ratios.append(push_symmetry)

        # Pull symmetry
        if 'pull' in phases and phases['pull']:
            pull_symmetry = self._calculate_pull_symmetry(landmarks_data, phases['pull'])
            if pull_symmetry is not None:
                symmetry_ratios.append(pull_symmetry)

        if not symmetry_ratios:
            return {
                'score': 0.0,
                'max_score': 1.0,
                'value': 0.0,
                'grade': 'poor',
                'details': 'Could not calculate symmetry'
            }

        # Average symmetry ratio
        avg_symmetry_ratio = np.mean(symmetry_ratios)

        # Grade based on thresholds (lower is better)
        if avg_symmetry_ratio <= thresholds['excellent']:
            score = 1.0
            grade = 'excellent'
        elif avg_symmetry_ratio <= thresholds['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'max_score': 1.0,
            'value': round(avg_symmetry_ratio, 3),
            'grade': grade
        }

    # ==================== B. Principles Evaluation Methods ====================

    def _evaluate_compensation(self, landmarks_data: List[Dict],
                              phases: Dict, base_width: float,
                              shoulder_width: float) -> Dict:
        """
        What: Evaluate P1 - compensation patterns
        Why: Measure unwanted compensatory movements
        Design Decision: 3 sub-metrics × 1 point each = 3 points

        CRITICAL: P1-1 (torso lean), P1-2 (shoulder elevation), P1-3 (pelvis tilt)
        """
        thresholds = self.thresholds['principles']['P1_compensation']

        # P1-1: Torso lean (trunk forward/backward tilt)
        p11_result = self._evaluate_torso_lean(
            landmarks_data, phases, thresholds
        )

        # P1-2: Shoulder elevation asymmetry
        p12_result = self._evaluate_shoulder_elevation(
            landmarks_data, phases, shoulder_width, thresholds
        )

        # P1-3: Pelvis anterior/posterior tilt
        p13_result = self._evaluate_pelvis_tilt(
            landmarks_data, phases, base_width, thresholds
        )

        total_score = p11_result['score'] + p12_result['score'] + p13_result['score']

        return {
            'score': total_score,
            'max_score': 3.0,
            'torso_lean': p11_result,
            'shoulder_elevation': p12_result,
            'pelvis_tilt': p13_result
        }

    def _evaluate_force_direction(self, landmarks_data: List[Dict],
                                  phases: Dict, shoulder_width: float) -> Dict:
        """
        What: Evaluate P6 - force direction control
        Why: Measure trajectory linearity and COM stability
        Design Decision: 3 sub-metrics × 1 point each = 3 points

        CRITICAL: P6-1 (push linearity), P6-2 (pull linearity), P6-3 (COM movement)
        """
        thresholds = self.thresholds['principles']['P6_force_direction']

        # P6-1: Push trajectory linearity
        p61_result = self._evaluate_push_trajectory_linearity(
            landmarks_data, phases, shoulder_width, thresholds
        )

        # P6-2: Pull trajectory linearity
        p62_result = self._evaluate_pull_trajectory_linearity(
            landmarks_data, phases, shoulder_width, thresholds
        )

        # P6-3: COM movement restriction
        p63_result = self._evaluate_com_movement(
            landmarks_data, phases, shoulder_width, thresholds
        )

        total_score = p61_result['score'] + p62_result['score'] + p63_result['score']

        return {
            'score': total_score,
            'max_score': 3.0,
            'push_trajectory_linearity': p61_result,
            'pull_trajectory_linearity': p62_result,
            'com_movement': p63_result
        }

    def _evaluate_kinetic_chain(self, landmarks_data: List[Dict],
                                phases: Dict, fps: float) -> Dict:
        """
        What: Evaluate P7 - kinetic chain optimization
        Why: Measure sequential force transmission
        Design Decision: 3 sub-metrics × 1 point each = 3 points

        CRITICAL: P7-1 (push chain), P7-2 (pull chain), P7-3 (transition)
        """
        thresholds = self.thresholds['principles']['P7_kinetic_chain']

        # P7-1: Push chain timing (trunk→shoulder→elbow)
        p71_result = self._evaluate_push_chain_timing(
            landmarks_data, phases, fps, thresholds
        )

        # P7-2: Pull chain timing (wrist→elbow→shoulder)
        p72_result = self._evaluate_pull_chain_timing(
            landmarks_data, phases, fps, thresholds
        )

        # P7-3: Push-pull transition efficiency
        p73_result = self._evaluate_transition_efficiency(
            landmarks_data, phases, fps, thresholds
        )

        total_score = p71_result['score'] + p72_result['score'] + p73_result['score']

        return {
            'score': total_score,
            'max_score': 3.0,
            'push_chain_timing': p71_result,
            'pull_chain_timing': p72_result,
            'transition_efficiency': p73_result
        }

    # ==================== Helper Methods: Phase Detection ====================

    def _detect_push_pull_phases(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: Detect push and pull phases based on z-axis movement
        Why: Identify distinct push (forward) and pull (backward) movements
        Design Decision: Use wrist/elbow z-velocity to detect phases

        Returns:
            Dict with 'push' and 'pull' phase info: {'start': int, 'end': int}
        """
        # Calculate wrist center z-velocity
        wrist_z_velocities = []
        wrist_z_positions = []

        for frame in landmarks_data:
            try:
                left_wrist = frame['landmarks'][self.LEFT_WRIST]
                right_wrist = frame['landmarks'][self.RIGHT_WRIST]

                if left_wrist['visibility'] >= 0.5 and right_wrist['visibility'] >= 0.5:
                    wrist_center_z = (left_wrist['z'] + right_wrist['z']) / 2
                    wrist_z_positions.append(wrist_center_z)
                else:
                    wrist_z_positions.append(None)
            except (KeyError, IndexError, TypeError):
                wrist_z_positions.append(None)

        # Calculate velocities
        for i in range(1, len(wrist_z_positions)):
            if wrist_z_positions[i] is not None and wrist_z_positions[i-1] is not None:
                velocity = wrist_z_positions[i] - wrist_z_positions[i-1]
                wrist_z_velocities.append(velocity)
            else:
                wrist_z_velocities.append(0.0)

        if not wrist_z_velocities:
            return {'push': None, 'pull': None}

        # Detect push phase (positive velocity = forward movement)
        push_phase = self._find_continuous_phase(wrist_z_velocities, threshold=0.001, min_duration=10)

        # Detect pull phase (negative velocity = backward movement)
        # Use elbow for pull detection
        elbow_z_velocities = []
        elbow_z_positions = []

        for frame in landmarks_data:
            try:
                left_elbow = frame['landmarks'][self.LEFT_ELBOW]
                right_elbow = frame['landmarks'][self.RIGHT_ELBOW]

                if left_elbow['visibility'] >= 0.5 and right_elbow['visibility'] >= 0.5:
                    elbow_center_z = (left_elbow['z'] + right_elbow['z']) / 2
                    elbow_z_positions.append(elbow_center_z)
                else:
                    elbow_z_positions.append(None)
            except (KeyError, IndexError, TypeError):
                elbow_z_positions.append(None)

        # Calculate velocities
        for i in range(1, len(elbow_z_positions)):
            if elbow_z_positions[i] is not None and elbow_z_positions[i-1] is not None:
                velocity = elbow_z_positions[i] - elbow_z_positions[i-1]
                elbow_z_velocities.append(velocity)
            else:
                elbow_z_velocities.append(0.0)

        # Detect pull phase (negative velocity = backward movement)
        pull_phase = self._find_continuous_phase(elbow_z_velocities, threshold=-0.001, min_duration=10, negative=True)

        return {
            'push': push_phase,
            'pull': pull_phase
        }

    def _find_continuous_phase(self, velocities: List[float], threshold: float,
                              min_duration: int, negative: bool = False) -> Optional[Dict]:
        """
        What: Find continuous phase where velocity exceeds threshold
        Why: Identify sustained movement in one direction
        Design Decision: Use threshold and minimum duration to filter noise

        Args:
            negative: If True, look for negative velocities (backward movement)
        """
        in_phase = False
        phase_start = 0
        longest_phase = None
        max_duration = 0

        for i, velocity in enumerate(velocities):
            if negative:
                condition = velocity < threshold
            else:
                condition = velocity > threshold

            if condition:
                if not in_phase:
                    in_phase = True
                    phase_start = i
            else:
                if in_phase:
                    duration = i - phase_start
                    if duration >= min_duration and duration > max_duration:
                        max_duration = duration
                        longest_phase = {'start': phase_start, 'end': i}
                    in_phase = False

        # Check final phase
        if in_phase:
            duration = len(velocities) - phase_start
            if duration >= min_duration and duration > max_duration:
                longest_phase = {'start': phase_start, 'end': len(velocities)}

        return longest_phase

    # ==================== Helper Methods: Symmetry ====================

    def _calculate_push_symmetry(self, landmarks_data: List[Dict],
                                 push_phase: Dict) -> Optional[float]:
        """
        What: Calculate push symmetry (left-right wrist movement difference)
        Why: Measure bilateral balance during push
        Design Decision: Compare left and right wrist z-displacement
        """
        push_data = landmarks_data[push_phase['start']:push_phase['end']]

        left_z_positions = []
        right_z_positions = []

        for frame in push_data:
            try:
                left_wrist = frame['landmarks'][self.LEFT_WRIST]
                right_wrist = frame['landmarks'][self.RIGHT_WRIST]

                if left_wrist['visibility'] >= 0.5:
                    left_z_positions.append(left_wrist['z'])
                if right_wrist['visibility'] >= 0.5:
                    right_z_positions.append(right_wrist['z'])
            except (KeyError, IndexError, TypeError):
                continue

        if len(left_z_positions) < 2 or len(right_z_positions) < 2:
            return None

        # Calculate displacement for each side
        left_displacement = max(left_z_positions) - min(left_z_positions)
        right_displacement = max(right_z_positions) - min(right_z_positions)

        # Calculate symmetry ratio
        max_displacement = max(left_displacement, right_displacement)
        if max_displacement == 0:
            return 0.0

        symmetry_ratio = abs(left_displacement - right_displacement) / max_displacement

        return symmetry_ratio

    def _calculate_pull_symmetry(self, landmarks_data: List[Dict],
                                 pull_phase: Dict) -> Optional[float]:
        """
        What: Calculate pull symmetry (left-right elbow movement difference)
        Why: Measure bilateral balance during pull
        Design Decision: Compare left and right elbow z-displacement
        """
        pull_data = landmarks_data[pull_phase['start']:pull_phase['end']]

        left_z_positions = []
        right_z_positions = []

        for frame in pull_data:
            try:
                left_elbow = frame['landmarks'][self.LEFT_ELBOW]
                right_elbow = frame['landmarks'][self.RIGHT_ELBOW]

                if left_elbow['visibility'] >= 0.5:
                    left_z_positions.append(left_elbow['z'])
                if right_elbow['visibility'] >= 0.5:
                    right_z_positions.append(right_elbow['z'])
            except (KeyError, IndexError, TypeError):
                continue

        if len(left_z_positions) < 2 or len(right_z_positions) < 2:
            return None

        # Calculate displacement for each side
        left_displacement = max(left_z_positions) - min(left_z_positions)
        right_displacement = max(right_z_positions) - min(right_z_positions)

        # Calculate symmetry ratio
        max_displacement = max(left_displacement, right_displacement)
        if max_displacement == 0:
            return 0.0

        symmetry_ratio = abs(left_displacement - right_displacement) / max_displacement

        return symmetry_ratio

    # ==================== Helper Methods: P6 Force Direction ====================

    def _evaluate_push_trajectory_linearity(self, landmarks_data: List[Dict],
                                           phases: Dict, shoulder_width: float,
                                           thresholds: Dict) -> Dict:
        """
        What: Evaluate P6-1 - push trajectory linearity
        Why: Measure deviation from ideal straight line during push
        Design Decision: Calculate average deviation from start-end line
        """
        if 'push' not in phases or not phases['push']:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        push_phase = phases['push']
        push_data = landmarks_data[push_phase['start']:push_phase['end']]

        # Collect wrist center positions
        wrist_positions = []
        for frame in push_data:
            try:
                left_wrist = frame['landmarks'][self.LEFT_WRIST]
                right_wrist = frame['landmarks'][self.RIGHT_WRIST]

                if left_wrist['visibility'] >= 0.5 and right_wrist['visibility'] >= 0.5:
                    wrist_center = np.array([
                        (left_wrist['x'] + right_wrist['x']) / 2,
                        (left_wrist['y'] + right_wrist['y']) / 2,
                        (left_wrist['z'] + right_wrist['z']) / 2
                    ])
                    wrist_positions.append(wrist_center)
            except (KeyError, IndexError, TypeError):
                continue

        if len(wrist_positions) < 3:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        # Calculate deviation from ideal line
        avg_deviation = self._calculate_trajectory_deviation(wrist_positions)

        # Normalize by shoulder width
        normalized_deviation = avg_deviation / shoulder_width if shoulder_width > 0 else 0

        # Grade based on thresholds (lower is better)
        t = thresholds['push_trajectory_linearity']
        if normalized_deviation <= t['excellent']:
            score = 1.0
            grade = 'excellent'
        elif normalized_deviation <= t['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(normalized_deviation, 3),
            'grade': grade
        }

    def _evaluate_pull_trajectory_linearity(self, landmarks_data: List[Dict],
                                           phases: Dict, shoulder_width: float,
                                           thresholds: Dict) -> Dict:
        """
        What: Evaluate P6-2 - pull trajectory linearity
        Why: Measure deviation from ideal straight line during pull
        Design Decision: Calculate average deviation from start-end line
        """
        if 'pull' not in phases or not phases['pull']:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        pull_phase = phases['pull']
        pull_data = landmarks_data[pull_phase['start']:pull_phase['end']]

        # Collect elbow center positions
        elbow_positions = []
        for frame in pull_data:
            try:
                left_elbow = frame['landmarks'][self.LEFT_ELBOW]
                right_elbow = frame['landmarks'][self.RIGHT_ELBOW]

                if left_elbow['visibility'] >= 0.5 and right_elbow['visibility'] >= 0.5:
                    elbow_center = np.array([
                        (left_elbow['x'] + right_elbow['x']) / 2,
                        (left_elbow['y'] + right_elbow['y']) / 2,
                        (left_elbow['z'] + right_elbow['z']) / 2
                    ])
                    elbow_positions.append(elbow_center)
            except (KeyError, IndexError, TypeError):
                continue

        if len(elbow_positions) < 3:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        # Calculate deviation from ideal line
        avg_deviation = self._calculate_trajectory_deviation(elbow_positions)

        # Normalize by shoulder width
        normalized_deviation = avg_deviation / shoulder_width if shoulder_width > 0 else 0

        # Grade based on thresholds (lower is better)
        t = thresholds['pull_trajectory_linearity']
        if normalized_deviation <= t['excellent']:
            score = 1.0
            grade = 'excellent'
        elif normalized_deviation <= t['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(normalized_deviation, 3),
            'grade': grade
        }

    def _evaluate_com_movement(self, landmarks_data: List[Dict],
                              phases: Dict, shoulder_width: float,
                              thresholds: Dict) -> Dict:
        """
        What: Evaluate P6-3 - COM forward/backward movement restriction
        Why: Measure body stability during push-pull
        Design Decision: Calculate z-axis COM variation
        """
        # Collect COM z-positions for entire movement
        com_z_positions = []

        for frame in landmarks_data:
            try:
                left_hip = frame['landmarks'][self.LEFT_HIP]
                right_hip = frame['landmarks'][self.RIGHT_HIP]

                if left_hip['visibility'] >= 0.5 and right_hip['visibility'] >= 0.5:
                    com_z = (left_hip['z'] + right_hip['z']) / 2
                    com_z_positions.append(com_z)
            except (KeyError, IndexError, TypeError):
                continue

        if len(com_z_positions) < 3:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        # Calculate z-axis variation
        z_variation = max(com_z_positions) - min(com_z_positions)

        # Normalize by shoulder width
        normalized_variation = z_variation / shoulder_width if shoulder_width > 0 else 0

        # Grade based on thresholds (lower is better)
        t = thresholds['com_movement']
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

    def _calculate_trajectory_deviation(self, positions: List[np.ndarray]) -> float:
        """
        What: Calculate average deviation from ideal straight line
        Why: Measure trajectory linearity
        Design Decision: Use perpendicular distance from start-end line

        Args:
            positions: List of 3D position vectors

        Returns:
            Average deviation distance
        """
        if len(positions) < 3:
            return 0.0

        start_point = positions[0]
        end_point = positions[-1]

        # Vector from start to end
        line_vector = end_point - start_point
        line_length = np.linalg.norm(line_vector)

        if line_length == 0:
            return 0.0

        # Calculate deviation for each intermediate point
        deviations = []
        for point in positions[1:-1]:
            # Vector from start to point
            point_vector = point - start_point

            # Calculate perpendicular distance
            # d = |AP × AB| / |AB|
            cross_product = np.cross(point_vector, line_vector)
            deviation = np.linalg.norm(cross_product) / line_length
            deviations.append(deviation)

        return np.mean(deviations) if deviations else 0.0

    # ==================== Helper Methods: P7 Kinetic Chain ====================

    def _evaluate_push_chain_timing(self, landmarks_data: List[Dict],
                                   phases: Dict, fps: float,
                                   thresholds: Dict) -> Dict:
        """
        What: Evaluate P7-1 - push chain timing (shoulder→elbow)
        Why: Measure proximal-to-distal force transmission
        Design Decision: Detect peak velocity timing for shoulder and elbow
        """
        if 'push' not in phases or not phases['push']:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        push_phase = phases['push']
        push_data = landmarks_data[push_phase['start']:push_phase['end']]

        # Detect peak velocity frames
        shoulder_peak = self._detect_peak_z_velocity_frame(push_data, 'shoulder')
        elbow_peak = self._detect_peak_z_velocity_frame(push_data, 'elbow')

        if shoulder_peak is None or elbow_peak is None:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        # Calculate timing difference
        time_diff = abs(elbow_peak - shoulder_peak) / fps

        # Grade based on thresholds
        t = thresholds['push_chain_timing']
        if t['excellent_min'] <= time_diff <= t['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif t['good_min'] <= time_diff <= t['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(time_diff, 3),
            'grade': grade
        }

    def _evaluate_pull_chain_timing(self, landmarks_data: List[Dict],
                                   phases: Dict, fps: float,
                                   thresholds: Dict) -> Dict:
        """
        What: Evaluate P7-2 - pull chain timing (wrist→elbow)
        Why: Measure distal-to-proximal force transmission
        Design Decision: Detect peak velocity timing for wrist and elbow
        """
        if 'pull' not in phases or not phases['pull']:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        pull_phase = phases['pull']
        pull_data = landmarks_data[pull_phase['start']:pull_phase['end']]

        # Detect peak velocity frames (backward movement, so look for negative velocities)
        wrist_peak = self._detect_peak_z_velocity_frame(pull_data, 'wrist', negative=True)
        elbow_peak = self._detect_peak_z_velocity_frame(pull_data, 'elbow', negative=True)

        if wrist_peak is None or elbow_peak is None:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        # Calculate timing difference
        time_diff = abs(elbow_peak - wrist_peak) / fps

        # Grade based on thresholds
        t = thresholds['pull_chain_timing']
        if t['excellent_min'] <= time_diff <= t['excellent_max']:
            score = 1.0
            grade = 'excellent'
        elif t['good_min'] <= time_diff <= t['good_max']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(time_diff, 3),
            'grade': grade
        }

    def _evaluate_transition_efficiency(self, landmarks_data: List[Dict],
                                       phases: Dict, fps: float,
                                       thresholds: Dict) -> Dict:
        """
        What: Evaluate P7-3 - push-pull transition efficiency
        Why: Measure time between push end and pull start
        Design Decision: Calculate frame difference between phases
        """
        if 'push' not in phases or not phases['push'] or 'pull' not in phases or not phases['pull']:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        push_end = phases['push']['end']
        pull_start = phases['pull']['start']

        # If pull starts before push ends, they overlap (very efficient)
        if pull_start <= push_end:
            transition_time = 0.0
        else:
            transition_time = (pull_start - push_end) / fps

        # Grade based on thresholds (lower is better)
        t = thresholds['transition_efficiency']
        if transition_time <= t['excellent']:
            score = 1.0
            grade = 'excellent'
        elif transition_time <= t['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(transition_time, 3),
            'grade': grade
        }

    def _detect_peak_z_velocity_frame(self, phase_data: List[Dict],
                                     joint: str, negative: bool = False) -> Optional[int]:
        """
        What: Detect frame with peak z-velocity for specified joint
        Why: Identify timing of maximum joint movement
        Design Decision: Calculate z-velocity and find maximum

        Args:
            joint: 'shoulder', 'elbow', or 'wrist'
            negative: If True, look for peak negative velocity (backward)
        """
        if joint == 'shoulder':
            joint_indices = [self.LEFT_SHOULDER, self.RIGHT_SHOULDER]
        elif joint == 'elbow':
            joint_indices = [self.LEFT_ELBOW, self.RIGHT_ELBOW]
        elif joint == 'wrist':
            joint_indices = [self.LEFT_WRIST, self.RIGHT_WRIST]
        else:
            return None

        # Calculate center z-positions
        z_positions = []
        for frame in phase_data:
            try:
                left_joint = frame['landmarks'][joint_indices[0]]
                right_joint = frame['landmarks'][joint_indices[1]]

                if left_joint['visibility'] >= 0.5 and right_joint['visibility'] >= 0.5:
                    center_z = (left_joint['z'] + right_joint['z']) / 2
                    z_positions.append(center_z)
                else:
                    z_positions.append(None)
            except (KeyError, IndexError, TypeError):
                z_positions.append(None)

        # Calculate velocities
        velocities = []
        for i in range(1, len(z_positions)):
            if z_positions[i] is not None and z_positions[i-1] is not None:
                velocity = z_positions[i] - z_positions[i-1]
                velocities.append(velocity if not negative else -velocity)
            else:
                velocities.append(0.0)

        if not velocities:
            return None

        # Find peak velocity
        peak_frame = np.argmax(velocities)

        return peak_frame

    # ==================== Helper Methods: P1 Compensation Evaluation ====================

    def _evaluate_torso_lean(self, landmarks_data: List[Dict],
                            phases: Dict, thresholds: Dict) -> Dict:
        """
        What: Evaluate P1-1 - trunk forward/backward lean from vertical
        Why: Measure torso compensation during push-pull
        Design Decision: Calculate trunk angle from vertical in sagittal plane (y-z)

        CRITICAL: Measure max torso lean during push and pull phases
        """
        max_lean_angles = []

        # Collect data from both push and pull phases
        for phase_name in ['push', 'pull']:
            if phase_name not in phases or not phases[phase_name]:
                continue

            phase = phases[phase_name]
            phase_data = landmarks_data[phase['start']:phase['end']]

            for frame in phase_data:
                lean_angle = self._calculate_torso_lean_angle(frame['landmarks'])
                if lean_angle is not None:
                    max_lean_angles.append(lean_angle)

        if not max_lean_angles:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        # Use maximum lean angle (worst case)
        max_lean = max(max_lean_angles)

        # Grade based on thresholds (lower is better)
        t = thresholds['torso_lean']
        if max_lean <= t['excellent']:
            score = 1.0
            grade = 'excellent'
        elif max_lean <= t['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(max_lean, 1),
            'grade': grade
        }

    def _evaluate_shoulder_elevation(self, landmarks_data: List[Dict],
                                     phases: Dict, shoulder_width: float,
                                     thresholds: Dict) -> Dict:
        """
        What: Evaluate P1-2 - shoulder elevation asymmetry
        Why: Detect compensatory shoulder hiking
        Design Decision: Measure left-right shoulder height difference ratio

        CRITICAL: Normalized by shoulder_width to account for body size
        """
        max_elevation_diffs = []

        # Collect data from both push and pull phases
        for phase_name in ['push', 'pull']:
            if phase_name not in phases or not phases[phase_name]:
                continue

            phase = phases[phase_name]
            phase_data = landmarks_data[phase['start']:phase['end']]

            for frame in phase_data:
                try:
                    left_shoulder = frame['landmarks'][self.LEFT_SHOULDER]
                    right_shoulder = frame['landmarks'][self.RIGHT_SHOULDER]

                    # Check visibility
                    if left_shoulder['visibility'] < 0.5 or right_shoulder['visibility'] < 0.5:
                        continue

                    # Calculate shoulder height difference (absolute value)
                    height_diff = abs(left_shoulder['y'] - right_shoulder['y'])
                    max_elevation_diffs.append(height_diff)

                except (KeyError, IndexError, TypeError):
                    continue

        if not max_elevation_diffs or shoulder_width <= 0:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        # Use maximum elevation difference (worst case)
        max_elevation = max(max_elevation_diffs)

        # Normalize by shoulder width
        normalized_elevation = max_elevation / shoulder_width

        # Grade based on thresholds (lower is better)
        t = thresholds['shoulder_elevation']
        if normalized_elevation <= t['excellent']:
            score = 1.0
            grade = 'excellent'
        elif normalized_elevation <= t['good']:
            score = 0.5
            grade = 'good'
        else:
            score = 0.0
            grade = 'poor'

        return {
            'score': score,
            'value': round(normalized_elevation, 3),
            'grade': grade
        }

    def _evaluate_pelvis_tilt(self, landmarks_data: List[Dict],
                             phases: Dict, base_width: float,
                             thresholds: Dict) -> Dict:
        """
        What: Evaluate P1-3 - pelvis anterior/posterior tilt variation
        Why: Measure pelvis stability during movement
        Design Decision: Calculate pelvis height variation (stability indicator)

        CRITICAL: Normalized by base_width to account for body size
        """
        pelvis_heights = []

        # Collect data from both push and pull phases
        for phase_name in ['push', 'pull']:
            if phase_name not in phases or not phases[phase_name]:
                continue

            phase = phases[phase_name]
            phase_data = landmarks_data[phase['start']:phase['end']]

            for frame in phase_data:
                try:
                    left_hip = frame['landmarks'][self.LEFT_HIP]
                    right_hip = frame['landmarks'][self.RIGHT_HIP]

                    # Check visibility
                    if left_hip['visibility'] < 0.5 or right_hip['visibility'] < 0.5:
                        continue

                    # Calculate pelvis center height (y-coordinate)
                    pelvis_center_y = (left_hip['y'] + right_hip['y']) / 2
                    pelvis_heights.append(pelvis_center_y)

                except (KeyError, IndexError, TypeError):
                    continue

        if not pelvis_heights or base_width <= 0:
            return {'score': 0.0, 'value': None, 'grade': 'poor'}

        # Calculate variation (standard deviation of pelvis height)
        pelvis_variation = np.std(pelvis_heights)

        # Normalize by base width
        normalized_variation = pelvis_variation / base_width

        # Grade based on thresholds (lower is better)
        t = thresholds['pelvis_tilt']
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

    def _calculate_torso_lean_angle(self, landmarks: List[Dict]) -> Optional[float]:
        """
        What: Calculate torso lean angle from vertical in sagittal plane
        Why: Measure forward/backward trunk compensation
        Design Decision: Calculate angle between torso vector and vertical axis

        Returns:
            Angle in degrees (0 = perfectly vertical)

        CRITICAL: Uses shoulder center to hip center vector in y-z plane
        """
        try:
            # Get shoulder and hip landmarks
            left_shoulder = landmarks[self.LEFT_SHOULDER]
            right_shoulder = landmarks[self.RIGHT_SHOULDER]
            left_hip = landmarks[self.LEFT_HIP]
            right_hip = landmarks[self.RIGHT_HIP]

            # Check visibility
            if (left_shoulder['visibility'] < 0.5 or right_shoulder['visibility'] < 0.5 or
                left_hip['visibility'] < 0.5 or right_hip['visibility'] < 0.5):
                return None

            # Calculate shoulder center and hip center
            shoulder_center_y = (left_shoulder['y'] + right_shoulder['y']) / 2
            shoulder_center_z = (left_shoulder['z'] + right_shoulder['z']) / 2
            hip_center_y = (left_hip['y'] + right_hip['y']) / 2
            hip_center_z = (left_hip['z'] + right_hip['z']) / 2

            # Calculate torso vector (from hip to shoulder)
            torso_dy = shoulder_center_y - hip_center_y  # vertical component (negative = upward)
            torso_dz = shoulder_center_z - hip_center_z  # forward/backward component

            # Calculate angle from vertical
            # If torso_dz = 0, torso is perfectly vertical
            # Angle = arctan(horizontal_displacement / vertical_displacement)
            if abs(torso_dy) < 1e-6:
                return 90.0  # Torso is horizontal (worst case)

            lean_angle = np.degrees(np.arctan(abs(torso_dz) / abs(torso_dy)))

            return lean_angle

        except (KeyError, IndexError, TypeError, ValueError, ZeroDivisionError):
            return None
