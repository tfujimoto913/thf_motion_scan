"""
Purpose: Test suite for JumpLandingEvaluator (T04) 2-axis evaluation system
Responsibility: Validate execution (3pts) and principles (9pts) scoring
Dependencies: pytest, JumpLandingEvaluator, config.json
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
from jump_landing import JumpLandingEvaluator


class TestJumpLandingEvaluator:
    """
    What: Test suite for JumpLandingEvaluator 2-axis evaluation
    Why: Ensure correct implementation of A (3pts) + B (9pts) scoring system
    Design Decision: Follow same pattern as previous test files
    """

    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance with test config"""
        config_path = Path(__file__).parent.parent / 'config.json'
        return JumpLandingEvaluator(config_path=str(config_path))

    @pytest.fixture
    def sample_landmarks_data(self):
        """Generate sample landmark data simulating jump and landing"""
        landmarks_data = []
        fps = 30.0

        # Simulate 90 frames (3 seconds): standing -> jump -> airborne -> landing -> stabilization
        for frame_idx in range(90):
            landmarks = [{'x': 0.0, 'y': 0.0, 'z': 0.0, 'visibility': 1.0} for _ in range(33)]

            # Phase simulation
            if frame_idx < 10:  # Standing phase
                hip_y = 0.5
                ankle_y = 0.9
            elif frame_idx < 20:  # Jump preparation (squat)
                progress = (frame_idx - 10) / 10
                hip_y = 0.5 + 0.1 * progress
                ankle_y = 0.9
            elif frame_idx < 40:  # Airborne phase
                progress = (frame_idx - 20) / 20
                # Parabolic trajectory
                hip_y = 0.6 - 0.2 * (1 - (progress - 0.5)**2 * 4)
                ankle_y = hip_y + 0.3
            elif frame_idx < 55:  # Landing phase
                progress = (frame_idx - 40) / 15
                hip_y = 0.4 + 0.15 * progress
                ankle_y = 0.9
            else:  # Stabilization
                hip_y = 0.55
                ankle_y = 0.9

            # Set key landmarks
            # NOSE (0)
            landmarks[0] = {'x': 0.5, 'y': hip_y - 0.5, 'z': 0.0, 'visibility': 1.0}

            # Shoulders (11, 12)
            landmarks[11] = {'x': 0.4, 'y': hip_y - 0.2, 'z': 0.0, 'visibility': 1.0}
            landmarks[12] = {'x': 0.6, 'y': hip_y - 0.2, 'z': 0.0, 'visibility': 1.0}

            # Hips (23, 24)
            landmarks[23] = {'x': 0.4, 'y': hip_y, 'z': 0.0, 'visibility': 1.0}
            landmarks[24] = {'x': 0.6, 'y': hip_y, 'z': 0.0, 'visibility': 1.0}

            # Knees (25, 26)
            knee_offset = 0.2 if frame_idx >= 40 and frame_idx < 55 else 0.15
            landmarks[25] = {'x': 0.4, 'y': hip_y + knee_offset, 'z': 0.0, 'visibility': 1.0}
            landmarks[26] = {'x': 0.6, 'y': hip_y + knee_offset, 'z': 0.0, 'visibility': 1.0}

            # Ankles (27, 28)
            landmarks[27] = {'x': 0.4, 'y': ankle_y, 'z': 0.0, 'visibility': 1.0}
            landmarks[28] = {'x': 0.6, 'y': ankle_y, 'z': 0.0, 'visibility': 1.0}

            # Foot index (31, 32)
            landmarks[31] = {'x': 0.4, 'y': ankle_y + 0.05, 'z': 0.05, 'visibility': 1.0}
            landmarks[32] = {'x': 0.6, 'y': ankle_y + 0.05, 'z': 0.05, 'visibility': 1.0}

            landmarks_data.append({
                'frame': frame_idx,
                'timestamp': frame_idx / fps,
                'landmarks': landmarks
            })

        return landmarks_data

    def test_evaluator_initialization(self, evaluator):
        """Test evaluator initialization with config"""
        assert evaluator is not None
        assert 'T04_jump_landing' in evaluator.config['thresholds']
        assert 'execution' in evaluator.thresholds
        assert 'principles' in evaluator.thresholds

    def test_evaluation_structure(self, evaluator, sample_landmarks_data):
        """Test main evaluation return structure (12-point system)"""
        base_width = 0.2
        shoulder_width = 0.2

        result = evaluator.evaluate(sample_landmarks_data, base_width, shoulder_width)

        # Check top-level structure
        assert 'test_id' in result
        assert result['test_id'] == 'T04_jump_landing'
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
        assert 'A1_jump_height' in execution
        assert 'A2_landing_timing_sync' in execution
        assert 'A3_posture_stability' in execution
        assert 'total' in execution

        # Check A1 structure
        a1 = execution['A1_jump_height']
        assert 'score' in a1
        assert 'max_score' in a1
        assert a1['max_score'] == 1.0

        # Check A2 structure
        a2 = execution['A2_landing_timing_sync']
        assert 'score' in a2
        assert 'max_score' in a2
        assert a2['max_score'] == 1.0

        # Check A3 structure
        a3 = execution['A3_posture_stability']
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
        assert 'P2_center_of_mass' in principles
        assert 'P4_joint_angles' in principles
        assert 'P1_joint_coordination' in principles
        assert 'total' in principles

        # Check P2 structure
        p2 = principles['P2_center_of_mass']
        assert 'score' in p2
        assert 'max_score' in p2
        assert p2['max_score'] == 3.0
        assert 'descent_control' in p2
        assert 'horizontal_position' in p2
        assert 'height_maintenance' in p2

        # Check P4 structure
        p4 = principles['P4_joint_angles']
        assert 'score' in p4
        assert 'max_score' in p4
        assert p4['max_score'] == 3.0
        assert 'knee_flexion' in p4
        assert 'hip_flexion' in p4
        assert 'ankle_angle' in p4

        # Check P1 structure
        p1 = principles['P1_joint_coordination']
        assert 'score' in p1
        assert 'max_score' in p1
        assert p1['max_score'] == 3.0
        assert 'ankle_knee_timing' in p1
        assert 'knee_hip_timing' in p1
        assert 'coordination_consistency' in p1

        # Verify scoring ranges
        assert 0 <= p2['score'] <= 3.0
        assert 0 <= p4['score'] <= 3.0
        assert 0 <= p1['score'] <= 3.0
        assert 0 <= principles['total'] <= 9.0

    def test_landing_detection(self, evaluator, sample_landmarks_data):
        """Test landing frame detection logic"""
        # Detect landing for left foot
        landing_frame = evaluator._detect_landing_frame(sample_landmarks_data, 'left')

        # Should detect landing somewhere between frame 35-45 based on sample data
        assert landing_frame is not None
        assert 35 <= landing_frame <= 50

    def test_body_height_estimation(self, evaluator, sample_landmarks_data):
        """Test body height estimation from standing frames"""
        standing_frames = sample_landmarks_data[:5]
        body_height = evaluator._estimate_body_height(standing_frames)

        assert body_height is not None
        assert body_height > 0
        # Should be reasonable (roughly 0.9 based on sample data)
        assert 0.5 <= body_height <= 1.5

    def test_joint_angle_calculations(self, evaluator, sample_landmarks_data):
        """Test knee, hip, and ankle angle calculations"""
        frame_landmarks = sample_landmarks_data[50]['landmarks']  # Landing phase

        # Knee angle
        knee_angle = evaluator._calculate_knee_angle(frame_landmarks, 'left')
        assert knee_angle is not None
        assert 0 <= knee_angle <= 180

        # Hip angle
        hip_angle = evaluator._calculate_hip_angle(frame_landmarks, 'left')
        assert hip_angle is not None
        assert 0 <= hip_angle <= 180

        # Ankle angle
        ankle_angle = evaluator._calculate_ankle_angle(frame_landmarks, 'left')
        assert ankle_angle is not None
        assert 0 <= ankle_angle <= 180

    def test_empty_data_handling(self, evaluator):
        """Test handling of empty/invalid input data"""
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
        """Test all config thresholds are properly loaded"""
        # Check execution thresholds
        assert 'jump_height' in evaluator.thresholds['execution']
        assert 'landing_timing_sync' in evaluator.thresholds['execution']
        assert 'posture_stability' in evaluator.thresholds['execution']

        # Check principles thresholds
        assert 'P2_center_of_mass' in evaluator.thresholds['principles']
        assert 'P4_joint_angles' in evaluator.thresholds['principles']
        assert 'P1_joint_coordination' in evaluator.thresholds['principles']

        # Check specific threshold values
        p2 = evaluator.thresholds['principles']['P2_center_of_mass']
        assert 'descent_control' in p2
        assert 'horizontal_position' in p2
        assert 'height_maintenance' in p2

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
        # (landing_timing_sync, coordination metrics)
        assert 'A2_landing_timing_sync' in result_30fps['execution']
        assert 'A2_landing_timing_sync' in result_60fps['execution']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
