"""Combine multiple image descriptors for robust object identification.

This module extracts complementary features from an image. On standard
setups it returns a normalized HSV histogram, Histogram of Oriented
Gradients (HOG) descriptors, and a scalar edge density score. When the
``HIGH_MEMORY_MODE`` flag or a large ``FEATURE_RICHNESS`` multiplier is
enabled we layer in additional descriptors—multi-scale histograms,
multi-resolution HOG vectors, Local Binary Pattern (LBP) histograms,
color moments, gradient statistics, Lab-color histograms, Gabor filter
energies, low-frequency Fourier coefficients, grey-level co-occurrence
matrix (GLCM) properties, coarse histograms from augmented views, Hu
moments, per-channel covariance summaries, wavelet energies, grid-based
Lab statistics, and deep EfficientNet embeddings—to capture
substantially richer signals for operators with extra RAM/GPU resources.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Union

import cv2
import numpy as np
import math
from PIL import Image

from ..config import settings

try:  # scikit-image is optional during basic startup
    from skimage.feature import (
        hog,
        local_binary_pattern,
        greycomatrix,
        greycoprops,
    )
except Exception:  # pragma: no cover - fallback when package missing
    hog = None
    local_binary_pattern = None
    greycomatrix = None
    greycoprops = None

try:  # Optional dependencies for wavelets and deep embeddings
    import pywt
except Exception:  # pragma: no cover - pywt optional
    pywt = None

try:
    import torch
    from torchvision import models
except Exception:  # pragma: no cover - torch optional
    torch = None
    models = None

_DEEP_MODEL = None
_DEEP_TRANSFORM = None
_DEEP_DEVICE = None

FeatureDict = Dict[str, Union[List[float], float]]


def _use_high_memory_features(richness: float) -> bool:
    """Return ``True`` if additional descriptors should be computed."""

    return (
        settings.HIGH_MEMORY_MODE
        or richness > 1.5
        or settings.RESOLUTION_SCALE > 1.5
    )


def _extra_levels(richness: float) -> int:
    """Determine how many extra pyramid levels to compute."""

    extra = 0
    if richness > 1.0:
        extra = int(math.ceil(richness - 1.0) * 2)
    if settings.HIGH_MEMORY_MODE:
        extra = max(extra, 2)
    return min(extra, 4)


def _pyramid_scales(levels: int) -> List[float]:
    """Return multiplicative scales for multi-resolution features."""

    return [1.0 + 0.15 * (idx + 1) for idx in range(levels)]


def _safe_hog(image: np.ndarray, cell_size: int, orientations: int) -> np.ndarray:
    """Compute HOG features, resizing if needed to avoid errors."""

    if hog is None:
        raise ImportError("scikit-image is required for HOG features")
    height, width = image.shape[:2]
    min_size = cell_size * 2
    if height < min_size or width < min_size:
        resize_factor = max(min_size / height, min_size / width)
        new_w = max(min_size, int(width * resize_factor))
        new_h = max(min_size, int(height * resize_factor))
        image = cv2.resize(image, (new_w, new_h))
    return hog(
        image,
        pixels_per_cell=(cell_size, cell_size),
        cells_per_block=(2, 2),
        orientations=orientations,
        feature_vector=True,
    )


def _lab_hist(image: np.ndarray, richness: float) -> np.ndarray:
    """Return concatenated Lab histograms."""

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    bins = min(128, max(16, int(32 * richness)))
    hist_parts = []
    for channel in cv2.split(lab):
        hist = cv2.calcHist([channel], [0], None, [bins], [0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        hist_parts.append(hist)
    return np.concatenate(hist_parts)


def _gabor_energies(gray: np.ndarray) -> np.ndarray:
    """Return mean absolute responses from a small Gabor bank."""

    responses: List[float] = []
    sizes = (5, 9, 13)
    thetas = (0.0, np.pi / 4, np.pi / 2, 3 * np.pi / 4)
    gray_f = gray.astype(np.float32)
    for size in sizes:
        sigma = 0.5 * size
        lambd = size
        for theta in thetas:
            kernel = cv2.getGaborKernel((size, size), sigma, theta, lambd, 0.5, 0)
            filtered = cv2.filter2D(gray_f, cv2.CV_32F, kernel)
            responses.append(float(np.mean(np.abs(filtered))))
    return np.asarray(responses, dtype=float)


def _fourier_descriptor(gray: np.ndarray) -> np.ndarray:
    """Return low-frequency DCT coefficients from the grayscale image."""

    resized = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(resized.astype(np.float32) / 255.0)
    patch = dct[:8, :8]
    return patch.flatten()


def _glcm_props(gray: np.ndarray) -> np.ndarray | None:
    """Return averaged grey-level co-occurrence matrix properties."""

    if greycomatrix is None or greycoprops is None:
        return None
    # Reduce range to keep GLCM size manageable.
    scaled = np.floor_divide(gray, 16).astype(np.uint8)
    matrix = greycomatrix(
        scaled,
        distances=[1, 2, 3],
        angles=[0.0, np.pi / 4, np.pi / 2, 3 * np.pi / 4],
        levels=16,
        symmetric=True,
        normed=True,
    )
    props: List[float] = []
    for prop_name in ("contrast", "homogeneity", "energy", "correlation"):
        props.append(float(np.mean(greycoprops(matrix, prop_name))))
    return np.asarray(props, dtype=float)


def _augmented_histograms(gray: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Return concatenated coarse histograms for rotated/flipped views."""

    views = [
        gray,
        cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE),
        cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE),
        cv2.flip(gray, 1),
    ]
    histograms: List[np.ndarray] = []
    edge_densities: List[float] = []
    for view in views:
        hist = cv2.calcHist([view], [0], None, [16], [0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        histograms.append(hist)
        edges = cv2.Canny(view, 100, 200)
        edge_densities.append(float(np.count_nonzero(edges)) / float(edges.size))
    stacked = np.stack(histograms)
    return stacked.flatten(), np.asarray(edge_densities, dtype=float)


def _hu_moments(gray: np.ndarray) -> np.ndarray:
    """Return log-scaled Hu invariant moments for shape characterization."""

    moments = cv2.moments(gray)
    hu = cv2.HuMoments(moments).flatten()
    # Log-transform for stability, preserving sign information.
    with np.errstate(all="ignore"):
        hu = np.sign(hu) * np.log10(np.abs(hu) + 1e-12)
    return hu.astype(float)


def _channel_covariances(image: np.ndarray) -> np.ndarray:
    """Return flattened covariance matrix between color channels."""

    reshaped = image.reshape(-1, 3).astype(np.float32)
    cov = np.cov(reshaped, rowvar=False)
    return cov.flatten()


def _wavelet_energy(gray: np.ndarray) -> np.ndarray | None:
    """Return per-band wavelet energies when PyWavelets is available."""

    if pywt is None:
        return None
    coeffs = pywt.wavedec2(gray.astype(np.float32) / 255.0, "db2", level=2)
    energies: List[float] = []
    for level in coeffs[1:]:
        for component in level:
            energies.append(float(np.mean(component ** 2)))
    return np.asarray(energies, dtype=float)


def _grid_lab_stats(image: np.ndarray, richness: float) -> np.ndarray:
    """Return mean/std Lab statistics on a coarse grid."""

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    rows = cols = 4 + min(4, int(max(0.0, richness - 1.0) * 4))
    h, w = lab.shape[:2]
    row_step = max(1, h // rows)
    col_step = max(1, w // cols)
    stats: List[float] = []
    for row in range(rows):
        for col in range(cols):
            patch = lab[row * row_step : min(h, (row + 1) * row_step), col * col_step : min(w, (col + 1) * col_step)]
            if patch.size == 0:
                continue
            stats.extend(np.mean(patch, axis=(0, 1)).tolist())
            stats.extend(np.std(patch, axis=(0, 1)).tolist())
    return np.asarray(stats, dtype=float)


def _load_deep_model():
    """Lazily load an EfficientNet encoder for deep embeddings."""

    global _DEEP_MODEL, _DEEP_TRANSFORM, _DEEP_DEVICE
    if torch is None or models is None:
        return None, None, None
    if _DEEP_MODEL is not None:
        return _DEEP_MODEL, _DEEP_TRANSFORM, _DEEP_DEVICE
    try:
        weights = models.EfficientNet_B0_Weights.DEFAULT
        model = models.efficientnet_b0(weights=weights)
    except Exception:  # pragma: no cover - torchvision without weights
        return None, None, None
    model.classifier = torch.nn.Identity()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    model.eval()
    _DEEP_MODEL = model
    _DEEP_TRANSFORM = weights.transforms()
    _DEEP_DEVICE = device
    return _DEEP_MODEL, _DEEP_TRANSFORM, _DEEP_DEVICE


def _deep_embedding(image: np.ndarray) -> np.ndarray | None:
    """Return a deep image embedding when torch/torchvision are available."""

    loaded = _load_deep_model()
    if loaded[0] is None:
        return None
    model, transform, device = loaded
    pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    tensor = transform(pil_img).unsqueeze(0).to(device)
    with torch.no_grad():
        embedding = model(tensor)
    return embedding.squeeze(0).detach().cpu().numpy()


def extract_feature_fusion(
    image_path: str, bins: int | None = None
) -> FeatureDict:
    """Return combined descriptors for an image.

    ``FEATURE_RICHNESS`` scales histogram bins and HOG detail so high-memory
    systems can capture richer descriptors when set above ``1``.

    Parameters
    ----------
    image_path: str
        Path to the input image.
    bins: int | None
        Base number of bins for the color histogram. If ``None``, ``32`` is
        used before applying the richness multiplier.

    Returns
    -------
    dict
        Dictionary with color histogram, HOG features and edge density.
    """
    richness = settings.FEATURE_RICHNESS
    bins = int((bins or 32) * richness)
    high_memory = _use_high_memory_features(richness)

    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Image not found: {image_path}")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [bins, bins, bins], [0, 180, 0, 256, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cell = max(1, int(8 / richness))
    orientations = max(9, min(18, int(round(9 * (1 + max(0.0, richness - 1.0) * 0.5)))))
    hog_feat = _safe_hog(gray, cell, orientations)

    edges = cv2.Canny(gray, 100, 200)
    edge_density = float(np.count_nonzero(edges)) / float(edges.size)

    features: FeatureDict = {
        "color_hist": hist.tolist(),
        "hog": hog_feat.tolist(),
        "edge_density": edge_density,
    }

    if not high_memory:
        return features

    pyramid_levels = _extra_levels(richness)
    if pyramid_levels:
        pyr_hists: List[np.ndarray] = []
        for scale in _pyramid_scales(pyramid_levels):
            scaled = cv2.resize(
                hsv,
                (max(8, int(hsv.shape[1] * scale)), max(8, int(hsv.shape[0] * scale))),
                interpolation=cv2.INTER_LINEAR,
            )
            extra_bins = min(256, int(bins * (1 + 0.5 * scale)))
            extra_hist = cv2.calcHist(
                [scaled], [0, 1, 2], None, [extra_bins, extra_bins, extra_bins], [0, 180, 0, 256, 0, 256]
            )
            extra_hist = cv2.normalize(extra_hist, extra_hist).flatten()
            pyr_hists.append(extra_hist)
        if pyr_hists:
            features["pyramid_color_hist"] = np.concatenate(pyr_hists).tolist()

    hog_vectors: List[np.ndarray] = []
    for extra_cell in sorted({cell, max(1, cell // 2), min(16, cell * 2)}):
        if extra_cell == cell:
            continue
        hog_vectors.append(_safe_hog(gray, extra_cell, orientations))
    if hog_vectors:
        features["multiscale_hog"] = np.concatenate(hog_vectors).tolist()

    if local_binary_pattern is not None:
        lbp_vectors: List[np.ndarray] = []
        for radius in range(1, min(4, pyramid_levels + 2)):
            points = 8 * radius
            lbp = local_binary_pattern(gray, P=points, R=radius, method="uniform")
            bins_lbp = points + 2
            lbp_hist, _ = np.histogram(lbp, bins=bins_lbp, range=(0, bins_lbp), density=True)
            lbp_vectors.append(lbp_hist.astype(np.float32))
        if lbp_vectors:
            features["lbp_hist"] = np.concatenate(lbp_vectors).tolist()

    hsv_float = hsv.astype(np.float32)
    hsv_float[:, :, 0] /= 180.0
    hsv_float[:, :, 1:] /= 255.0
    color_moments: List[float] = []
    for channel in cv2.split(hsv_float):
        mean_val = float(np.mean(channel))
        std_val = float(np.std(channel))
        centered = channel - mean_val
        skew_val = float(np.mean((centered / (std_val + 1e-6)) ** 3))
        color_moments.extend([mean_val, std_val, skew_val])
    features["color_moments"] = color_moments

    grad_y, grad_x = np.gradient(gray.astype(np.float32) / 255.0)
    grad_mag = np.sqrt(grad_x ** 2 + grad_y ** 2)
    grad_mean = float(np.mean(grad_mag))
    grad_std = float(np.std(grad_mag))
    features["edge_stats"] = [grad_mean, grad_std]
    if grad_mag.max() > 0:
        grad_hist, _ = np.histogram(
            grad_mag,
            bins=32,
            range=(0.0, float(grad_mag.max())),
            density=True,
        )
    else:
        grad_hist = np.zeros(32, dtype=float)
    features["gradient_hist"] = grad_hist.astype(float).tolist()

    # Additional descriptors for top-tier hardware.
    lab_hist = _lab_hist(image, richness)
    features["lab_hist"] = lab_hist.astype(float).tolist()

    gabor_energy = _gabor_energies(gray)
    features["gabor_energy"] = gabor_energy.astype(float).tolist()

    fourier_descriptor = _fourier_descriptor(gray)
    features["fourier_descriptor"] = fourier_descriptor.astype(float).tolist()

    glcm = _glcm_props(gray)
    if glcm is not None:
        features["glcm_props"] = glcm.astype(float).tolist()

    view_hist, view_edges = _augmented_histograms(gray)
    features["view_histograms"] = view_hist.astype(float).tolist()
    features["view_edge_density"] = view_edges.astype(float).tolist()

    features["hu_moments"] = _hu_moments(gray).tolist()
    features["channel_covariance"] = _channel_covariances(image).astype(float).tolist()

    wavelet = _wavelet_energy(gray)
    if wavelet is not None:
        features["wavelet_energy"] = wavelet.astype(float).tolist()

    grid_stats = _grid_lab_stats(image, richness)
    if grid_stats.size:
        features["lab_grid_stats"] = grid_stats.astype(float).tolist()

    deep = _deep_embedding(image)
    if deep is not None:
        features["efficientnet_embedding"] = deep.astype(float).tolist()

    return features


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Extract fused image features")
    parser.add_argument("image", help="Path to image file")
    parser.add_argument("--bins", type=int, default=32, help="Number of histogram bins")
    args = parser.parse_args()

    features = extract_feature_fusion(args.image, bins=args.bins)
    print(json.dumps(features, indent=2)[:1000])
