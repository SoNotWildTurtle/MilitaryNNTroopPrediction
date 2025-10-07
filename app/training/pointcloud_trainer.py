"""Train a classifier using point clouds generated from images."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

import numpy as np
from joblib import dump
from sklearn.ensemble import RandomForestClassifier

from ..analysis import image_to_pointcloud


def _pointcloud_features(points: List[tuple[float, float]]) -> List[float]:
    if not points:
        return [0.0, 0.0, 0.0]
    xs, ys = zip(*points)
    cx = float(np.mean(xs))
    cy = float(np.mean(ys))
    spread = float(np.mean(np.sqrt((np.array(xs) - cx) ** 2 + (np.array(ys) - cy) ** 2)))
    return [cx, cy, spread]


def train_pointcloud_classifier(
    image_dir: str | Path,
    labels_csv: str | Path,
    model_path: str | Path = "pointcloud_model.joblib",
) -> Path:
    """Generate point clouds for images and train a classifier.

    ``labels_csv`` should contain rows of ``filename,label``.
    """
    image_dir = Path(image_dir)
    labels_csv = Path(labels_csv)
    model_path = Path(model_path)

    labels: Dict[str, str] = {}
    with labels_csv.open("r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                labels[row[0]] = row[1]

    X: List[List[float]] = []
    y: List[str] = []
    for name, label in labels.items():
        img_path = image_dir / name
        if not img_path.exists():
            continue
        pts = image_to_pointcloud(img_path)
        feats = _pointcloud_features(pts)
        X.append(feats)
        y.append(label)

    if not X:
        raise ValueError("No training samples found")

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X, y)

    dump({"model": clf, "features": ["cx", "cy", "spread"]}, model_path)
    return model_path
