"""Train a classifier on acoustic sensor features."""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier


def train_acoustic_classifier(csv_path: str, out_path: str) -> None:
    df = pd.read_csv(csv_path)
    X = df.drop("class", axis=1)
    y = df["class"]
    model = RandomForestClassifier(n_estimators=100)
    model.fit(X, y)
    joblib.dump(model, Path(out_path))
