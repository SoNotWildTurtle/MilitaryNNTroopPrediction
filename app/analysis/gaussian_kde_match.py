from __future__ import annotations
"""Match fused image and sensor clouds with per-class Gaussian KDE models."""

from pathlib import Path
from typing import Sequence, List, Tuple
import pickle

import numpy as np

from .image_pointcloud import image_to_pointcloud3d


def _cloud_stats(points: Sequence[Sequence[float]]) -> np.ndarray:
    arr = np.asarray(points, dtype=float)
    if arr.size == 0:
        return np.zeros(6)
    mean = arr.mean(axis=0)
    std = arr.std(axis=0)
    return np.concatenate([mean, std])


def match_gaussian_kde(
    image_file: Path, sensor_file: Path, model_path: Path
) -> List[Tuple[str, float]]:
    """Return class probabilities from a KDE model."""
    with Path(model_path).open("rb") as f:
        model = pickle.load(f)

    img_cloud = image_to_pointcloud3d(image_file)
    sens_cloud = np.loadtxt(sensor_file, delimiter=",")
    feat = np.concatenate([
        _cloud_stats(img_cloud),
        _cloud_stats(sens_cloud),
    ])[None, :]

    logs: dict[str, float] = {}
    for label, kde in model.items():
        logs[label] = float(kde.score_samples(feat)[0])

    max_log = max(logs.values())
    exp = {k: np.exp(v - max_log) for k, v in logs.items()}
    total = sum(exp.values()) or 1.0
    probs = {k: v / total for k, v in exp.items()}
    return sorted(probs.items(), key=lambda x: x[1], reverse=True)
