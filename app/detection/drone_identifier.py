"""Basic drone type classifier."""

from pathlib import Path
from typing import Any, Dict
from random import choice, random

DRONE_TYPES = ["quadcopter", "fixed-wing", "helicopter", "unknown"]


def classify_drone(image: Path) -> Dict[str, Any]:
    """Return a mock drone classification for demonstration."""
    drone_type = choice(DRONE_TYPES)
    return {"drone_type": drone_type, "confidence": random()}
