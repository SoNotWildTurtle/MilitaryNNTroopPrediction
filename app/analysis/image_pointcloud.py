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

try:
    import cv2
except Exception:  # pragma: no cover - OpenCV optional for extra richness
    cv2 = None

from ..config import settings

Point = Tuple[float, float]
Point3D = Tuple[float, float, float]


def _high_memory_enabled(richness: float, scale: float) -> bool:
    """Determine whether to generate denser point clouds."""

    return settings.HIGH_MEMORY_MODE or richness > 1.5 or scale > 1.5


def image_to_pointcloud(
    image_path: str | Path,
    threshold: int = 128,
    max_points: int = 1000,
    scale: float | None = None,
) -> List[Point]:
    """Convert ``image_path`` to a list of normalized points.

    ``threshold`` determines which pixels are considered part of the target.
    ``scale`` multiplies the number of points and resizes the image to produce
    higher-resolution clouds when ``RESOLUTION_SCALE`` or ``FEATURE_RICHNESS``
    is set above ``1``. Up to ``max_points``×``scale`` points are returned to
    keep the cloud compact. When ``HIGH_MEMORY_MODE`` (or large richness
    multipliers) are enabled, additional thresholds, edge-derived points, and
    sub-pixel jittered samples (weighted by a Gaussian mask) are merged to
    produce denser clouds for rich cross-sensor matching.
    """
    image_path = Path(image_path)
    scale = scale or settings.RESOLUTION_SCALE
    richness = settings.FEATURE_RICHNESS
    high_memory = _high_memory_enabled(richness, scale)
    if richness != 1.0:
        scale *= richness
        max_points = int(max_points * richness)
    img = Image.open(image_path).convert("L")
    if scale != 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    arr = np.asarray(img)
    thresholds = {int(threshold)}
    if high_memory:
        for offset in (-32, -16, 16, 32):
            thresholds.add(int(np.clip(threshold + offset, 1, 254)))
    coords_list = []
    for thr in sorted(thresholds):
        sel = np.argwhere(arr < thr)
        if sel.size:
            coords_list.append(sel)
    if high_memory:
        grad_y, grad_x = np.gradient(arr.astype(np.float32))
        grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)
        edge_mask = grad_mag > float(np.mean(grad_mag))
        edge_coords = np.argwhere(edge_mask)
        if edge_coords.size:
            coords_list.append(edge_coords)
    if not coords_list:
        return []
    coords = np.vstack(coords_list)
    coords = np.unique(coords, axis=0)
    if high_memory and coords.size:
        coords = _densify_coords(coords, arr.shape)
    max_points = int(max_points * scale)
    if high_memory:
        max_points = int(max_points * 1.5)
    if len(coords) > max_points:
        idx = np.linspace(0, len(coords) - 1, max_points).astype(int)
        coords = coords[idx]
    h, w = arr.shape
    points = [(float(x) / w, float(y) / h) for y, x in coords]
    return points


def image_to_pointcloud3d(
    image_path: str | Path,
    threshold: int = 128,
    max_points: int = 1000,
    scale: float | None = None,
) -> List[Point3D]:
    """Convert ``image_path`` to a list of normalized ``(x, y, z)`` points.

    ``scale`` plus ``RESOLUTION_SCALE`` and ``FEATURE_RICHNESS`` behave like in
    :func:`image_to_pointcloud`, producing denser 3‑D clouds when set above ``1``.
    The ``z`` value is the normalized pixel intensity; when high-memory mode is
    active we also fold in edge gradients and sub-pixel samples to emphasize
    structural detail in the resulting 3‑D cloud.
    """
    image_path = Path(image_path)
    scale = scale or settings.RESOLUTION_SCALE
    richness = settings.FEATURE_RICHNESS
    high_memory = _high_memory_enabled(richness, scale)
    if richness != 1.0:
        scale *= richness
        max_points = int(max_points * richness)
    img = Image.open(image_path).convert("L")
    if scale != 1.0:
        img = img.resize((int(img.width * scale), int(img.height * scale)))
    arr = np.asarray(img)
    thresholds = {int(threshold)}
    if high_memory:
        for offset in (-32, -16, 16, 32):
            thresholds.add(int(np.clip(threshold + offset, 1, 254)))
    coords_list = []
    for thr in sorted(thresholds):
        sel = np.argwhere(arr < thr)
        if sel.size:
            coords_list.append(sel)
    grad_y = grad_x = grad_mag = None
    if high_memory:
        grad_y, grad_x = np.gradient(arr.astype(np.float32))
        grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)
        edge_mask = grad_mag > float(np.mean(grad_mag))
        edge_coords = np.argwhere(edge_mask)
        if edge_coords.size:
            coords_list.append(edge_coords)
    if not coords_list:
        return []
    coords = np.vstack(coords_list)
    coords = np.unique(coords, axis=0)
    if high_memory and coords.size:
        coords = _densify_coords(coords, arr.shape)
    max_points = int(max_points * scale)
    if high_memory:
        max_points = int(max_points * 1.5)
    if len(coords) > max_points:
        idx = np.linspace(0, len(coords) - 1, max_points).astype(int)
        coords = coords[idx]
    h, w = arr.shape
    grad_norm = None
    if grad_mag is not None and grad_mag.max() > 0:
        grad_norm = grad_mag / float(grad_mag.max())
    points = [
        (
            float(x) / w,
            float(y) / h,
            _compute_height(arr, grad_norm, y, x, high_memory),
        )
        for y, x in coords
    ]
    return points


def _densify_coords(coords: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    """Super-sample coordinates for high-memory runs."""

    h, w = shape
    base = coords.astype(np.float32)
    offsets = np.array(
        [
            (0.0, 0.0),
            (-0.25, -0.25),
            (-0.25, 0.25),
            (0.25, -0.25),
            (0.25, 0.25),
        ],
        dtype=np.float32,
    )
    dense = base[:, None, :] + offsets[None, :, :]
    dense = dense.reshape(-1, 2)
    dense[:, 0] = np.clip(dense[:, 0], 0, h - 1)
    dense[:, 1] = np.clip(dense[:, 1], 0, w - 1)

    if cv2 is not None:
        # Blend with a softly blurred mask to prioritize structured areas.
        mask = np.zeros((h, w), dtype=np.uint8)
        int_coords = coords.astype(int)
        mask[int_coords[:, 0], int_coords[:, 1]] = 255
        blurred = cv2.GaussianBlur(mask, (5, 5), 0)
        weights = blurred[(dense[:, 0].astype(int), dense[:, 1].astype(int))]
        order = np.argsort(-weights)
        dense = dense[order]

    return dense


def _compute_height(
    arr: np.ndarray,
    grad_norm: np.ndarray | None,
    y: int,
    x: int,
    high_memory: bool,
) -> float:
    """Return the z value for the 3‑D point cloud."""

    base = 1.0 - float(arr[y, x]) / 255.0
    if not high_memory or grad_norm is None:
        return base
    enhancement = 0.0
    grad_value = float(grad_norm[y, x]) if grad_norm is not None else 0.0
    enhancement = 0.15 * grad_value
    return float(np.clip(base + enhancement, 0.0, 1.0))
