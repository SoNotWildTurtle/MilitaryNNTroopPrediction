"""Predict threat levels using a trained classifier."""

from pathlib import Path
from typing import Dict
import joblib
import numpy as np


def predict_threat_level(model_path: Path, features: Dict[str, float]) -> str:
    """Return the predicted threat label for the given feature mapping."""
    data = joblib.load(model_path)
    model = data["model"]
    names = data["features"]
    x = np.array([[features.get(n, 0.0) for n in names]], dtype=float)
    return model.predict(x)[0]


def _parse_args():
    import argparse
    import json

    p = argparse.ArgumentParser(description="Predict threat level from features")
    p.add_argument("model", type=Path, help="Path to trained model joblib")
    p.add_argument("features", type=str, help="JSON mapping of feature values")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    feats = json.loads(args.features)
    label = predict_threat_level(args.model, feats)
    print(label)


if __name__ == "__main__":
    main()
