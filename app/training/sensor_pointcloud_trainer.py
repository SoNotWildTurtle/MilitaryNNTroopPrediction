"""Train a classifier using sensor features and image-derived point clouds."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import List

import numpy as np
from joblib import dump
from sklearn.ensemble import RandomForestClassifier

from ..analysis import image_to_pointcloud3d


def _pc_stats(points: List[tuple[float, float, float]]) -> List[float]:
    if not points:
        return [0.0, 0.0, 0.0, 0.0]
    xs, ys, zs = zip(*points)
    return [
        float(np.mean(xs)),
        float(np.mean(ys)),
        float(np.mean(zs)),
        float(np.std(zs)),
    ]


def train_sensor_pointcloud_model(
    csv_path: str | Path,
    image_dir: str | Path,
    model_path: str | Path = "sensor_pointcloud_model.joblib",
) -> Path:
    """Train a classifier that combines sensor CSV features with image point clouds.

    The CSV must contain feature columns, an ``image`` filename column, and a
    ``label`` column.
    """
    csv_path = Path(csv_path)
    image_dir = Path(image_dir)
    model_path = Path(model_path)

    with csv_path.open("r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [row for row in reader if row]

    if not rows:
        raise ValueError("No training data found")

    try:
        img_idx = header.index("image")
        label_idx = header.index("label")
    except ValueError as exc:
        raise ValueError("CSV must contain 'image' and 'label' columns") from exc

    feature_idx = [i for i in range(len(header)) if i not in (img_idx, label_idx)]

    X: List[List[float]] = []
    y: List[str] = []
    for row in rows:
        img_file = image_dir / row[img_idx]
        points = image_to_pointcloud3d(img_file)
        feats = _pc_stats(points)
        sensor_feats = [float(row[i]) for i in feature_idx]
        X.append(sensor_feats + feats)
        y.append(row[label_idx])

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X, y)

    dump(
        {
            "model": clf,
            "features": [header[i] for i in feature_idx]
            + ["cx", "cy", "cz", "std_z"],
        },
        model_path,
    )
    return model_path
