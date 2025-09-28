"""Analyze cohesion among multiple image classifiers."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Callable, Dict, Iterable, List


def analyze_cohesion(
    image: Path,
    classifiers: Iterable[Callable[[Path], Dict[str, float]]],
) -> Dict[str, object]:
    """Run classifiers on ``image`` and report agreement statistics.

    Parameters
    ----------
    image:
        Path to the image file.
    classifiers:
        Iterable of callables returning ``{"target": str, "confidence": float}``.

    Returns
    -------
    dict
        Dictionary containing each model's prediction, the consensus label, and
        an ``agreement`` fraction between 0 and 1 indicating how many models
        predicted the consensus label.
    """
    predictions: List[Dict[str, float]] = []
    votes: Counter[str] = Counter()
    weighted: Counter[str] = Counter()
    for clf in classifiers:
        result = clf(image)
        predictions.append(result)
        label = result["target"]
        votes[label] += 1
        weighted[label] += float(result.get("confidence", 0.0))
    if not predictions:
        return {
            "predictions": [],
            "consensus": "unknown",
            "agreement": 0.0,
            "weighted_consensus": "unknown",
            "weighted_agreement": 0.0,
        }
    consensus, count = votes.most_common(1)[0]
    agreement = count / len(predictions)
    weighted_consensus, weight = weighted.most_common(1)[0]
    total_weight = sum(weighted.values()) or 1.0
    weighted_agreement = weight / total_weight
    return {
        "predictions": predictions,
        "consensus": consensus,
        "agreement": agreement,
        "weighted_consensus": weighted_consensus,
        "weighted_agreement": weighted_agreement,
    }


__all__ = ["analyze_cohesion"]
