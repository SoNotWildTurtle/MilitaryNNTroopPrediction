"""Basic vehicle type classifier."""

from pathlib import Path
from typing import Any, Dict
from random import choice, random

VEHICLE_TYPES = ["tank", "truck", "apc", "artillery", "unknown"]


def classify_vehicle(image: Path) -> Dict[str, Any]:
    """Return a mock vehicle classification for demonstration."""
    vehicle_type = choice(VEHICLE_TYPES)
    return {"vehicle_type": vehicle_type, "confidence": random()}
