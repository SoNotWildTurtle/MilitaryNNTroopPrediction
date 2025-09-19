"""Classify images using fused color, Lab, HOG, texture, and edge features."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import numpy as np

from ..analysis.feature_fusion import extract_feature_fusion


def load_feature_fused_classifier(path: Path | str) -> Any:
    """Load a scikit-learn classifier trained on fused features."""
    return joblib.load(path)


def extract_vector(image: Path) -> np.ndarray:
    """Convert fused feature dict into a single feature vector."""
    feats = extract_feature_fusion(str(image))
    parts = []
    for key in sorted(feats):
        value = feats[key]
        if isinstance(value, dict):
            sub = []
            for sub_key in sorted(value):
                sub_val = value[sub_key]
                if isinstance(sub_val, (list, tuple, np.ndarray)):
                    sub.append(np.asarray(sub_val, dtype=float).ravel())
                else:
                    sub.append(np.asarray([sub_val], dtype=float))
            parts.append(np.concatenate(sub))
            continue
        if isinstance(value, (list, tuple, np.ndarray)):
            parts.append(np.asarray(value, dtype=float).ravel())
        else:
            parts.append(np.asarray([value], dtype=float))
    return np.concatenate(parts)


def classify_feature_fused(image: Path, clf: Any) -> Dict[str, Any]:
    """Return label and confidence for ``image`` using ``clf``."""
    vec = extract_vector(image)
    probs = clf.predict_proba([vec])[0]
    idx = int(np.argmax(probs))
    return {"target": clf.classes_[idx], "confidence": float(probs[idx])}
