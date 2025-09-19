"""Match fused image/sensor point clouds against Gaussian models."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Tuple

from .image_pointcloud import image_to_pointcloud3d
from .gaussian_pointcloud_match import (
    rank_pointcloud_gaussian,
    match_pointcloud_gaussian,
)


Point3D = Tuple[float, float, float]


def _load_sensor_cloud(path: str | Path) -> List[Point3D]:
    pts: List[Point3D] = []
    with Path(path).open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                pts.append((float(row[0]), float(row[1]), float(row[2])))
    return pts


def rank_fused_gaussian(
    image_path: str | Path,
    sensor_path: str | Path,
    model_path: str | Path,
    top_k: int = 3,
) -> List[Tuple[str, float, float]]:
    """Rank classes by probability given image and sensor point clouds."""
    image_cloud = image_to_pointcloud3d(image_path)
    sensor_cloud = _load_sensor_cloud(sensor_path)
    return rank_pointcloud_gaussian(image_cloud, sensor_cloud, model_path, top_k)


def match_fused_gaussian(
    image_path: str | Path,
    sensor_path: str | Path,
    model_path: str | Path,
) -> Tuple[str, float]:
    """Return the best matching class and distance for fused clouds."""
    image_cloud = image_to_pointcloud3d(image_path)
    sensor_cloud = _load_sensor_cloud(sensor_path)
    return match_pointcloud_gaussian(image_cloud, sensor_cloud, model_path)
