"""Classify detected troops into categories."""

from pathlib import Path
from typing import Any, Dict

import numpy as np
from PIL import Image
import tensorflow as tf


def load_classifier(model_path: Path | str) -> tf.keras.Model:
    """Load a TensorFlow model for troop classification."""
    return tf.keras.models.load_model(model_path)


def classify_troop(image: Path, model: tf.keras.Model) -> Dict[str, Any]:
    """Return troop type and uniform predictions for the given image."""
    img = Image.open(image).convert("RGB").resize((128, 128))
    arr = np.expand_dims(np.array(img) / 255.0, 0)
    type_pred, uniform_pred = model.predict(arr, verbose=0)
    type_idx = int(type_pred[0].argmax())
    uniform_idx = int(uniform_pred[0].argmax())
    return {
        "troop_type": type_idx,
        "uniform": uniform_idx,
        "type_conf": float(type_pred[0].max()),
        "uniform_conf": float(uniform_pred[0].max()),
    }
