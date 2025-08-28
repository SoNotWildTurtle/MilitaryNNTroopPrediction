"""Identify peak detection times for each class."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..database import get_collection


def peak_times(days: int = 30) -> List[Dict[str, Any]]:
    """Return the most active hour and weekday for each class.

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
    hour_counts: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    day_counts: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for doc in cursor:
        ts = doc["timestamp"]
        cls = doc.get("class", "unknown")
        hour_counts[cls][ts.hour] += 1
        day_counts[cls][ts.weekday()] += 1
    results: List[Dict[str, Any]] = []
    classes = set(hour_counts.keys()) | set(day_counts.keys())
    for cls in classes:
        h_counts = hour_counts.get(cls, {})
        d_counts = day_counts.get(cls, {})
        peak_hour = max(h_counts.items(), key=lambda kv: kv[1])[0] if h_counts else None
        peak_day = max(d_counts.items(), key=lambda kv: kv[1])[0] if d_counts else None
        results.append({"class": cls, "peak_hour": peak_hour, "peak_day": peak_day})
    return results
