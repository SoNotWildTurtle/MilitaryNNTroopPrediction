"""Detection utilities."""

from .yolo import detect_vehicles
from .ground_troop import detect_ground_troops
from .troop_identifier import load_classifier as load_troop_classifier, classify_troop
from .drone_identifier import classify_drone

__all__ = [
    "detect_vehicles",
    "detect_ground_troops",
    "load_troop_classifier",
    "classify_troop",
    "classify_drone",
]
