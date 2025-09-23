"""Train a classifier on fused image features."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression

from ..detection.feature_fused_identifier import extract_vector


def train_feature_fused_classifier(images: Sequence[Path], labels: Sequence[str], model_path: Path) -> None:
    """Fit a logistic regression on fused features and save it."""
    X = np.vstack([extract_vector(img) for img in images])
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X, labels)
    joblib.dump(clf, model_path)
