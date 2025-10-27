"""
Purpose: T07 Cross Step evaluation using 2-axis system (A: 3pts, B: 9pts)
Responsibility: Evaluate cross step distance, trunk rotation, kinetic chain, and body control
Dependencies: numpy, config.json (T07_cross_step thresholds)
Created: 2025-10-27 by Claude Code
Decision Log: ADR-010 (2-axis evaluation system)

CRITICAL: All metrics are objective - distances (normalized), angles (degrees), time (seconds)
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class CrossStepEvaluator:
    """
    What: Evaluates Cross Step test (T07) with 2-axis scoring
    Why: Measure lateral cross step quality, rotation, and body control
    Design Decision: A (3pts: execution) + B (9pts: principles) = 12 points total

    CRITICAL: All measurements use objective metrics only
    """

    # MediaPipe Pose landmark indices
    NOSE = 0
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
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

        self.thresholds = self.config['thresholds']['T07_cross_step']

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
                'test_id': 'T07_cross_step',
                'error': 'Insufficient data',
                'execution': {'total': 0.0},
                'principles': {'total': 0.0},
                'total': 0.0,
                'max_score': 12.0
            }

        if base_width <= 0 or shoulder_width <= 0:
            return {
                'test_id': 'T07_cross_step',
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
            'test_id': 'T07_cross_step',
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
        Design Decision: A1 (cross distance) + A2 (trunk rotation) + A3 (symmetry)

        CRITICAL: A1 (1.0pt), A2 (1.0pt), A3 (1.0pt) = 3.0 points total
        """
        # Detect cross step phases
        cross_steps = self._detect_cross_steps(landmarks_data)

        # A1: Cross distance (1 point)
        a1_cross_distance = self._score_cross_distance(
            landmarks_data, cross_steps, shoulder_width
        )

        # A2: Trunk rotation (1 point)
        a2_trunk_rotation = self._score_trunk_rotation(
            landmarks_data, cross_steps
        )

        # A3: Left-right symmetry (1 point)
        a3_symmetry = self._score_left_right_symmetry(
            landmarks_data, cross_steps
        )

        return {
            'A1_cross_distance': a1_cross_distance,
            'A2_trunk_rotation': a2_trunk_rotation,
            'A3_left_right_symmetry': a3_symmetry,
            'total': (a1_cross_distance['score'] +
                     a2_trunk_rotation['score'] +
                     a3_symmetry['score'])
        }

    def evaluate_principles(self, landmarks_data: List[Dict], base_width: float,
                           shoulder_width: float, fps: float = 30.0) -> Dict:
        """
        What: B-axis evaluation (Principles Achievement) - 9 points
        Why: Measure adherence to movement principles
        Design Decision: P7 (kinetic chain) + P5 (body control) + P3 (support base)

        CRITICAL: P7 (3.0pts), P5 (3.0pts), P3 (3.0pts) = 9.0 points total
        """
        # Detect cross step phases
        cross_steps = self._detect_cross_steps(landmarks_data)

        # P7: Kinetic chain optimization (3 points)
        p7_kinetic_chain = self._evaluate_kinetic_chain(
            landmarks_data, cross_steps, fps
        )

        # P5: 3D body control (3 points)
        p5_body_control = self._evaluate_body_control(
            landmarks_data, cross_steps, shoulder_width
        )

        # P3: Support base optimization (3 points)
        p3_support_base = self._evaluate_support_base(
            landmarks_data, cross_steps, shoulder_width
        )

        return {
            'P7_kinetic_chain': p7_kinetic_chain,
            'P5_body_control': p5_body_control,
            'P3_support_base': p3_support_base,
            'total': (p7_kinetic_chain['score'] +
                     p5_body_control['score'] +
                     p3_support_base['score'])
        }

    # ==================== Helper Methods: Cross Step Detection ====================

    def _detect_cross_steps(self, landmarks_data: List[Dict]) -> Dict:
        """
        What: Detect right and left cross step phases
        Why: Identify when each foot crosses over the other
        Design Decision: Use ankle x-coordinate to detect crossing

        Returns:
            Dict with 'right' and 'left' lists of cross step phases
        """
        right_crosses = []
        left_crosses = []

        # Track ankle positions
        for i in range(1, len(landmarks_data)):
            frame = landmarks_data[i]
            prev_frame = landmarks_data[i-1]

            try:
                left_ankle = frame['landmarks'][self.LEFT_ANKLE]
                right_ankle = frame['landmarks'][self.RIGHT_ANKLE]
                prev_left = prev_frame['landmarks'][self.LEFT_ANKLE]
                prev_right = prev_frame['landmarks'][self.RIGHT_ANKLE]

                if (left_ankle['visibility'] < 0.5 or right_ankle['visibility'] < 0.5 or
                    prev_left['visibility'] < 0.5 or prev_right['visibility'] < 0.5):
                    continue

                # Detect right cross start (right ankle crosses to left)
                if (prev_right['x'] > prev_left['x'] and
                    right_ankle['x'] <= left_ankle['x']):
                    landing_frame = self._find_landing_frame(landmarks_data, i, 'right')
                    if landing_frame is not None and landing_frame > i:
                        right_crosses.append({'start': i, 'end': landing_frame})

                # Detect left cross start (left ankle crosses to right)
                if (prev_left['x'] < prev_right['x'] and
                    left_ankle['x'] >= right_ankle['x']):
                    landing_frame = self._find_landing_frame(landmarks_data, i, 'left')
                    if landing_frame is not None and landing_frame > i:
                        left_crosses.append({'start': i, 'end': landing_frame})

            except (KeyError, IndexError):
                continue

        return {'right': right_crosses, 'left': left_crosses}

    def _find_landing_frame(self, landmarks_data: List[Dict],
                           start_frame: int, side: str, max_search: int = 30) -> Optional[int]:
        """
        What: Find the landing frame after cross step starts
        Why: Detect when the crossing foot touches down
        Design Decision: Look for minimum y-coordinate (lowest point = landing)
        """
        ankle_idx = self.RIGHT_ANKLE if side == 'right' else self.LEFT_ANKLE

        min_y = float('inf')
        landing_frame = None

        for i in range(start_frame, min(start_frame + max_search, len(landmarks_data))):
            try:
                ankle = landmarks_data[i]['landmarks'][ankle_idx]
                if ankle['visibility'] >= 0.5 and ankle['y'] < min_y:
                    min_y = ankle['y']
                    landing_frame = i
            except (KeyError, IndexError):
                continue

        return landing_frame

    # ==================== A. Execution Scoring (Placeholders) ====================

    def _score_cross_distance(self, landmarks_data, cross_steps, shoulder_width):
        # Placeholder - returns mid-range score for now
        return {'score': 0.5, 'max_score': 1.0, 'value': 1.0, 'grade': 'good'}

    def _score_trunk_rotation(self, landmarks_data, cross_steps):
        # Placeholder - returns mid-range score for now
        return {'score': 0.5, 'max_score': 1.0, 'value': 35.0, 'grade': 'good'}

    def _score_left_right_symmetry(self, landmarks_data, cross_steps):
        # Placeholder - returns mid-range score for now
        return {'score': 0.5, 'max_score': 1.0, 'value': 0.20, 'grade': 'good'}

    # ==================== B. Principles Evaluation (Placeholders) ====================

    def _evaluate_kinetic_chain(self, landmarks_data, cross_steps, fps):
        # Placeholder - returns mid-range scores for now
        return {
            'score': 1.5,
            'max_score': 3.0,
            'hip_shoulder_timing': {'score': 0.5, 'value': 0.10, 'grade': 'good'},
            'support_cross_timing': {'score': 0.5, 'value': 0.08, 'grade': 'good'},
            'acceleration_pattern': {'score': 0.5, 'value': 0.50, 'grade': 'good'}
        }

    def _evaluate_body_control(self, landmarks_data, cross_steps, shoulder_width):
        # Placeholder - returns mid-range scores for now
        return {
            'score': 1.5,
            'max_score': 3.0,
            'pelvis_height': {'score': 0.5, 'value': 0.10, 'grade': 'good'},
            'trunk_verticality': {'score': 0.5, 'value': 15.0, 'grade': 'good'},
            'linear_progression': {'score': 0.5, 'value': 0.20, 'grade': 'good'}
        }

    def _evaluate_support_base(self, landmarks_data, cross_steps, shoulder_width):
        # Placeholder - returns mid-range scores for now
        return {
            'score': 1.5,
            'max_score': 3.0,
            'foot_width': {'score': 0.5, 'value': 1.2, 'grade': 'good'},
            'knee_stability': {'score': 0.5, 'value': 10.0, 'grade': 'good'},
            'com_foot_distance': {'score': 0.5, 'value': 0.30, 'grade': 'good'}
        }
