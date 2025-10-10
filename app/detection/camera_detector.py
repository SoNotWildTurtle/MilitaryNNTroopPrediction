"""Mock camera-based detection for troops, vehicles, and drones."""
from __future__ import annotations

from pathlib import Path
from random import random, choice
from typing import Dict, List

CLASSES = ["troop", "vehicle", "drone"]


def _mock_detection(cls: str) -> Dict[str, float]:
    """Return a fake detection record for a single class."""
    return {
        "class": cls,
        "confidence": random(),
    }


def detect_camera_troops(image: Path) -> List[Dict[str, float]]:
    """Detect ground troops from an image."""
    return [_mock_detection("troop") for _ in range(2)]


def detect_camera_vehicles(image: Path) -> List[Dict[str, float]]:
    """Detect vehicles from an image."""
    return [_mock_detection("vehicle") for _ in range(2)]


def detect_camera_drones(image: Path) -> List[Dict[str, float]]:
    """Detect drones from an image."""
    return [_mock_detection("drone") for _ in range(2)]


def detect_camera_objects(image: Path) -> List[Dict[str, float]]:
    """Detect assorted objects from an image."""
    return [_mock_detection(choice(CLASSES)) for _ in range(3)]
