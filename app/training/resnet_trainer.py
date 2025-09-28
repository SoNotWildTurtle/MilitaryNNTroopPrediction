"""Train a ResNet-based classifier for target identification."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from ..detection.resnet_identifier import load_resnet_components, extract_features


def train_resnet_classifier(images: Sequence[Path], labels: Sequence[str], model_path: Path) -> None:
    """Fit a logistic regression on ResNet embeddings and save it."""
    model, transform = load_resnet_components()
    feats = [extract_features(img, model, transform) for img in images]
    X = np.vstack(feats)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, labels)
    joblib.dump(clf, model_path)
