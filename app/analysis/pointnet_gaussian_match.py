"""Match point clouds using a PointNet encoder with Gaussian statistics."""
from __future__ import annotations

import json
from math import log
from pathlib import Path
from typing import Iterable, List, Tuple

import numpy as np
import torch

from .pointnet_model import PointNetEncoder


def _fuse_clouds(
    image_points: Iterable[Tuple[float, float, float]],
    sensor_points: Iterable[Tuple[float, float, float]],
) -> np.ndarray:
    """Return fused array of points."""
    image_arr = np.asarray(list(image_points), dtype=float)
    sensor_arr = np.asarray(list(sensor_points), dtype=float)
    if image_arr.size == 0 and sensor_arr.size == 0:
        raise ValueError("No points supplied")
    return np.vstack([a for a in (image_arr, sensor_arr) if a.size])


def rank_pointnet_gaussian(
    image_points: Iterable[Tuple[float, float, float]],
    sensor_points: Iterable[Tuple[float, float, float]],
    model_path: str | Path,
    stats_path: str | Path,
    top_k: int = 3,
) -> List[Tuple[str, float, float]]:
    """Return top classes ranked by Mahalanobis distance and probability."""
    fused = _fuse_clouds(image_points, sensor_points)

    with Path(stats_path).open("r", encoding="utf-8") as f:
        stats = json.load(f)
    if not stats:
        raise ValueError("Empty stats file")
    feat_dim = len(next(iter(stats.values()))["mean"])

    encoder = PointNetEncoder(feat_dim=feat_dim)
    state = torch.load(model_path, map_location="cpu")
    encoder.mlp.load_state_dict(state)
    encoder.eval()

    with torch.no_grad():
        feats = encoder(torch.tensor(fused, dtype=torch.float32))
    feat_mean = feats.mean(dim=0).numpy()

    scores: List[Tuple[str, float, float]] = []
    log_probs: List[float] = []
    dim = len(feat_mean)
    for label, params in stats.items():
        class_mean = np.asarray(params["mean"], dtype=float)
        class_cov = np.asarray(params["cov"], dtype=float)
        try:
            inv = np.linalg.inv(class_cov)
        except np.linalg.LinAlgError:
            continue
        diff = feat_mean - class_mean
        mah = float(diff.T @ inv @ diff)
        det = np.linalg.det(class_cov)
        if det <= 0:
            continue
        log_prob = -0.5 * (mah + log(det) + dim * log(2 * np.pi))
        scores.append((label, mah, log_prob))
        log_probs.append(log_prob)
    if not scores:
        raise ValueError("No valid classes in stats")

    log_probs_arr = np.asarray(log_probs)
    probs = np.exp(log_probs_arr - log_probs_arr.max())
    probs /= probs.sum()
    ranked = [
        (label, mah, float(prob))
        for (label, mah, _), prob in zip(scores, probs)
    ]
    ranked.sort(key=lambda x: x[2], reverse=True)
    return ranked[:top_k]


def match_pointnet_gaussian(
    image_points: Iterable[Tuple[float, float, float]],
    sensor_points: Iterable[Tuple[float, float, float]],
    model_path: str | Path,
    stats_path: str | Path,
) -> Tuple[str, float]:
    """Return closest class and Mahalanobis distance."""
    label, score, _ = rank_pointnet_gaussian(
        image_points, sensor_points, model_path, stats_path, top_k=1
    )[0]
    return label, score
