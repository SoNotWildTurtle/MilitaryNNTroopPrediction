from __future__ import annotations

"""Train a Gaussian Naive Bayes model on fused image and sensor point clouds."""

from pathlib import Path
from typing import Sequence

import numpy as np
import pickle
from sklearn.naive_bayes import GaussianNB

from ..analysis.image_pointcloud import image_to_pointcloud3d


def _cloud_stats(points: Sequence[Sequence[float]]) -> np.ndarray:
    arr = np.asarray(points, dtype=float)
    if arr.size == 0:
        return np.zeros(6)
    mean = arr.mean(axis=0)
    std = arr.std(axis=0)
    return np.concatenate([mean, std])


def train_gaussian_nb(
    image_files: Sequence[Path],
    sensor_files: Sequence[Path],
    labels: Sequence[str],
    model_out: Path,
) -> Path:
    """Train and save a GaussianNB model from paired image and sensor clouds."""
    if not (len(image_files) == len(sensor_files) == len(labels)):
        raise ValueError("Images, sensors, and labels must have equal length")

    feats: list[np.ndarray] = []
    for img, sens in zip(image_files, sensor_files):
        img_cloud = image_to_pointcloud3d(img)
        sens_cloud = np.loadtxt(sens, delimiter=",")
        feats.append(np.concatenate([_cloud_stats(img_cloud), _cloud_stats(sens_cloud)]))

    X = np.vstack(feats)
    y = np.array(labels)

    clf = GaussianNB()
    clf.fit(X, y)

    model_out = Path(model_out)
    with model_out.open("wb") as f:
        pickle.dump(clf, f)
    return model_out
