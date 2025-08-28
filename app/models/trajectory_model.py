"""LSTM-based model predicting troop trajectories."""

from typing import Sequence

import tensorflow as tf


class TrajectoryModel(tf.keras.Model):
    """Simple LSTM model stub."""

    def __init__(self, units: int = 64):
        super().__init__()
        self.lstm = tf.keras.layers.LSTM(units, return_sequences=True)
        self.dense = tf.keras.layers.Dense(2)  # lat, lon outputs

    def call(self, inputs, training=False):
        x = self.lstm(inputs)
        return self.dense(x)


def load_model(path: str) -> "TrajectoryModel":
    """Load a saved model from disk."""
    print(f"Loading model from {path}")
    return tf.keras.models.load_model(path)
