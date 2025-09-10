"""Compute detection counts per class grouped by day of week."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..database import get_collection


def weekly_activity(weeks: int = 4) -> List[Dict[str, Any]]:
    """Return detection counts per class for each day of the week.

    Args:
        weeks: Number of weeks to look back from now.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(weeks=weeks)
    cursor = coll.find(
        {"timestamp": {"$gte": start, "$lt": end}},
        {"class": 1, "timestamp": 1},
    )
    buckets: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for doc in cursor:
        day = doc["timestamp"].weekday()
        cls = doc.get("class", "unknown")
        buckets[day][cls] += 1
    results: List[Dict[str, Any]] = []
    for day in range(7):
        for cls, count in buckets[day].items():
            results.append({"day": day, "class": cls, "count": count})
    return results
