"""Mock LIDAR-based detection for troops, vehicles, and drones."""
from __future__ import annotations

from pathlib import Path
from random import random, choice
from typing import Dict, List

CLASSES = ["troop", "vehicle", "drone"]


def _mock_detection(cls: str) -> Dict[str, float | bool]:
    """Return a fake detection record for a single class.

    The mock also estimates whether the object is hidden by foliage based on a
    random draw, exposing an ``in_cover`` flag used by downstream fusion.
    """
    return {
        "class": cls,
        "confidence": random(),
        "in_cover": random() > 0.5,
    }


def detect_lidar_troops(point_cloud: Path) -> List[Dict[str, float | bool]]:
    """Detect ground troops from a LIDAR point cloud.

    Each detection includes an ``in_cover`` flag indicating if the unit appears
    to be under foliage or other cover.
    """
    return [_mock_detection("troop") for _ in range(2)]


def detect_lidar_vehicles(point_cloud: Path) -> List[Dict[str, float | bool]]:
    """Detect vehicles from a LIDAR point cloud.

    Returns detections with ``in_cover`` flags.
    """
    return [_mock_detection("vehicle") for _ in range(2)]


def detect_lidar_drones(point_cloud: Path) -> List[Dict[str, float | bool]]:
    """Detect drones from a LIDAR point cloud.

    Returns detections with ``in_cover`` flags.
    """
    return [_mock_detection("drone") for _ in range(2)]


def detect_lidar_objects(point_cloud: Path) -> List[Dict[str, float | bool]]:
    """Detect assorted objects from a LIDAR point cloud.

    Each record contains an ``in_cover`` flag.
    """
    return [_mock_detection(choice(CLASSES)) for _ in range(3)]
