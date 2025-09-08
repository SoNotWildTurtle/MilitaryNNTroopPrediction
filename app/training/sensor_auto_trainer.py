"""Train a simple classifier on sensor feature CSV files."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import List

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from joblib import dump


def train_sensor_model(csv_path: str | Path, model_path: str | Path = "sensor_model.joblib") -> Path:
    """Load feature rows from ``csv_path`` and train a classifier.

    The CSV is expected to have feature columns followed by a ``label`` column.
    The trained model and feature ordering are saved with :mod:`joblib`.
    """
    csv_path = Path(csv_path)
    model_path = Path(model_path)

    with csv_path.open("r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = [row for row in reader if row]

    if not rows:
        raise ValueError("No training data found")

    X = np.array([[float(v) for v in row[:-1]] for row in rows])
    y = np.array([row[-1] for row in rows])

    clf = RandomForestClassifier(n_estimators=100, random_state=42)
    clf.fit(X, y)

    dump({"model": clf, "features": header[:-1]}, model_path)
    return model_path


def auto_train_directory(csv_dir: str | Path, out_dir: str | Path | None = None) -> List[Path]:
    """Train a model for every CSV file in ``csv_dir``.

    Each ``*.csv`` file is passed to :func:`train_sensor_model`. Models are saved
    alongside the CSV or in ``out_dir`` if provided. Returns the list of model
    paths that were generated.
    """

    csv_dir = Path(csv_dir)
    out_dir = Path(out_dir) if out_dir else csv_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    models: List[Path] = []
    for csv_file in csv_dir.glob("*.csv"):
        model_path = out_dir / f"{csv_file.stem}.joblib"
        models.append(train_sensor_model(csv_file, model_path))
    return models
