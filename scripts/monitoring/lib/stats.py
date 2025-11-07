"""
Statistical utilities for Ground Truth evaluation.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Sequence, Tuple, Union

Label = Union[str, int, float, bool]


def calculate_bcr(ai_labels: Sequence[Label], human_labels: Sequence[Label]) -> float:
    """
    Calculate the Binary Classification Rate (match ratio).
    """
    if len(ai_labels) != len(human_labels):
        raise ValueError("ai_labels and human_labels must be the same length")
    if not ai_labels:
        raise ValueError("labels must not be empty")
    matches = sum(1 for ai, human in zip(ai_labels, human_labels) if ai == human)
    return matches / len(ai_labels)


def calculate_cohens_kappa(ai_labels: Sequence[Label], human_labels: Sequence[Label]) -> float:
    """
    Calculate Cohen's Kappa between two categorical label sequences.
    """
    if len(ai_labels) != len(human_labels):
        raise ValueError("ai_labels and human_labels must be the same length")
    n = len(ai_labels)
    if n == 0:
        raise ValueError("labels must not be empty")

    observed = sum(1 for ai, human in zip(ai_labels, human_labels) if ai == human) / n

    ai_counts = Counter(ai_labels)
    human_counts = Counter(human_labels)

    expected = 0.0
    for label in set(ai_counts) | set(human_counts):
        expected += (ai_counts[label] / n) * (human_counts[label] / n)

    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1 - expected)


def calculate_override_rate(overrides: Iterable[bool]) -> float:
    """
    Calculate override ratio (AI -> Human change count / total count).
    """
    overrides_list = list(overrides)
    if not overrides_list:
        raise ValueError("overrides must not be empty")
    total = len(overrides_list)
    count = sum(1 for flag in overrides_list if bool(flag))
    return count / total


__all__ = [
    "calculate_bcr",
    "calculate_cohens_kappa",
    "calculate_override_rate",
]
