"""Unified target classifier for troops, vehicles, and drones.

This module demonstrates how a single model can identify multiple target types
rather than maintaining separate classifiers for each category. It loads a
TensorFlow model if provided or builds a small neural network on the fly. The
model is intentionally lightweight and untrained; operators are expected to
train it with their own labeled datasets.
"""

from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from PIL import Image
import tensorflow as tf

# Start with three core classes but allow dynamic expansion.
TARGETS: List[str] = ["troop", "vehicle", "drone"]


def load_unified_model(model_path: Path | str | None = None) -> tf.keras.Model:
    """Load a unified classification model or create a small default network."""
    if model_path and Path(model_path).exists():
        return tf.keras.models.load_model(model_path)
    return tf.keras.Sequential(
        [
            tf.keras.layers.Flatten(input_shape=(128, 128, 3)),
            tf.keras.layers.Dense(32, activation="relu"),
            tf.keras.layers.Dense(len(TARGETS), activation="softmax"),
        ]
    )


def classify_target(image: Path, model: tf.keras.Model) -> Dict[str, Any]:
    """Classify the given image into troop, vehicle, or drone."""
    img = Image.open(image).convert("RGB").resize((128, 128))
    arr = np.expand_dims(np.array(img) / 255.0, 0)
    probs = model(arr, training=False).numpy()[0]
    idx = int(np.argmax(probs))
    return {"target": TARGETS[idx], "confidence": float(probs[idx])}


def add_target_to_model(model: tf.keras.Sequential, label: str) -> tf.keras.Model:
    """Expand the classifier with an output neuron for ``label``.

    The new neuron is initialized with small random weights so operators can
    retrain the model to learn the additional class. ``TARGETS`` is updated in
    place so subsequent classifications include the new label.
    """
    if label in TARGETS:
        return model

    TARGETS.append(label)
    # Rebuild the Sequential model with a larger output layer.
    *base_layers, last = model.layers
    units = last.units + 1
    new_model = tf.keras.Sequential(list(base_layers) + [tf.keras.layers.Dense(units, activation="softmax")])

    w, b = last.get_weights()
    new_w = np.concatenate([w, np.random.normal(scale=0.01, size=(w.shape[0], 1))], axis=1)
    new_b = np.concatenate([b, [0.0]])
    new_model.layers[-1].set_weights([new_w, new_b])
    return new_model
