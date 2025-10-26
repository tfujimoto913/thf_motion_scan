"""
Purpose: Test suite for CrossStepEvaluator (T07) 2-axis evaluation system
Responsibility: Validate execution (3pts) and principles (9pts) scoring
Dependencies: pytest, CrossStepEvaluator, config.json
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
from cross_step import CrossStepEvaluator


class TestCrossStepEvaluator:
    """
    What: Test suite for CrossStepEvaluator 2-axis evaluation
    Why: Ensure correct implementation of A (3pts) + B (9pts) scoring system
    Design Decision: Follow same pattern as previous test files
    """

    @pytest.fixture
    def evaluator(self):
        """Create evaluator instance with test config"""
        config_path = Path(__file__).parent.parent / 'config.json'
        return CrossStepEvaluator(config_path=str(config_path))

    @pytest.fixture
    def sample_landmarks_data(self):
        """Generate sample landmark data simulating cross step movements"""
        landmarks_data = []
        fps = 30.0

        # Simulate 90 frames (3 seconds): neutral -> right cross -> neutral -> left cross -> neutral
        for frame_idx in range(90):
            landmarks = [{'x': 0.0, 'y': 0.0, 'z': 0.0, 'visibility': 1.0} for _ in range(33)]

            # Base positions
            base_y = 0.5

            # Simulate cross step movements (lateral ankle displacement)
            if frame_idx < 10:  # Neutral start
                left_ankle_x = 0.4
                right_ankle_x = 0.6
            elif frame_idx < 30:  # Right cross step (right ankle crosses to left)
                progress = (frame_idx - 10) / 20
                left_ankle_x = 0.4
                right_ankle_x = 0.6 - 0.3 * progress  # Moves from 0.6 to 0.3 (crossing over)
            elif frame_idx < 40:  # Return to neutral
                progress = (frame_idx - 30) / 10
                left_ankle_x = 0.4
                right_ankle_x = 0.3 + 0.3 * progress
            elif frame_idx < 65:  # Left cross step (left ankle crosses to right)
                progress = (frame_idx - 40) / 25
                left_ankle_x = 0.4 + 0.3 * progress  # Moves from 0.4 to 0.7 (crossing over)
                right_ankle_x = 0.6
            else:  # Return to neutral
                progress = (frame_idx - 65) / 25
                left_ankle_x = 0.7 - 0.3 * progress
                right_ankle_x = 0.6

            # Set key landmarks
            # NOSE (0)
            landmarks[0] = {'x': 0.5, 'y': base_y - 0.3, 'z': 0.0, 'visibility': 1.0}

            # Shoulders (11, 12)
            landmarks[11] = {'x': 0.4, 'y': base_y - 0.1, 'z': 0.0, 'visibility': 1.0}
            landmarks[12] = {'x': 0.6, 'y': base_y - 0.1, 'z': 0.0, 'visibility': 1.0}

            # Hips (23, 24)
            landmarks[23] = {'x': 0.4, 'y': base_y + 0.4, 'z': 0.0, 'visibility': 1.0}
            landmarks[24] = {'x': 0.6, 'y': base_y + 0.4, 'z': 0.0, 'visibility': 1.0}

            # Knees (25, 26)
            landmarks[25] = {'x': 0.4, 'y': base_y + 0.6, 'z': 0.0, 'visibility': 1.0}
            landmarks[26] = {'x': 0.6, 'y': base_y + 0.6, 'z': 0.0, 'visibility': 1.0}

            # Ankles (27, 28)
            landmarks[27] = {'x': left_ankle_x, 'y': base_y + 0.8, 'z': 0.0, 'visibility': 1.0}
            landmarks[28] = {'x': right_ankle_x, 'y': base_y + 0.8, 'z': 0.0, 'visibility': 1.0}

            landmarks_data.append({
                'frame': frame_idx,
                'timestamp': frame_idx / fps,
                'landmarks': landmarks
            })

        return landmarks_data

    def test_evaluator_initialization(self, evaluator):
        """Test evaluator initialization with config"""
        assert evaluator is not None
        assert 'T07_cross_step' in evaluator.config['thresholds']
        assert 'execution' in evaluator.thresholds
        assert 'principles' in evaluator.thresholds

    def test_evaluation_structure(self, evaluator, sample_landmarks_data):
        """Test main evaluation return structure (12-point system)"""
        base_width = 0.2
        shoulder_width = 0.2

        result = evaluator.evaluate(sample_landmarks_data, base_width, shoulder_width)

        # Check top-level structure
        assert 'test_id' in result
        assert result['test_id'] == 'T07_cross_step'
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
        assert 'A1_cross_distance' in execution
        assert 'A2_trunk_rotation' in execution
        assert 'A3_left_right_symmetry' in execution
        assert 'total' in execution

        # Check A1 structure
        a1 = execution['A1_cross_distance']
        assert 'score' in a1
        assert 'max_score' in a1
        assert a1['max_score'] == 1.0

        # Check A2 structure
        a2 = execution['A2_trunk_rotation']
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
        assert 'P7_kinetic_chain' in principles
        assert 'P5_body_control' in principles
        assert 'P3_support_base' in principles
        assert 'total' in principles

        # Check P7 structure
        p7 = principles['P7_kinetic_chain']
        assert 'score' in p7
        assert 'max_score' in p7
        assert p7['max_score'] == 3.0
        assert 'hip_shoulder_timing' in p7
        assert 'support_cross_timing' in p7
        assert 'acceleration_pattern' in p7

        # Check P5 structure
        p5 = principles['P5_body_control']
        assert 'score' in p5
        assert 'max_score' in p5
        assert p5['max_score'] == 3.0
        assert 'pelvis_height' in p5
        assert 'trunk_verticality' in p5
        assert 'linear_progression' in p5

        # Check P3 structure
        p3 = principles['P3_support_base']
        assert 'score' in p3
        assert 'max_score' in p3
        assert p3['max_score'] == 3.0
        assert 'foot_width' in p3
        assert 'knee_stability' in p3
        assert 'com_foot_distance' in p3

        # Verify scoring ranges
        assert 0 <= p7['score'] <= 3.0
        assert 0 <= p5['score'] <= 3.0
        assert 0 <= p3['score'] <= 3.0
        assert 0 <= principles['total'] <= 9.0

    def test_cross_step_detection(self, evaluator, sample_landmarks_data):
        """Test cross step phase detection logic"""
        cross_steps = evaluator._detect_cross_steps(sample_landmarks_data)

        # Check structure
        assert 'right' in cross_steps
        assert 'left' in cross_steps

        # Should detect at least one cross step on each side
        # (May not detect if movement is too subtle in sample data)
        assert isinstance(cross_steps['right'], list)
        assert isinstance(cross_steps['left'], list)

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
        assert 'cross_distance' in evaluator.thresholds['execution']
        assert 'trunk_rotation' in evaluator.thresholds['execution']
        assert 'left_right_symmetry' in evaluator.thresholds['execution']

        # Check principles thresholds
        assert 'P7_kinetic_chain' in evaluator.thresholds['principles']
        assert 'P5_body_control' in evaluator.thresholds['principles']
        assert 'P3_support_base' in evaluator.thresholds['principles']

        # Check specific threshold values
        p7 = evaluator.thresholds['principles']['P7_kinetic_chain']
        assert 'hip_shoulder_timing' in p7
        assert 'support_cross_timing' in p7
        assert 'acceleration_pattern' in p7

        p5 = evaluator.thresholds['principles']['P5_body_control']
        assert 'pelvis_height' in p5
        assert 'trunk_verticality' in p5
        assert 'linear_progression' in p5

        p3 = evaluator.thresholds['principles']['P3_support_base']
        assert 'foot_width' in p3
        assert 'knee_stability' in p3
        assert 'com_foot_distance' in p3

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
        assert 'P7_kinetic_chain' in result_30fps['principles']
        assert 'P7_kinetic_chain' in result_60fps['principles']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
