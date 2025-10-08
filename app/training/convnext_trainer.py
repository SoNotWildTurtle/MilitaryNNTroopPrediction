"""Train a ConvNeXt-based classifier for target identification."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from ..detection.convnext_identifier import load_convnext_components, extract_features

def train_convnext_classifier(images: Sequence[Path], labels: Sequence[str], model_path: Path) -> None:
    """Fit a logistic regression on ConvNeXt embeddings and save it."""
    model, transform = load_convnext_components()
    feats = [extract_features(img, model, transform) for img in images]
    X = np.vstack(feats)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, labels)
    joblib.dump(clf, model_path)
