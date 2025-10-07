"""Ensemble classifier combining multiple image identifiers."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Iterable, List


def classify_ensemble(
    image: Path,
    classifiers: Iterable[Callable[[Path], Dict[str, float]]],
) -> Dict[str, float]:
    """Run each classifier and average confidences for each label.

    Parameters
    ----------
    image:
        Path to the image file.
    classifiers:
        Iterable of callables that accept an image ``Path`` and return a
        mapping with ``target`` and ``confidence`` keys.

    Returns
    -------
    dict
        Dictionary with the highest-scoring ``target`` and its averaged
        ``confidence``. If no classifiers are provided, ``{"target": "unknown", "confidence": 0.0}`` is returned.
    """
    scores: Dict[str, List[float]] = {}
    for clf in classifiers:
        result = clf(image)
        scores.setdefault(result["target"], []).append(result["confidence"])
    if not scores:
        return {"target": "unknown", "confidence": 0.0}
    averaged = {k: sum(v) / len(v) for k, v in scores.items()}
    target = max(averaged, key=averaged.get)
    return {"target": target, "confidence": float(averaged[target])}


__all__ = ["classify_ensemble"]
