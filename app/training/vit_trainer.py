"""Train a ViT-based classifier for target identification."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import joblib
from sklearn.linear_model import LogisticRegression

from ..detection.vit_identifier import load_vit_components, extract_features


def train_vit_classifier(images: Sequence[Path], labels: Sequence[str], model_path: Path) -> None:
    """Fit a logistic regression on ViT embeddings and save it."""
    extractor, vit = load_vit_components()
    feats = [extract_features(img, extractor, vit) for img in images]
    X = np.vstack(feats)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, labels)
    joblib.dump(clf, model_path)

