"""Compute per-class detection counts grouped by day."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..database import get_collection


def detection_trends(days: int = 7) -> List[Dict[str, Any]]:
    """Return detection counts per class for each day in the lookback window."""
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    cursor = coll.find(
        {"timestamp": {"$gte": start, "$lt": end}},
        {"class": 1, "timestamp": 1},
    )
    buckets: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for doc in cursor:
        day = doc["timestamp"].date().isoformat()
        cls = doc.get("class", "unknown")
        buckets[day][cls] += 1
    results: List[Dict[str, Any]] = []
    for day in sorted(buckets.keys()):
        for cls, count in buckets[day].items():
            results.append({"date": day, "class": cls, "count": count})
    return results
