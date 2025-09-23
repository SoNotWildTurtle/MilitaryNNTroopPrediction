"""Train Gaussian models from paired image and sensor point clouds."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np

from ..analysis import image_to_pointcloud3d


def _load_sensor_cloud(csv_path: str | Path) -> List[List[float]]:
    pts: List[List[float]] = []
    with Path(csv_path).open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                pts.append([float(row[0]), float(row[1]), float(row[2])])
    return pts


def train_fused_gaussian_model(
    pairs_csv: str | Path,
    model_path: str | Path = "fused_gaussian_model.json",
) -> Path:
    """Fit Gaussian statistics from ``image,sensor,label`` rows.

    Each row references an image file and a CSV point cloud from a sensor. The
    image is converted to a 3‑D point cloud and concatenated with the sensor
    points before accumulating per‑class statistics.
    """
    pairs_csv = Path(pairs_csv)
    model_path = Path(model_path)

    points: Dict[str, List[List[float]]] = defaultdict(list)
    with pairs_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                image_file = row["image"]
                sensor_file = row["sensor"]
                label = row["label"]
            except KeyError as exc:
                raise ValueError(
                    "CSV must contain image,sensor,label columns"
                ) from exc
            image_pts = image_to_pointcloud3d(image_file)
            sensor_pts = _load_sensor_cloud(sensor_file)
            fused = image_pts + sensor_pts
            for pt in fused:
                points[label].append([float(p) for p in pt])

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
        raise ValueError("No valid training samples found")

    with model_path.open("w", encoding="utf-8") as f:
        json.dump(model, f)
    return model_path
