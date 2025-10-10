"""Train Gaussian models from labeled point clouds."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np


def train_gaussian_pointcloud_model(
    csv_path: str | Path,
    model_path: str | Path = "gaussian_pointcloud_model.json",
) -> Path:
    """Fit mean and covariance for each label from a CSV of ``x,y,z,label``."""
    csv_path = Path(csv_path)
    model_path = Path(model_path)

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

    model = {}
    for label, pts in points.items():
        arr = np.asarray(pts, dtype=float)
        if arr.shape[0] < 2:
            continue
        mean = arr.mean(axis=0)
        cov = np.cov(arr, rowvar=False).tolist()
        model[label] = {
            "mean": mean.tolist(),
            "cov": cov,
            "count": int(arr.shape[0]),
        }

    if not model:
        raise ValueError("No valid labeled points found")

    with model_path.open("w", encoding="utf-8") as f:
        json.dump(model, f)
    return model_path
