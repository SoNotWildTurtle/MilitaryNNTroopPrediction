"""Combine multiple image descriptors for robust object identification.

This module extracts several complementary features from an image:
- color histogram in HSV space
- Histogram of Oriented Gradients (HOG)
- edge density via Canny edges

These features can help downstream classifiers distinguish between
similar looking troops, vehicles, and drones.
"""

from __future__ import annotations

from typing import Dict, List

import cv2
import numpy as np
from skimage.feature import hog


def extract_feature_fusion(image_path: str, bins: int = 32) -> Dict[str, List[float]]:
    """Return combined descriptors for an image.

    Parameters
    ----------
    image_path: str
        Path to the input image.
    bins: int, default 32
        Number of bins for the color histogram.

    Returns
    -------
    dict
        Dictionary with color histogram, HOG features and edge density.
    """
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Image not found: {image_path}")

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [bins, bins, bins], [0, 180, 0, 256, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hog_feat = hog(gray, pixels_per_cell=(8, 8), cells_per_block=(2, 2), feature_vector=True)

    edges = cv2.Canny(gray, 100, 200)
    edge_density = float(np.count_nonzero(edges)) / float(edges.size)

    return {
        "color_hist": hist.tolist(),
        "hog": hog_feat.tolist(),
        "edge_density": edge_density,
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Extract fused image features")
    parser.add_argument("image", help="Path to image file")
    parser.add_argument("--bins", type=int, default=32, help="Number of histogram bins")
    args = parser.parse_args()

    features = extract_feature_fusion(args.image, bins=args.bins)
    print(json.dumps(features, indent=2)[:1000])
