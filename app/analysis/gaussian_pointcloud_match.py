"""Match image and sensor point clouds via Gaussian estimation."""
from __future__ import annotations

import json
from math import log
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np


def _fuse_clouds(
    image_points: Iterable[Tuple[float, float, float]],
    sensor_points: Iterable[Tuple[float, float, float]],
) -> tuple[np.ndarray, np.ndarray]:
    """Return fused point cloud mean and covariance matrix."""
    image_arr = np.asarray(list(image_points), dtype=float)
    sensor_arr = np.asarray(list(sensor_points), dtype=float)
    if image_arr.size == 0 and sensor_arr.size == 0:
        raise ValueError("No points supplied")
    fused = np.vstack([a for a in (image_arr, sensor_arr) if a.size])
    return fused.mean(axis=0), np.cov(fused, rowvar=False)


def rank_pointcloud_gaussian(
    image_points: Iterable[Tuple[float, float, float]],
    sensor_points: Iterable[Tuple[float, float, float]],
    model_path: str | Path,
    top_k: int = 3,
) -> List[Tuple[str, float, float]]:
    """Return top classes ranked by Mahalanobis distance and probability.

    The likelihood for each class is computed using the multivariate normal
    density and normalised to probabilities. ``top_k`` controls how many of
    the best matches are returned.
    """
    mean, cov = _fuse_clouds(image_points, sensor_points)

    with Path(model_path).open("r", encoding="utf-8") as f:
        model = json.load(f)

    scores: List[Tuple[str, float, float]] = []
    log_probs = []
    dim = len(mean)
    for label, params in model.items():
        class_mean = np.asarray(params["mean"], dtype=float)
        class_cov = np.asarray(params["cov"], dtype=float)
        try:
            inv = np.linalg.inv(class_cov)
        except np.linalg.LinAlgError:
            continue
        diff = mean - class_mean
        mah = float(diff.T @ inv @ diff)
        det = np.linalg.det(class_cov)
        if det <= 0:
            continue
        log_prob = -0.5 * (mah + log(det) + dim * log(2 * np.pi))
        scores.append((label, mah, log_prob))
        log_probs.append(log_prob)
    if not scores:
        raise ValueError("No valid classes in model")

    log_probs_arr = np.asarray(log_probs)
    probs = np.exp(log_probs_arr - log_probs_arr.max())
    probs /= probs.sum()
    ranked = [
        (label, mah, float(prob))
        for (label, mah, _), prob in zip(scores, probs)
    ]
    ranked.sort(key=lambda x: x[2], reverse=True)
    return ranked[:top_k]


def match_pointcloud_gaussian(
    image_points: Iterable[Tuple[float, float, float]],
    sensor_points: Iterable[Tuple[float, float, float]],
    model_path: str | Path,
) -> tuple[str, float]:
    """Return the closest trained entity and Mahalanobis distance."""
    label, score, _ = rank_pointcloud_gaussian(
        image_points, sensor_points, model_path, top_k=1
    )[0]
    return label, score
