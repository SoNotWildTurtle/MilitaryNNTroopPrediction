"""Detection helpers for ground troops in challenging imagery."""

from pathlib import Path
from typing import List, Dict

from PIL import Image

from . import yolo
from ..utils import image_utils


def detect_ground_troops(image: Path) -> List[Dict]:
    """Run detection on multiple orientations to improve recall."""
    processed = image_utils.prepare_ground_troop_image(image)
    angles = [0, 90, 180, 270]
    detections: List[Dict] = []
    for angle in angles:
        img = Image.open(processed).rotate(angle)
        tmp = processed.parent / f"rot_{angle}_{processed.name}"
        img.save(tmp)
        detections.extend(yolo.detect_vehicles(tmp))
        tmp.unlink(missing_ok=True)
    return detections
