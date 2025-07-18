"""YOLOv8 detection wrapper."""

from pathlib import Path
from typing import List, Dict
from random import random


def detect_vehicles(image: Path) -> List[Dict]:
    """Run YOLO detection on a satellite image.

    This function currently returns a few mock detections with random
    coordinates to demonstrate the pipeline without requiring heavy
    model downloads. Replace this with a real YOLOv8 call when models
    are available.
    """

    print(f"Running YOLO detection on {image}")
    detections: List[Dict] = []
    for _ in range(3):
        detections.append(
            {
                "lat": 50 + random(),
                "lon": 30 + random(),
                "confidence": 0.5,
            }
        )
    return detections
