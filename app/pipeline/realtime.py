"""Real-time pipeline tying data ingestion, detection and prediction."""

from typing import List, Dict

import tensorflow as tf

from .. import data_ingestion
from ..detection import detect_and_tag
from ..models import trajectory_model
from ..utils import image_utils
from ..database import get_collection
from datetime import datetime


def store_detections(area: str, detections: List[Dict]) -> None:
    """Insert raw detections into MongoDB."""
    coll = get_collection("detections")
    if detections:
        now = datetime.utcnow()
        docs = [{**d, "area": area, "timestamp": now} for d in detections]
        coll.insert_many(docs)
        print(f"Stored {len(docs)} detections")


def store_prediction(area: str, prediction: tf.Tensor) -> None:
    """Save predicted trajectory point."""
    coll = get_collection("predictions")
    doc = {
        "area": area,
        "prediction": prediction.numpy().tolist(),
        "timestamp": datetime.utcnow(),
    }
    coll.insert_one(doc)
    print(f"Stored prediction for {area}: {doc}")


def process_area(area: str, model_path: str) -> None:
    """Fetch imagery, detect vehicles and predict trajectories."""
    image = data_ingestion.fetch_satellite_images(area)
    image = image_utils.enhance_image(image)
    detections = detect_and_tag(image)
    store_detections(area, detections)

    coords = [[d.get("lat"), d.get("lon")] for d in detections if "lat" in d and "lon" in d]
    if coords:
        sequence = tf.expand_dims(tf.constant(coords, dtype=tf.float32), 0)
        model = trajectory_model.load_model(model_path)
        pred = model(sequence, training=False)[0, -1]
        store_prediction(area, pred)

    print(f"Detections for {area}: {detections}")
