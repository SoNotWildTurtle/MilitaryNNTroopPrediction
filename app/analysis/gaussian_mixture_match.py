"""Gaussian mixture matching for sensor features."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np


def match_gaussian_mixture(features: Dict[str, float], model_path: str) -> List[Tuple[str, float]]:
    """Rank classes by Gaussian mixture log-probabilities.

    Args:
        features: Mapping of feature name to value.
        model_path: Path to the saved mixture model produced by
            ``train_gaussian_mixture_model``.
    Returns:
        List of (class, probability) tuples sorted from most likely to least.
    """
    models: Dict[str, any] = joblib.load(Path(model_path))
    x = np.array([features[k] for k in sorted(features.keys())]).reshape(1, -1)
    scores = []
    for cls, gm in models.items():
        log_prob = gm.score(x)[0]
        scores.append((cls, log_prob))
    # convert log probabilities to normalized probabilities
    log_probs = np.array([s for _, s in scores])
    probs = np.exp(log_probs - np.max(log_probs))
    probs = probs / probs.sum()
    ranked = sorted(zip([c for c, _ in scores], probs), key=lambda t: t[1], reverse=True)
    return ranked
