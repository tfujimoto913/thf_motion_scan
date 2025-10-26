"""
Purpose: Test suite for UpperBodySwingEvaluator (T05) 2-axis evaluation system
Responsibility: Validate execution (3pts) and principles (9pts) scoring
Dependencies: pytest, UpperBodySwingEvaluator, config.json
Created: 2025-10-27 by Claude Code
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
from upper_body_swing import UpperBodySwingEvaluator


class TestUpperBodySwingEvaluator:
    """
    What: Test suite for UpperBodySwingEvaluator 2-axis evaluation
    Why: Ensure correct implementation of A (3pts) + B (9pts) scoring system
    Design Decision: Follow same pattern as previous test files
    """

    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance with test config"""
        config_path = Path(__file__).parent.parent / 'config.json'
        return UpperBodySwingEvaluator(config_path=str(config_path))

    @pytest.fixture
    def sample_landmarks_data(self):
        """Generate sample landmark data simulating upper body swing"""
        landmarks_data = []
        fps = 30.0

        # Simulate 90 frames (3 seconds): standing → swing cycles
        for frame_idx in range(90):
            landmarks = [{'x': 0.0, 'y': 0.0, 'z': 0.0, 'visibility': 1.0} for _ in range(33)]

            # Simulate swing motion using sine wave
            # Period = 30 frames (1 second per cycle)
            t = frame_idx / 30.0
            swing_angle = 30 * np.sin(2 * np.pi * t)  # ±30 degrees rotation

            # Convert rotation to shoulder positions (horizontal plane)
            rotation_rad = np.radians(swing_angle)
            shoulder_width_base = 0.2

            # NOSE (0)
            landmarks[0] = {'x': 0.5, 'y': 0.1, 'z': 0.0, 'visibility': 1.0}

            # Shoulders (11, 12) - rotate in horizontal plane
            landmarks[11] = {
                'x': 0.5 - shoulder_width_base/2 * np.cos(rotation_rad),
                'y': 0.3,
                'z': -shoulder_width_base/2 * np.sin(rotation_rad),
                'visibility': 1.0
            }
            landmarks[12] = {
                'x': 0.5 + shoulder_width_base/2 * np.cos(rotation_rad),
                'y': 0.3,
                'z': shoulder_width_base/2 * np.sin(rotation_rad),
                'visibility': 1.0
            }

            # Elbows (13, 14) - move with swing
            elbow_offset = 0.25
            landmarks[13] = {
                'x': landmarks[11]['x'] - elbow_offset * np.sin(rotation_rad),
                'y': 0.5,
                'z': landmarks[11]['z'] + elbow_offset * np.cos(rotation_rad),
                'visibility': 1.0
            }
            landmarks[14] = {
                'x': landmarks[12]['x'] + elbow_offset * np.sin(rotation_rad),
                'y': 0.5,
                'z': landmarks[12]['z'] - elbow_offset * np.cos(rotation_rad),
                'visibility': 1.0
            }

            # Wrists (15, 16) - larger amplitude than elbows
            wrist_offset = 0.4
            landmarks[15] = {
                'x': landmarks[11]['x'] - wrist_offset * np.sin(rotation_rad),
                'y': 0.6,
                'z': landmarks[11]['z'] + wrist_offset * np.cos(rotation_rad),
                'visibility': 1.0
            }
            landmarks[16] = {
                'x': landmarks[12]['x'] + wrist_offset * np.sin(rotation_rad),
                'y': 0.6,
                'z': landmarks[12]['z'] - wrist_offset * np.cos(rotation_rad),
                'visibility': 1.0
            }

            # Hips (23, 24) - stable
            landmarks[23] = {'x': 0.4, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}
            landmarks[24] = {'x': 0.6, 'y': 0.5, 'z': 0.0, 'visibility': 1.0}

            # Ankles (27, 28)
            landmarks[27] = {'x': 0.4, 'y': 0.9, 'z': 0.0, 'visibility': 1.0}
            landmarks[28] = {'x': 0.6, 'y': 0.9, 'z': 0.0, 'visibility': 1.0}

            landmarks_data.append({
                'frame': frame_idx,
                'timestamp': frame_idx / fps,
                'landmarks': landmarks
            })

        return landmarks_data

    def test_evaluator_initialization(self, evaluator):
        """Test evaluator initialization with config"""
        assert evaluator is not None
        assert 'T05_upper_body_swing' in evaluator.config['thresholds']
        assert 'execution' in evaluator.thresholds
        assert 'principles' in evaluator.thresholds

    def test_evaluation_structure(self, evaluator, sample_landmarks_data):
        """Test main evaluation return structure (12-point system)"""
        base_width = 0.2
        shoulder_width = 0.2
        body_height = 0.8

        result = evaluator.evaluate(sample_landmarks_data, base_width, shoulder_width, body_height)

        # Check top-level structure
        assert 'test_id' in result
        assert result['test_id'] == 'T05_upper_body_swing'
        assert 'execution' in result
        assert 'principles' in result
        assert 'total' in result
        assert 'max_score' in result
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
        """Test A evaluation (execution) structure and scoring"""
        base_width = 0.2
        shoulder_width = 0.2
        body_height = 0.8

        execution = evaluator.evaluate_execution(sample_landmarks_data, base_width, shoulder_width, body_height)

        # Check structure
        assert 'A1_trunk_rotation_range' in execution
        assert 'A2_arm_swing_range' in execution
        assert 'A3_left_right_symmetry' in execution
        assert 'total' in execution

        # Check A1 structure
        a1 = execution['A1_trunk_rotation_range']
        assert 'score' in a1
        assert 'max_score' in a1
        assert a1['max_score'] == 1.0

        # Check A2 structure
        a2 = execution['A2_arm_swing_range']
        assert 'score' in a2
        assert 'max_score' in a2
        assert a2['max_score'] == 1.0

        # Check A3 structure
        a3 = execution['A3_left_right_symmetry']
        assert 'score' in a3
        assert 'max_score' in a3
        assert a3['max_score'] == 1.0

        # Verify scoring ranges
        assert 0 <= a1['score'] <= 1.0
        assert 0 <= a2['score'] <= 1.0
        assert 0 <= a3['score'] <= 1.0
        assert 0 <= execution['total'] <= 3.0

    def test_principles_evaluation(self, evaluator, sample_landmarks_data):
        """Test B evaluation (principles) structure and scoring"""
        base_width = 0.2
        shoulder_width = 0.2
        body_height = 0.8

        principles = evaluator.evaluate_principles(sample_landmarks_data, base_width, shoulder_width, body_height)

        # Check structure
        assert 'P7_kinetic_chain' in principles
        assert 'P4_joint_angles' in principles
        assert 'P6_force_direction' in principles
        assert 'total' in principles

        # Check P7 structure
        p7 = principles['P7_kinetic_chain']
        assert 'score' in p7
        assert 'max_score' in p7
        assert p7['max_score'] == 3.0
        assert 'hip_shoulder_timing' in p7
        assert 'shoulder_elbow_timing' in p7
        assert 'elbow_wrist_timing' in p7

        # Check P4 structure
        p4 = principles['P4_joint_angles']
        assert 'score' in p4
        assert 'max_score' in p4
        assert p4['max_score'] == 3.0
        assert 'shoulder_rom' in p4
        assert 'elbow_extension' in p4
        assert 'trunk_lateral_flexion' in p4

        # Check P6 structure
        p6 = principles['P6_force_direction']
        assert 'score' in p6
        assert 'max_score' in p6
        assert p6['max_score'] == 3.0
        assert 'wrist_horizontality' in p6
        assert 'com_stability' in p6
        assert 'trajectory_reproducibility' in p6

        # Verify scoring ranges
        assert 0 <= p7['score'] <= 3.0
        assert 0 <= p4['score'] <= 3.0
        assert 0 <= p6['score'] <= 3.0
        assert 0 <= principles['total'] <= 9.0

    def test_swing_cycle_detection(self, evaluator, sample_landmarks_data):
        """Test swing cycle detection logic"""
        cycles = evaluator._detect_swing_cycles(sample_landmarks_data)

        # Should detect multiple cycles in 90 frames
        assert len(cycles) > 0

        # Each cycle should have required fields
        for cycle in cycles:
            assert 'start' in cycle
            assert 'end' in cycle
            assert 'direction' in cycle
            assert cycle['direction'] in ['left', 'right']
            assert cycle['start'] < cycle['end']
            assert cycle['end'] - cycle['start'] >= 10  # Minimum duration

    def test_trunk_rotation_angle(self, evaluator, sample_landmarks_data):
        """Test trunk rotation angle calculation"""
        # Test a frame with known rotation
        frame_landmarks = sample_landmarks_data[7]['landmarks']  # Should be at ~30 degrees

        rotation_angle = evaluator._calculate_trunk_rotation_angle(frame_landmarks)

        assert rotation_angle is not None
        # Should detect some rotation (not exactly 0)
        assert abs(rotation_angle) > 5  # At least 5 degrees

    def test_wrist_trajectory_length(self, evaluator, sample_landmarks_data):
        """Test wrist trajectory length calculation"""
        # Take a cycle of frames
        cycle_data = sample_landmarks_data[0:30]

        left_length = evaluator._calculate_wrist_trajectory_length(cycle_data, 'left')
        right_length = evaluator._calculate_wrist_trajectory_length(cycle_data, 'right')

        assert left_length is not None
        assert right_length is not None
        assert left_length > 0
        assert right_length > 0

    def test_shoulder_angle_calculation(self, evaluator, sample_landmarks_data):
        """Test shoulder angle calculation"""
        frame_landmarks = sample_landmarks_data[15]['landmarks']

        left_angle = evaluator._calculate_shoulder_angle(frame_landmarks, 'left')
        right_angle = evaluator._calculate_shoulder_angle(frame_landmarks, 'right')

        assert left_angle is not None
        assert right_angle is not None
        assert 0 <= left_angle <= 180
        assert 0 <= right_angle <= 180

    def test_elbow_angle_calculation(self, evaluator, sample_landmarks_data):
        """Test elbow angle calculation"""
        frame_landmarks = sample_landmarks_data[15]['landmarks']

        left_angle = evaluator._calculate_elbow_angle(frame_landmarks, 'left')
        right_angle = evaluator._calculate_elbow_angle(frame_landmarks, 'right')

        assert left_angle is not None
        assert right_angle is not None
        assert 0 <= left_angle <= 180
        assert 0 <= right_angle <= 180

    def test_empty_data_handling(self, evaluator):
        """Test handling of empty/invalid input data"""
        # Test empty landmarks
        result = evaluator.evaluate([], 0.2, 0.2, 0.8)

        assert result is not None
        assert 'error' in result
        assert result['total'] == 0.0

        # Test invalid normalization factors
        sample_data = [{'frame': 0, 'landmarks': [{'x': 0, 'y': 0, 'z': 0} for _ in range(33)]}]
        result = evaluator.evaluate(sample_data, 0, 0, 0)

        assert result is not None
        assert 'error' in result
        assert result['total'] == 0.0

    def test_config_threshold_loading(self, evaluator):
        """Test all config thresholds are properly loaded"""
        # Check execution thresholds
        assert 'trunk_rotation_range' in evaluator.thresholds['execution']
        assert 'arm_swing_range' in evaluator.thresholds['execution']
        assert 'left_right_symmetry' in evaluator.thresholds['execution']

        # Check principles thresholds
        assert 'P7_kinetic_chain' in evaluator.thresholds['principles']
        assert 'P4_joint_angles' in evaluator.thresholds['principles']
        assert 'P6_force_direction' in evaluator.thresholds['principles']

        # Check specific threshold values
        p7 = evaluator.thresholds['principles']['P7_kinetic_chain']
        assert 'hip_shoulder_timing' in p7
        assert 'shoulder_elbow_timing' in p7
        assert 'elbow_wrist_timing' in p7

        p4 = evaluator.thresholds['principles']['P4_joint_angles']
        assert 'shoulder_rom' in p4
        assert 'elbow_extension' in p4
        assert 'trunk_lateral_flexion' in p4

    def test_body_height_estimation(self, evaluator, sample_landmarks_data):
        """Test body height estimation from standing frames"""
        body_height = evaluator._estimate_body_height(sample_landmarks_data)

        assert body_height is not None
        assert body_height > 0
        # Should be reasonable (around 0.8 based on sample data)
        assert 0.5 <= body_height <= 1.5

    def test_trunk_lateral_flexion_calculation(self, evaluator, sample_landmarks_data):
        """Test trunk lateral flexion angle calculation"""
        frame_landmarks = sample_landmarks_data[15]['landmarks']

        flexion_angle = evaluator._calculate_trunk_lateral_flexion_angle(frame_landmarks)

        assert flexion_angle is not None
        assert 0 <= flexion_angle <= 90  # Should be small for upright posture

    def test_fps_parameter(self, evaluator, sample_landmarks_data):
        """Test FPS parameter affects timing calculations"""
        base_width = 0.2
        shoulder_width = 0.2
        body_height = 0.8

        # Test with different FPS values
        result_30fps = evaluator.evaluate(sample_landmarks_data, base_width, shoulder_width, body_height, fps=30.0)
        result_60fps = evaluator.evaluate(sample_landmarks_data, base_width, shoulder_width, body_height, fps=60.0)

        # Both should return valid results
        assert result_30fps['total'] >= 0
        assert result_60fps['total'] >= 0

        # Timing-based metrics may differ (kinetic chain timing)
        assert 'P7_kinetic_chain' in result_30fps['principles']
        assert 'P7_kinetic_chain' in result_60fps['principles']

    def test_real_data_integration(self):
        """Integration test with real landmark data from fixture"""
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

        # Calculate normalization factors
        first_frame = landmarks_data[0]['landmarks']
        shoulder_width = abs(first_frame[12]['x'] - first_frame[11]['x'])
        pelvis_width = abs(first_frame[24]['x'] - first_frame[23]['x'])
        base_width = max(shoulder_width, pelvis_width)

        # Estimate body height
        config_path = Path(__file__).parent.parent / 'config.json'
        evaluator = UpperBodySwingEvaluator(config_path=str(config_path))
        body_height = evaluator._estimate_body_height(landmarks_data)

        # Run evaluation
        result = evaluator.evaluate(landmarks_data, base_width, shoulder_width, body_height)

        # Verify result structure
        assert result is not None
        assert 'total' in result
        assert 0 <= result['total'] <= 12.0

        # Print results for manual inspection
        print("\n=== Real Data Evaluation Results ===")
        print(f"Total Score: {result['total']:.2f} / 12.0")
        print(f"A. Execution: {result['execution']['total']:.2f} / 3.0")
        print(f"  - Trunk Rotation Range: {result['execution']['A1_trunk_rotation_range']['score']:.2f}")
        print(f"  - Arm Swing Range: {result['execution']['A2_arm_swing_range']['score']:.2f}")
        print(f"  - Left-Right Symmetry: {result['execution']['A3_left_right_symmetry']['score']:.2f}")
        print(f"B. Principles: {result['principles']['total']:.2f} / 9.0")
        print(f"  - P7 Kinetic Chain: {result['principles']['P7_kinetic_chain']['score']:.2f}")
        print(f"  - P4 Joint Angles: {result['principles']['P4_joint_angles']['score']:.2f}")
        print(f"  - P6 Force Direction: {result['principles']['P6_force_direction']['score']:.2f}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
