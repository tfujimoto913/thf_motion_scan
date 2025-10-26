"""
Purpose: Test suite for StrideMinicryEvaluator (T03) 2-axis evaluation system
Responsibility: Validate execution (3pts) and principles (9pts) scoring
Dependencies: pytest, StrideMinicryEvaluator, config.json
Created: 2025-10-25 by Claude Code
Decision Log: ADR-010 (2-axis evaluation system)

CRITICAL: All tests use objective metrics only - no subjective measurements
"""

import pytest
import json
import numpy as np
from pathlib import Path
import sys

# Add processing directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'processing' / 'evaluators'))
from stride_mimic import StrideMinicryEvaluator


class TestStrideMinicryEvaluator:
    """
    What: Test suite for StrideMinicryEvaluator 2-axis evaluation
    Why: Ensure correct implementation of A (3pts) + B (9pts) scoring system
    Design Decision: Follow same pattern as test_single_leg_squat_v2.py
    """

    @pytest.fixture
    def evaluator(self):
        """
        What: Create evaluator instance with test config
        Why: Setup for all test cases
        """
        config_path = Path(__file__).parent.parent / 'config.json'
        return StrideMinicryEvaluator(config_path=str(config_path))

    @pytest.fixture
    def sample_landmarks_data(self):
        """
        What: Generate sample landmark data for testing
        Why: Provide realistic test data with proper structure
        """
        # Create 60 frames of sample data (simulating ~2 seconds at 30fps)
        landmarks_data = []

        for frame_idx in range(60):
            # Simulate alternating support phases using sine wave
            phase = (frame_idx // 10) % 2  # Switch every 10 frames

            # Left support phase: left knee lower (higher Y value)
            # Right support phase: right knee lower (higher Y value)
            if phase == 0:  # Left support
                left_knee_y = 0.7
                right_knee_y = 0.5
            else:  # Right support
                left_knee_y = 0.5
                right_knee_y = 0.7

            # Basic landmark structure (33 landmarks)
            landmarks = [{'x': 0.0, 'y': 0.0, 'z': 0.0, 'visibility': 1.0} for _ in range(33)]

            # Set key landmarks with realistic positions
            # Shoulders (11, 12)
            landmarks[11] = {'x': 0.4, 'y': 0.3, 'z': 0.0, 'visibility': 1.0}
            landmarks[12] = {'x': 0.6, 'y': 0.3, 'z': 0.0, 'visibility': 1.0}

            # Hips (23, 24) - vary X to simulate lateral movement
            hip_offset = 0.1 * np.sin(frame_idx * 0.2)
            landmarks[23] = {'x': 0.4 + hip_offset, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}
            landmarks[24] = {'x': 0.6 + hip_offset, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}

            # Knees (25, 26) - different Y values for support phase
            landmarks[25] = {'x': 0.4, 'y': left_knee_y, 'z': 0.0, 'visibility': 1.0}
            landmarks[26] = {'x': 0.6, 'y': right_knee_y, 'z': 0.0, 'visibility': 1.0}

            # Ankles (27, 28)
            landmarks[27] = {'x': 0.4, 'y': 0.9, 'z': 0.0, 'visibility': 1.0}
            landmarks[28] = {'x': 0.6, 'y': 0.9, 'z': 0.0, 'visibility': 1.0}

            # Heels (29, 30)
            landmarks[29] = {'x': 0.4, 'y': 0.95, 'z': -0.05, 'visibility': 1.0}
            landmarks[30] = {'x': 0.6, 'y': 0.95, 'z': -0.05, 'visibility': 1.0}

            # Foot index (31, 32)
            landmarks[31] = {'x': 0.4, 'y': 0.95, 'z': 0.05, 'visibility': 1.0}
            landmarks[32] = {'x': 0.6, 'y': 0.95, 'z': 0.05, 'visibility': 1.0}

            landmarks_data.append({
                'frame': frame_idx,
                'timestamp': frame_idx / 30.0,
                'landmarks': landmarks
            })

        return landmarks_data

    def test_evaluator_initialization(self, evaluator):
        """
        What: Test evaluator initialization with config
        Why: Verify config loading and threshold setup
        """
        assert evaluator is not None
        assert 'T03_stride_mimic' in evaluator.config['thresholds']
        assert 'execution' in evaluator.thresholds
        assert 'principles' in evaluator.thresholds

    def test_evaluation_structure(self, evaluator, sample_landmarks_data):
        """
        What: Test main evaluation return structure
        Why: Verify 12-point structure (A: 3pts, B: 9pts)
        """
        base_width = 0.2
        shoulder_width = 0.2

        result = evaluator.evaluate(sample_landmarks_data, base_width, shoulder_width)

        # Check top-level structure
        assert 'test_id' in result
        assert result['test_id'] == 'T03_stride_mimic'
        assert 'execution' in result
        assert 'principles' in result
        assert 'total' in result
        assert 'max_score' in result

        # Check max scores
        assert result['max_score'] == 12.0

        # Check nested structures
        assert 'total' in result['execution']
        assert 'total' in result['principles']

        # Verify total calculation
        execution_total = result['execution']['total']
        principles_total = result['principles']['total']
        assert result['total'] == execution_total + principles_total

        # Score ranges
        assert 0 <= execution_total <= 3.0
        assert 0 <= principles_total <= 9.0
        assert 0 <= result['total'] <= 12.0

    def test_execution_evaluation(self, evaluator, sample_landmarks_data):
        """
        What: Test A evaluation (execution) structure and scoring
        Why: Verify 3-point execution scoring (A1: 1.5pts, A2: 1.5pts)
        """
        shoulder_width = 0.2

        execution = evaluator.evaluate_execution(sample_landmarks_data, shoulder_width)

        # Check structure
        assert 'A1_movement_range' in execution
        assert 'A2_bilateral_symmetry' in execution
        assert 'total' in execution

        # Check A1 structure
        a1 = execution['A1_movement_range']
        assert 'score' in a1
        assert 'max_score' in a1
        assert a1['max_score'] == 1.5
        assert 'knee_flexion' in a1
        assert 'hip_abduction' in a1

        # Check A2 structure
        a2 = execution['A2_bilateral_symmetry']
        assert 'score' in a2
        assert 'max_score' in a2
        assert a2['max_score'] == 1.5
        assert 'knee_angle_diff' in a2
        assert 'hip_abduction_diff' in a2

        # Verify scoring ranges
        assert 0 <= a1['score'] <= 1.5
        assert 0 <= a2['score'] <= 1.5
        assert 0 <= execution['total'] <= 3.0

    def test_principles_evaluation(self, evaluator, sample_landmarks_data):
        """
        What: Test B evaluation (principles) structure and scoring
        Why: Verify 9-point principles scoring (P3: 3pts, P2: 3pts, P4: 3pts)
        """
        base_width = 0.2
        shoulder_width = 0.2

        principles = evaluator.evaluate_principles(sample_landmarks_data, base_width, shoulder_width)

        # Check structure
        assert 'P3_support_base' in principles
        assert 'P2_center_of_mass' in principles
        assert 'P4_joint_angles' in principles
        assert 'total' in principles

        # Check P3 structure
        p3 = principles['P3_support_base']
        assert 'score' in p3
        assert 'max_score' in p3
        assert p3['max_score'] == 3.0
        assert 'ankle_stability' in p3
        assert 'kick_leg_abduction' in p3
        assert 'support_time_symmetry' in p3

        # Check P2 structure
        p2 = principles['P2_center_of_mass']
        assert 'score' in p2
        assert 'max_score' in p2
        assert p2['max_score'] == 3.0
        assert 'height_stability' in p2
        assert 'forward_movement' in p2
        assert 'projection_offset' in p2

        # Check P4 structure
        p4 = principles['P4_joint_angles']
        assert 'score' in p4
        assert 'max_score' in p4
        assert p4['max_score'] == 3.0
        assert 'support_knee' in p4
        assert 'hip_extension' in p4
        assert 'trunk_lean' in p4

        # Verify scoring ranges
        assert 0 <= p3['score'] <= 3.0
        assert 0 <= p2['score'] <= 3.0
        assert 0 <= p4['score'] <= 3.0
        assert 0 <= principles['total'] <= 9.0

    def test_support_phase_detection(self, evaluator, sample_landmarks_data):
        """
        What: Test support phase detection logic
        Why: Verify correct identification of left/right support phases
        """
        phases = evaluator._detect_support_phases(sample_landmarks_data)

        # Should detect multiple phases in 60 frames
        assert len(phases) > 0

        # Each phase should have required fields
        for phase in phases:
            assert 'side' in phase
            assert 'start' in phase
            assert 'end' in phase
            assert phase['side'] in ['left', 'right']
            assert phase['start'] < phase['end']
            assert phase['end'] - phase['start'] >= 5  # Minimum duration

    def test_knee_angle_calculation(self, evaluator):
        """
        What: Test knee angle calculation using 3D vectors
        Why: Verify correct angle calculation between HIP→KNEE→ANKLE
        """
        # Create test landmarks with known angles
        landmarks = [{'x': 0.0, 'y': 0.0, 'z': 0.0, 'visibility': 1.0} for _ in range(33)]

        # Left leg: 90-degree knee angle
        landmarks[23] = {'x': 0.4, 'y': 0.3, 'z': 0.0, 'visibility': 1.0}  # LEFT_HIP
        landmarks[25] = {'x': 0.4, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}  # LEFT_KNEE
        landmarks[27] = {'x': 0.6, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}  # LEFT_ANKLE (perpendicular)

        angle = evaluator._calculate_knee_angle(landmarks, 'left')

        assert angle is not None
        # Should be approximately 90 degrees
        assert 85 <= angle <= 95

    def test_hip_abduction_width_calculation(self, evaluator, sample_landmarks_data):
        """
        What: Test hip abduction width calculation
        Why: Verify correct measurement of max left-right hip X-distance
        """
        width = evaluator._calculate_hip_abduction_width(sample_landmarks_data)

        assert width > 0
        # Should be reasonable (around 0.2 based on sample data)
        assert 0.1 <= width <= 0.5

    def test_ankle_stability_calculation(self, evaluator, sample_landmarks_data):
        """
        What: Test ankle stability calculation (std dev)
        Why: Verify ankle angle variation measurement during support phase
        """
        # Extract single support phase
        phase_data = sample_landmarks_data[0:10]

        stability = evaluator._calculate_ankle_stability(phase_data, 'left')

        # Should return a value (or None if insufficient data)
        if stability is not None:
            assert stability >= 0
            # Std dev should be reasonable
            assert stability < 180

    def test_empty_data_handling(self, evaluator):
        """
        What: Test handling of empty/invalid input data
        Why: Verify graceful error handling (no exceptions)
        """
        # Test empty landmarks
        result = evaluator.evaluate([], 0.2, 0.2)

        assert result is not None
        assert 'error' in result
        assert result['total'] == 0.0

        # Test invalid normalization factors
        sample_data = [{'frame': 0, 'landmarks': [{'x': 0, 'y': 0, 'z': 0} for _ in range(33)]}]
        result = evaluator.evaluate(sample_data, 0, 0)

        assert result is not None
        assert 'error' in result
        assert result['total'] == 0.0

    def test_config_threshold_loading(self, evaluator):
        """
        What: Test all config thresholds are properly loaded
        Why: Verify no hardcoded values, all from config.json
        """
        # Check execution thresholds
        assert 'movement_range' in evaluator.thresholds['execution']
        assert 'bilateral_symmetry' in evaluator.thresholds['execution']

        # Check principles thresholds
        assert 'P3_support_base' in evaluator.thresholds['principles']
        assert 'P2_center_of_mass' in evaluator.thresholds['principles']
        assert 'P4_joint_angles' in evaluator.thresholds['principles']

        # Check specific threshold values
        movement_range = evaluator.thresholds['execution']['movement_range']
        assert 'knee_flexion' in movement_range
        assert 'hip_abduction' in movement_range

        p3 = evaluator.thresholds['principles']['P3_support_base']
        assert 'ankle_stability' in p3
        assert 'kick_leg_abduction' in p3
        assert 'support_time_symmetry' in p3

    def test_scoring_grade_system(self, evaluator, sample_landmarks_data):
        """
        What: Test scoring grade system (excellent/good/fair/poor)
        Why: Verify correct grade assignment based on thresholds
        """
        shoulder_width = 0.2

        execution = evaluator.evaluate_execution(sample_landmarks_data, shoulder_width)

        # Check knee flexion has grade
        knee_flexion = execution['A1_movement_range']['knee_flexion']
        assert 'grade' in knee_flexion
        assert knee_flexion['grade'] in ['excellent', 'good', 'fair']

        # Check hip abduction has grade
        hip_abduction = execution['A1_movement_range']['hip_abduction']
        assert 'grade' in hip_abduction
        assert hip_abduction['grade'] in ['excellent', 'good', 'fair']

    def test_real_data_integration(self):
        """
        What: Integration test with real landmark data from fixture
        Why: Verify end-to-end evaluation with actual test data
        """
        # Load real test data if available
        fixtures_dir = Path(__file__).parent / 'fixtures'
        fixture_file = fixtures_dir / 'sample_landmarks.json'

        if not fixture_file.exists():
            pytest.skip("Real landmark data fixture not available")

        with open(fixture_file, 'r') as f:
            data = json.load(f)

        # Extract required data
        landmarks_data = data.get('landmarks', [])

        if not landmarks_data:
            pytest.skip("No landmark data in fixture")

        # Calculate normalization factors (simple approximation)
        first_frame = landmarks_data[0]['landmarks']
        shoulder_width = abs(first_frame[12]['x'] - first_frame[11]['x'])
        pelvis_width = abs(first_frame[24]['x'] - first_frame[23]['x'])
        base_width = max(shoulder_width, pelvis_width)

        # Run evaluation
        config_path = Path(__file__).parent.parent / 'config.json'
        evaluator = StrideMinicryEvaluator(config_path=str(config_path))

        result = evaluator.evaluate(landmarks_data, base_width, shoulder_width)

        # Verify result structure
        assert result is not None
        assert 'total' in result
        assert 0 <= result['total'] <= 12.0

        # Print results for manual inspection
        print("\n=== Real Data Evaluation Results ===")
        print(f"Total Score: {result['total']:.2f} / 12.0")
        print(f"A. Execution: {result['execution']['total']:.2f} / 3.0")
        print(f"  - Movement Range: {result['execution']['A1_movement_range']['score']:.2f}")
        print(f"  - Bilateral Symmetry: {result['execution']['A2_bilateral_symmetry']['score']:.2f}")
        print(f"B. Principles: {result['principles']['total']:.2f} / 9.0")
        print(f"  - P3 Support Base: {result['principles']['P3_support_base']['score']:.2f}")
        print(f"  - P2 Center of Mass: {result['principles']['P2_center_of_mass']['score']:.2f}")
        print(f"  - P4 Joint Angles: {result['principles']['P4_joint_angles']['score']:.2f}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
