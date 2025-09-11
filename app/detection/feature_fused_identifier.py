"""Classify images using fused color, HOG, and edge features."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import joblib
import numpy as np

from ..analysis.feature_fusion import extract_feature_fusion


def load_feature_fused_classifier(path: Path | str) -> Any:
    """Load a scikit-learn classifier trained on fused features."""
    return joblib.load(path)


def extract_vector(image: Path) -> np.ndarray:
    """Convert fused feature dict into a single feature vector."""
    feats = extract_feature_fusion(str(image))
    return np.concatenate([feats["color_hist"], feats["hog"], [feats["edge_density"]]])


def classify_feature_fused(image: Path, clf: Any) -> Dict[str, Any]:
    """Return label and confidence for ``image`` using ``clf``."""
    vec = extract_vector(image)
    probs = clf.predict_proba([vec])[0]
    idx = int(np.argmax(probs))
    return {"target": clf.classes_[idx], "confidence": float(probs[idx])}
