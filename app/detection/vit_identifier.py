"""Vision Transformer-based target identifier.

This module extracts embeddings from a pretrained ViT model and applies a
lightweight classifier to identify troops, vehicles, or drones. It serves as a
placeholder demonstrating how transformer features can drive classification.
Operators are expected to train the classifier with their own labeled data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
from PIL import Image
import joblib
import torch
from transformers import ViTFeatureExtractor, ViTModel

CLASSES = ["troop", "vehicle", "drone"]


def load_vit_components() -> Tuple[ViTFeatureExtractor, ViTModel]:
    """Load a pretrained ViT feature extractor and model."""
    extractor = ViTFeatureExtractor.from_pretrained("google/vit-base-patch16-224")
    model = ViTModel.from_pretrained("google/vit-base-patch16-224")
    model.eval()
    return extractor, model


def extract_features(image: Path, extractor: ViTFeatureExtractor, model: ViTModel) -> np.ndarray:
    """Return a pooled embedding for ``image``."""
    img = Image.open(image).convert("RGB")
    inputs = extractor(images=img, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.pooler_output.cpu().numpy()


def load_vit_classifier(model_path: Path | str | None = None):
    """Load a fitted classifier or create an empty logistic regression."""
    if model_path and Path(model_path).exists():
        return joblib.load(model_path)
    from sklearn.linear_model import LogisticRegression

    clf = LogisticRegression(max_iter=1000)
    return clf


def classify_vit(image: Path, clf, extractor: ViTFeatureExtractor, model: ViTModel) -> Dict[str, Any]:
    """Classify ``image`` using ``clf`` and return a label and confidence."""
    feat = extract_features(image, extractor, model)
    if not hasattr(clf, "classes_"):
        # Untrained classifier; return uniform probabilities
        probs = np.full(len(CLASSES), 1 / len(CLASSES))
    else:
        probs = clf.predict_proba(feat)[0]
    idx = int(np.argmax(probs))
    return {"target": CLASSES[idx], "confidence": float(probs[idx])}

