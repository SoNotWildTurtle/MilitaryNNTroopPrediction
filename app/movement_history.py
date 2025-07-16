"""Utility for querying recent movement data from MongoDB."""
from datetime import datetime, timedelta
from typing import List, Dict

from .database import get_collection


def recent_positions(unit_id: str, hours: int = 24) -> List[Dict]:
    """Return recent positions for a unit within the last number of hours."""
    coll = get_collection("movements")
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = {"unit_id": unit_id, "timestamp": {"$gte": cutoff}}
    print(f"Querying movements: {query}")
    return list(coll.find(query))


def recent_detections(area: str, limit: int = 10) -> List[Dict]:
    """Return recent detections for an area."""
    coll = get_collection("detections")
    query = {"area": area}
    cursor = coll.find(query).sort("_id", -1).limit(limit)
    return list(cursor)


def recent_predictions(area: str, limit: int = 10) -> List[Dict]:
    """Return recent trajectory predictions for an area."""
    coll = get_collection("predictions")
    query = {"area": area}
    cursor = coll.find(query).sort("_id", -1).limit(limit)
    return list(cursor)
