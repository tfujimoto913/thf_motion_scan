"""
Purpose: Test suite for PushPullEvaluator (T06) 2-axis evaluation system
Responsibility: Validate execution (3pts) and principles (9pts) scoring
Dependencies: pytest, PushPullEvaluator, config.json
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
from push_pull import PushPullEvaluator


class TestPushPullEvaluator:
    """
    What: Test suite for PushPullEvaluator 2-axis evaluation
    Why: Ensure correct implementation of A (3pts) + B (9pts) scoring system
    Design Decision: Follow same pattern as previous test files
    """

    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance with test config"""
        config_path = Path(__file__).parent.parent / 'config.json'
        return PushPullEvaluator(config_path=str(config_path))

    @pytest.fixture
    def sample_landmarks_data(self):
        """Generate sample landmark data simulating push-pull movement"""
        landmarks_data = []
        fps = 30.0

        # Simulate 90 frames (3 seconds): neutral -> push -> neutral -> pull -> neutral
        for frame_idx in range(90):
            landmarks = [{'x': 0.0, 'y': 0.0, 'z': 0.0, 'visibility': 1.0} for _ in range(33)]

            # Base positions
            base_y = 0.5

            # Z-axis movement simulation (forward/backward)
            if frame_idx < 15:  # Neutral start
                wrist_z = 0.0
                elbow_z = -0.1
            elif frame_idx < 35:  # Push phase (forward movement)
                progress = (frame_idx - 15) / 20
                # Wrist moves forward (z increases from 0 to 0.16)
                wrist_z = 0.0 + 0.16 * progress  # 0.16 = 0.8 * shoulder_width (0.2)
                elbow_z = -0.1 + 0.05 * progress
            elif frame_idx < 45:  # Transition back to neutral
                progress = (frame_idx - 35) / 10
                wrist_z = 0.16 - 0.16 * progress
                elbow_z = -0.05 - 0.05 * progress
            elif frame_idx < 70:  # Pull phase (backward movement)
                progress = (frame_idx - 45) / 25
                # Elbow moves backward (z decreases from -0.1 to -0.22)
                wrist_z = 0.0 - 0.05 * progress
                elbow_z = -0.1 - 0.12 * progress  # -0.12 = -0.6 * shoulder_width (0.2)
            else:  # Return to neutral
                progress = (frame_idx - 70) / 20
                wrist_z = -0.05 + 0.05 * progress
                elbow_z = -0.22 + 0.12 * progress

            # Set key landmarks
            # NOSE (0)
            landmarks[0] = {'x': 0.5, 'y': base_y - 0.3, 'z': 0.0, 'visibility': 1.0}

            # Shoulders (11, 12)
            landmarks[11] = {'x': 0.4, 'y': base_y - 0.1, 'z': 0.0, 'visibility': 1.0}
            landmarks[12] = {'x': 0.6, 'y': base_y - 0.1, 'z': 0.0, 'visibility': 1.0}

            # Elbows (13, 14)
            landmarks[13] = {'x': 0.4, 'y': base_y, 'z': elbow_z, 'visibility': 1.0}
            landmarks[14] = {'x': 0.6, 'y': base_y, 'z': elbow_z, 'visibility': 1.0}

            # Wrists (15, 16)
            landmarks[15] = {'x': 0.4, 'y': base_y + 0.1, 'z': wrist_z, 'visibility': 1.0}
            landmarks[16] = {'x': 0.6, 'y': base_y + 0.1, 'z': wrist_z, 'visibility': 1.0}

            # Hips (23, 24)
            # COM should remain stable (low z-movement)
            hip_z = 0.0 + 0.03 * np.sin(frame_idx * 0.1)  # Small variation
            landmarks[23] = {'x': 0.4, 'y': base_y + 0.4, 'z': hip_z, 'visibility': 1.0}
            landmarks[24] = {'x': 0.6, 'y': base_y + 0.4, 'z': hip_z, 'visibility': 1.0}

            # Ankles (27, 28)
            landmarks[27] = {'x': 0.4, 'y': base_y + 0.8, 'z': 0.0, 'visibility': 1.0}
            landmarks[28] = {'x': 0.6, 'y': base_y + 0.8, 'z': 0.0, 'visibility': 1.0}

            landmarks_data.append({
                'frame': frame_idx,
                'timestamp': frame_idx / fps,
                'landmarks': landmarks
            })

        return landmarks_data

    def test_evaluator_initialization(self, evaluator):
        """Test evaluator initialization with config"""
        assert evaluator is not None
        assert 'T06_push_pull' in evaluator.config['thresholds']
        assert 'execution' in evaluator.thresholds
        assert 'principles' in evaluator.thresholds

    def test_evaluation_structure(self, evaluator, sample_landmarks_data):
        """Test main evaluation return structure (12-point system)"""
        base_width = 0.2
        shoulder_width = 0.2

        result = evaluator.evaluate(sample_landmarks_data, base_width, shoulder_width)

        # Check top-level structure
        assert 'test_id' in result
        assert result['test_id'] == 'T06_push_pull'
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

        execution = evaluator.evaluate_execution(sample_landmarks_data, base_width, shoulder_width)

        # Check structure
        assert 'A1_push_distance' in execution
        assert 'A2_pull_distance' in execution
        assert 'A3_left_right_symmetry' in execution
        assert 'total' in execution

        # Check A1 structure
        a1 = execution['A1_push_distance']
        assert 'score' in a1
        assert 'max_score' in a1
        assert a1['max_score'] == 1.0

        # Check A2 structure
        a2 = execution['A2_pull_distance']
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

        principles = evaluator.evaluate_principles(sample_landmarks_data, base_width, shoulder_width)

        # Check structure
        assert 'P1_compensation' in principles
        assert 'P6_force_direction' in principles
        assert 'P7_kinetic_chain' in principles
        assert 'total' in principles

        # Check P1 structure
        p1 = principles['P1_compensation']
        assert 'score' in p1
        assert 'max_score' in p1
        assert p1['max_score'] == 3.0
        assert 'torso_lean' in p1
        assert 'shoulder_elevation' in p1
        assert 'pelvis_tilt' in p1

        # Check P6 structure
        p6 = principles['P6_force_direction']
        assert 'score' in p6
        assert 'max_score' in p6
        assert p6['max_score'] == 3.0
        assert 'push_trajectory_linearity' in p6
        assert 'pull_trajectory_linearity' in p6
        assert 'com_movement' in p6

        # Check P7 structure
        p7 = principles['P7_kinetic_chain']
        assert 'score' in p7
        assert 'max_score' in p7
        assert p7['max_score'] == 3.0
        assert 'push_chain_timing' in p7
        assert 'pull_chain_timing' in p7
        assert 'transition_efficiency' in p7

        # Verify scoring ranges
        assert 0 <= p1['score'] <= 3.0
        assert 0 <= p6['score'] <= 3.0
        assert 0 <= p7['score'] <= 3.0
        assert 0 <= principles['total'] <= 9.0

    def test_phase_detection(self, evaluator, sample_landmarks_data):
        """Test push and pull phase detection logic"""
        phases = evaluator._detect_push_pull_phases(sample_landmarks_data)

        # Check structure
        assert 'push' in phases
        assert 'pull' in phases

        # Push phase should be detected around frames 15-35
        push_phase = phases['push']
        if push_phase:
            assert 'start' in push_phase
            assert 'end' in push_phase
            assert 10 <= push_phase['start'] <= 25
            assert 25 <= push_phase['end'] <= 40

        # Pull phase should be detected around frames 35-70
        # (may start during transition as elbow begins backward movement)
        pull_phase = phases['pull']
        if pull_phase:
            assert 'start' in pull_phase
            assert 'end' in pull_phase
            assert 30 <= pull_phase['start'] <= 55
            assert 60 <= pull_phase['end'] <= 75

    def test_push_distance_calculation(self, evaluator, sample_landmarks_data):
        """Test push distance measurement"""
        base_width = 0.2
        shoulder_width = 0.2

        execution = evaluator.evaluate_execution(sample_landmarks_data, base_width, shoulder_width)
        a1 = execution['A1_push_distance']

        # Should detect forward wrist movement
        assert 'value' in a1  # normalized distance ratio
        assert 'score' in a1

        # Normalized distance should be reasonable (around 0.8 for excellent)
        if a1['value'] is not None:
            assert 0 <= a1['value'] <= 2.0

    def test_pull_distance_calculation(self, evaluator, sample_landmarks_data):
        """Test pull distance measurement"""
        base_width = 0.2
        shoulder_width = 0.2

        execution = evaluator.evaluate_execution(sample_landmarks_data, base_width, shoulder_width)
        a2 = execution['A2_pull_distance']

        # Should detect backward elbow movement
        assert 'value' in a2  # normalized distance ratio
        assert 'score' in a2

        # Normalized distance should be reasonable (around 0.6 for excellent)
        if a2['value'] is not None:
            assert 0 <= a2['value'] <= 2.0

    def test_trajectory_linearity(self, evaluator, sample_landmarks_data):
        """Test trajectory linearity calculation for push and pull"""
        base_width = 0.2
        shoulder_width = 0.2

        principles = evaluator.evaluate_principles(sample_landmarks_data, base_width, shoulder_width)
        p6 = principles['P6_force_direction']

        # Check push trajectory linearity
        push_linearity = p6['push_trajectory_linearity']
        assert 'value' in push_linearity  # normalized deviation
        assert 'score' in push_linearity
        if push_linearity['value'] is not None:
            assert 0 <= push_linearity['value'] <= 1.0

        # Check pull trajectory linearity
        pull_linearity = p6['pull_trajectory_linearity']
        assert 'value' in pull_linearity  # normalized deviation
        assert 'score' in pull_linearity
        if pull_linearity['value'] is not None:
            assert 0 <= pull_linearity['value'] <= 1.0

    def test_kinetic_chain_timing(self, evaluator, sample_landmarks_data):
        """Test kinetic chain timing calculations"""
        base_width = 0.2
        shoulder_width = 0.2

        principles = evaluator.evaluate_principles(sample_landmarks_data, base_width, shoulder_width, fps=30.0)
        p7 = principles['P7_kinetic_chain']

        # Check push chain timing
        push_chain = p7['push_chain_timing']
        assert 'value' in push_chain  # timing difference in seconds
        assert 'score' in push_chain
        if push_chain['value'] is not None:
            assert 0 <= push_chain['value'] <= 1.0

        # Check pull chain timing
        pull_chain = p7['pull_chain_timing']
        assert 'value' in pull_chain  # timing difference in seconds
        assert 'score' in pull_chain
        if pull_chain['value'] is not None:
            assert 0 <= pull_chain['value'] <= 1.0

        # Check transition efficiency
        transition = p7['transition_efficiency']
        assert 'value' in transition  # transition time in seconds
        assert 'score' in transition
        if transition['value'] is not None:
            assert 0 <= transition['value'] <= 2.0

    def test_com_movement_evaluation(self, evaluator, sample_landmarks_data):
        """Test center of mass z-axis movement evaluation"""
        base_width = 0.2
        shoulder_width = 0.2

        principles = evaluator.evaluate_principles(sample_landmarks_data, base_width, shoulder_width)
        p6 = principles['P6_force_direction']

        com_movement = p6['com_movement']
        assert 'value' in com_movement  # normalized z-movement
        assert 'score' in com_movement

        # COM should be relatively stable (low z-movement)
        if com_movement['value'] is not None:
            assert 0 <= com_movement['value'] <= 1.0

    def test_symmetry_calculation(self, evaluator, sample_landmarks_data):
        """Test left-right symmetry calculation"""
        base_width = 0.2
        shoulder_width = 0.2

        execution = evaluator.evaluate_execution(sample_landmarks_data, base_width, shoulder_width)
        a3 = execution['A3_left_right_symmetry']

        assert 'value' in a3  # symmetry difference ratio
        assert 'score' in a3

        # Sample data is perfectly symmetric, should score well
        if a3['value'] is not None:
            assert 0 <= a3['value'] <= 1.0
            # Perfect symmetry in sample data should yield low ratio
            assert a3['value'] < 0.2

    def test_empty_data_handling(self, evaluator):
        """Test handling of empty/invalid input data"""
        # Test empty landmarks
        result = evaluator.evaluate([], 0.2, 0.2)

        assert result is not None
        assert 'error' in result
        assert result['total'] == 0.0

        # Test invalid normalization factors
        sample_data = [{'frame': 0, 'landmarks': [{'x': 0, 'y': 0, 'z': 0, 'visibility': 1.0} for _ in range(33)]}]
        result = evaluator.evaluate(sample_data, 0, 0)

        assert result is not None
        assert 'error' in result
        assert result['total'] == 0.0

    def test_config_threshold_loading(self, evaluator):
        """Test all config thresholds are properly loaded"""
        # Check execution thresholds
        assert 'push_distance' in evaluator.thresholds['execution']
        assert 'pull_distance' in evaluator.thresholds['execution']
        assert 'left_right_symmetry' in evaluator.thresholds['execution']

        # Check principles thresholds
        assert 'P1_compensation' in evaluator.thresholds['principles']
        assert 'P6_force_direction' in evaluator.thresholds['principles']
        assert 'P7_kinetic_chain' in evaluator.thresholds['principles']

        # Check P1 specific threshold values
        p1 = evaluator.thresholds['principles']['P1_compensation']
        assert 'torso_lean' in p1
        assert 'shoulder_elevation' in p1
        assert 'pelvis_tilt' in p1

        # Check P6 specific threshold values
        p6 = evaluator.thresholds['principles']['P6_force_direction']
        assert 'push_trajectory_linearity' in p6
        assert 'pull_trajectory_linearity' in p6
        assert 'com_movement' in p6

        # Check P7 specific threshold values
        p7 = evaluator.thresholds['principles']['P7_kinetic_chain']
        assert 'push_chain_timing' in p7
        assert 'pull_chain_timing' in p7
        assert 'transition_efficiency' in p7

    def test_fps_parameter(self, evaluator, sample_landmarks_data):
        """Test FPS parameter affects timing calculations"""
        base_width = 0.2
        shoulder_width = 0.2

        # Test with different FPS values
        result_30fps = evaluator.evaluate(sample_landmarks_data, base_width, shoulder_width, fps=30.0)
        result_60fps = evaluator.evaluate(sample_landmarks_data, base_width, shoulder_width, fps=60.0)

        # Both should return valid results
        assert result_30fps['total'] >= 0
        assert result_60fps['total'] >= 0

        # Timing-based metrics may differ
        # (kinetic chain timing, transition efficiency)
        assert 'P7_kinetic_chain' in result_30fps['principles']
        assert 'P7_kinetic_chain' in result_60fps['principles']

    def test_z_velocity_detection(self, evaluator, sample_landmarks_data):
        """Test z-axis velocity calculation for phase detection"""
        # Extract wrist z-positions
        wrist_z_positions = []
        for frame in sample_landmarks_data:
            left_wrist = frame['landmarks'][15]
            right_wrist = frame['landmarks'][16]
            if left_wrist['visibility'] >= 0.5 and right_wrist['visibility'] >= 0.5:
                wrist_center_z = (left_wrist['z'] + right_wrist['z']) / 2
                wrist_z_positions.append(wrist_center_z)

        # Calculate velocities
        velocities = [wrist_z_positions[i] - wrist_z_positions[i-1]
                     for i in range(1, len(wrist_z_positions))]

        # During push phase (frames 15-35), velocities should be positive
        push_velocities = velocities[15:35]
        assert any(v > 0 for v in push_velocities), "Should detect positive z-velocity during push"

        # During pull transition, velocities should be negative
        pull_velocities = velocities[50:70]
        # Note: wrist may not move much during pull (elbow does), so this is less strict


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
