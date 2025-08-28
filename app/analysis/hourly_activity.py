"""Compute detection counts per class grouped by hour of day."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..database import get_collection


def hourly_activity(days: int = 7) -> List[Dict[str, Any]]:
    """Return detection counts per class for each hour of day.

    Args:
        days: Number of days to look back from now.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    cursor = coll.find(
        {"timestamp": {"$gte": start, "$lt": end}},
        {"class": 1, "timestamp": 1},
    )
    buckets: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for doc in cursor:
        hour = doc["timestamp"].hour
        cls = doc.get("class", "unknown")
        buckets[hour][cls] += 1
    results: List[Dict[str, Any]] = []
    for hour in range(24):
        for cls, count in buckets[hour].items():
            results.append({"hour": hour, "class": cls, "count": count})
    return results
