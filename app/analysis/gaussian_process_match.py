from __future__ import annotations
"""Match fused image and sensor clouds using a Gaussian Process classifier."""

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


def match_gaussian_process(
    image_file: Path, sensor_file: Path, model_path: Path
) -> List[Tuple[str, float]]:
    """Return class probabilities from a GaussianProcessClassifier model."""
    with Path(model_path).open("rb") as f:
        gpc = pickle.load(f)

    img_cloud = image_to_pointcloud3d(image_file)
    sens_cloud = np.loadtxt(sensor_file, delimiter=",")
    feat = np.concatenate([_cloud_stats(img_cloud), _cloud_stats(sens_cloud)])
    probs = gpc.predict_proba([feat])[0]
    classes = gpc.classes_
    return list(zip(classes, probs))
