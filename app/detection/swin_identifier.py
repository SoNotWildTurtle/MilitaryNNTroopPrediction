"""Swin Transformer-based target identifier."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import joblib
import numpy as np
from PIL import Image
import torch
from torchvision import models, transforms

CLASSES = ["troop", "vehicle", "drone"]


def load_swin_components() -> Tuple[torch.nn.Module, transforms.Compose]:
    """Load a pretrained Swin-T model and image transforms."""
    weights = models.Swin_T_Weights.DEFAULT
    model = models.swin_t(weights=weights)
    model.head = torch.nn.Identity()
    model.eval()
    transform = weights.transforms()
    return model, transform


def extract_features(image: Path, model: torch.nn.Module, transform: transforms.Compose) -> np.ndarray:
    """Return flattened Swin features for ``image``."""
    img = Image.open(image).convert("RGB")
    tensor = transform(img).unsqueeze(0)
    with torch.no_grad():
        feats = model(tensor)
    return feats.cpu().numpy()


def load_swin_classifier(model_path: Path | str | None = None):
    """Load a fitted classifier or create an empty logistic regression."""
    if model_path and Path(model_path).exists():
        return joblib.load(model_path)
    from sklearn.linear_model import LogisticRegression

    return LogisticRegression(max_iter=1000)


def classify_swin(
    image: Path,
    clf,
    model: torch.nn.Module,
    transform: transforms.Compose,
) -> Dict[str, Any]:
    """Classify ``image`` using ``clf`` and return label and confidence."""
    feat = extract_features(image, model, transform)
    if not hasattr(clf, "classes_"):
        probs = np.full(len(CLASSES), 1 / len(CLASSES))
    else:
        probs = clf.predict_proba(feat)[0]
    idx = int(np.argmax(probs))
    return {"target": CLASSES[idx], "confidence": float(probs[idx])}
