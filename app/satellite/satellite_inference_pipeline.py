"""Pipeline running detection on Sentinel Hub imagery."""
from pathlib import Path
from typing import List, Dict

import tensorflow as tf

from ..detection import yolo
from ..utils import image_utils
from . import sentinel_hub_fetcher
from ..pipeline import realtime
from ..models import trajectory_model


def run(area: str, model_path: str) -> None:
    """Download imagery for an area and run the detection pipeline."""
    image: Path = sentinel_hub_fetcher.download_image(area)
    image = image_utils.enhance_image(image)
    detections: List[Dict] = yolo.detect_vehicles(image)
    realtime.store_detections(area, detections)

    coords = [[d.get("lat"), d.get("lon")] for d in detections if "lat" in d and "lon" in d]
    if coords:
        sequence = tf.expand_dims(tf.constant(coords, dtype=tf.float32), 0)
        model = trajectory_model.load_model(model_path)
        pred = model(sequence, training=False)[0, -1]
        realtime.store_prediction(area, pred)

    print(f"Detections for {area}: {detections}")
