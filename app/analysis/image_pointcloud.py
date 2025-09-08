"""Generate a simple 2D point cloud from an image.

The helper converts an image to grayscale, thresholds dark pixels, and
returns a list of normalized ``(x, y)`` coordinates. This can be used to
approximate a point cloud of the target for sensor matching or training.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import numpy as np
from PIL import Image

Point = Tuple[float, float]
Point3D = Tuple[float, float, float]


def image_to_pointcloud(image_path: str | Path, threshold: int = 128, max_points: int = 1000) -> List[Point]:
    """Convert ``image_path`` to a list of normalized points.

    ``threshold`` determines which pixels are considered part of the target.
    Up to ``max_points`` are returned to keep the cloud compact.
    """
    image_path = Path(image_path)
    img = Image.open(image_path).convert("L")
    arr = np.asarray(img)
    coords = np.argwhere(arr < threshold)
    if coords.size == 0:
        return []
    if len(coords) > max_points:
        idx = np.linspace(0, len(coords) - 1, max_points).astype(int)
        coords = coords[idx]
    h, w = arr.shape
    points = [(float(x) / w, float(y) / h) for y, x in coords]
    return points


def image_to_pointcloud3d(
    image_path: str | Path, threshold: int = 128, max_points: int = 1000
) -> List[Point3D]:
    """Convert ``image_path`` to a list of normalized ``(x, y, z)`` points.

    The ``z`` value is the normalized pixel intensity, enabling rudimentary 3‑D
    point clouds for richer sensor matching.
    """
    image_path = Path(image_path)
    img = Image.open(image_path).convert("L")
    arr = np.asarray(img)
    coords = np.argwhere(arr < threshold)
    if coords.size == 0:
        return []
    if len(coords) > max_points:
        idx = np.linspace(0, len(coords) - 1, max_points).astype(int)
        coords = coords[idx]
    h, w = arr.shape
    points = [
        (float(x) / w, float(y) / h, 1.0 - float(arr[y, x]) / 255.0) for y, x in coords
    ]
    return points
