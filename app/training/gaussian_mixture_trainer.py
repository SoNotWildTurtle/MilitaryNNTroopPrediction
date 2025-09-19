"""Train Gaussian mixture models for sensor features."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import joblib
import pandas as pd
from sklearn.mixture import GaussianMixture


def train_gaussian_mixture_model(csv_path: str, out_path: str, components: int = 2) -> None:
    """Fit per-class Gaussian mixtures and save the model."""
    df = pd.read_csv(csv_path)
    models: Dict[str, GaussianMixture] = {}
    feature_cols = [c for c in df.columns if c != "class"]
    for cls, group in df.groupby("class"):
        gm = GaussianMixture(n_components=components, covariance_type="full")
        gm.fit(group[feature_cols])
        models[cls] = gm
    joblib.dump(models, Path(out_path))
