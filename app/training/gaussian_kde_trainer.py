from __future__ import annotations
"""Train Gaussian KDE models from fused image and sensor point clouds."""

from pathlib import Path
from typing import Sequence, Dict, List
import pickle

import numpy as np
from sklearn.neighbors import KernelDensity

from ..analysis.image_pointcloud import image_to_pointcloud3d


def _cloud_stats(points: Sequence[Sequence[float]]) -> np.ndarray:
    """Return concatenated mean/std of a point cloud."""
    arr = np.asarray(points, dtype=float)
    if arr.size == 0:
        return np.zeros(6)
    mean = arr.mean(axis=0)
    std = arr.std(axis=0)
    return np.concatenate([mean, std])


def train_gaussian_kde(
    image_files: Sequence[Path],
    sensor_files: Sequence[Path],
    labels: Sequence[str],
    model_out: Path,
    bandwidth: float = 1.0,
) -> Path:
    """Fit a per-class Gaussian kernel density model.

    Each image is converted to a point cloud and fused with the matching sensor
    cloud. The fused statistics feed per-class KDE estimators which are saved to
    ``model_out``.
    """
    if not (len(image_files) == len(sensor_files) == len(labels)):
        raise ValueError("Images, sensors, and labels must have equal length")

    feats: Dict[str, List[np.ndarray]] = {}
    for img, sens, label in zip(image_files, sensor_files, labels):
        img_cloud = image_to_pointcloud3d(img)
        sens_cloud = np.loadtxt(sens, delimiter=",")
        feat = np.concatenate([
            _cloud_stats(img_cloud),
            _cloud_stats(sens_cloud),
        ])
        feats.setdefault(label, []).append(feat)

    model: Dict[str, KernelDensity] = {}
    for label, vecs in feats.items():
        X = np.vstack(vecs)
        kde = KernelDensity(kernel="gaussian", bandwidth=bandwidth)
        kde.fit(X)
        model[label] = kde

    with Path(model_out).open("wb") as f:
        pickle.dump(model, f)
    return Path(model_out)
