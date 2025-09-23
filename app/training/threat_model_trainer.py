"""Train a classifier to predict threat levels from cluster features."""

from pathlib import Path
import csv
from typing import Tuple, List

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report


def _load_dataset(csv_path: Path) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Load feature matrix ``X`` and labels ``y`` from a CSV file."""
    with csv_path.open() as f:
        reader = csv.DictReader(f)
        feature_names = [c for c in reader.fieldnames if c != "label"]
        X, y = [], []
        for row in reader:
            X.append([float(row[c]) for c in feature_names])
            y.append(row["label"])
    return np.array(X, dtype=float), np.array(y), feature_names


def train_threat_model(
    csv_path: Path, out_model: Path, algorithm: str = "logistic"
) -> None:
    """Fit a classifier on cluster features and save it with feature ordering."""
    X, y, feature_names = _load_dataset(csv_path)

    if algorithm == "forest":
        clf = RandomForestClassifier(n_estimators=100, random_state=0)
    else:
        clf = LogisticRegression(max_iter=1000)

    clf.fit(X, y)
    preds = clf.predict(X)
    print(classification_report(y, preds))
    joblib.dump({"model": clf, "features": feature_names}, out_model)


def _parse_args():
    import argparse

    p = argparse.ArgumentParser(description="Train threat level classifier")
    p.add_argument("csv_path", type=Path)
    p.add_argument("out_model", type=Path)
    p.add_argument("--algo", choices=["logistic", "forest"], default="logistic")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    train_threat_model(args.csv_path, args.out_model, algorithm=args.algo)


if __name__ == "__main__":
    main()
