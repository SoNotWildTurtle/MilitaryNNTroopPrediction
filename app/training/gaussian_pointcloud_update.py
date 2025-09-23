"""Update existing Gaussian point-cloud models with new data."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


def _stats_from_csv(csv_path: Path) -> Dict[str, Tuple[np.ndarray, np.ndarray, int]]:
    """Return mean, covariance and count for each label in the CSV."""
    points: Dict[str, List[List[float]]] = defaultdict(list)
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                x = float(row["x"])
                y = float(row["y"])
                z = float(row["z"])
                label = row["label"]
            except KeyError as exc:
                raise ValueError("CSV must contain x,y,z,label columns") from exc
            points[label].append([x, y, z])

    stats: Dict[str, Tuple[np.ndarray, np.ndarray, int]] = {}
    for label, pts in points.items():
        arr = np.asarray(pts, dtype=float)
        if arr.shape[0] < 2:
            continue
        mean = arr.mean(axis=0)
        cov = np.cov(arr, rowvar=False)
        stats[label] = (mean, cov, arr.shape[0])
    return stats


def _combine(
    mean_a: np.ndarray,
    cov_a: np.ndarray,
    n_a: int,
    mean_b: np.ndarray,
    cov_b: np.ndarray,
    n_b: int,
) -> Tuple[np.ndarray, np.ndarray, int]:
    """Return combined mean/cov/count for two Gaussian estimates."""
    if n_a == 0:
        return mean_b, cov_b, n_b
    if n_b == 0:
        return mean_a, cov_a, n_a
    n = n_a + n_b
    mean = (n_a * mean_a + n_b * mean_b) / n
    cov = (
        (n_a - 1) * cov_a
        + (n_b - 1) * cov_b
        + n_a * np.outer(mean_a - mean, mean_a - mean)
        + n_b * np.outer(mean_b - mean, mean_b - mean)
    ) / (n - 1)
    return mean, cov, n


def update_gaussian_pointcloud_model(
    csv_path: str | Path,
    model_path: str | Path = "gaussian_pointcloud_model.json",
) -> Path:
    """Update a Gaussian model file with additional labeled point clouds."""
    csv_path = Path(csv_path)
    model_path = Path(model_path)

    with model_path.open("r", encoding="utf-8") as f:
        model = json.load(f)

    new_stats = _stats_from_csv(csv_path)
    for label, (mean_new, cov_new, n_new) in new_stats.items():
        if label in model:
            mean_old = np.asarray(model[label]["mean"], dtype=float)
            cov_old = np.asarray(model[label]["cov"], dtype=float)
            n_old = int(model[label].get("count", 0))
            mean, cov, n = _combine(mean_old, cov_old, n_old, mean_new, cov_new, n_new)
        else:
            mean, cov, n = mean_new, cov_new, n_new
        model[label] = {
            "mean": mean.tolist(),
            "cov": cov.tolist(),
            "count": int(n),
        }

    with model_path.open("w", encoding="utf-8") as f:
        json.dump(model, f)
    return model_path
