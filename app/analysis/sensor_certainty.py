"""Utilities for weighting multi-sensor confidences and estimating uncertainty."""
from __future__ import annotations

from math import sqrt
from typing import Sequence, Tuple


def fuse_sensor_confidences(
    scores: Sequence[float], weights: Sequence[float]
) -> Tuple[float, float]:
    """Return a weighted average confidence and its standard deviation.

    Parameters
    ----------
    scores:
        Confidence values from individual sensors.
    weights:
        Reliability weights for the corresponding sensors.

    Returns
    -------
    tuple of (average confidence, standard deviation)
    """
    total = sum(weights)
    if total == 0 or len(scores) == 0:
        return 0.0, 0.0
    avg = sum(s * w for s, w in zip(scores, weights)) / total
    variance = sum(w * (s - avg) ** 2 for s, w in zip(scores, weights)) / total
    return avg, sqrt(variance)
