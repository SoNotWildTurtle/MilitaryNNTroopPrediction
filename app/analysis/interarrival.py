"""Compute time between successive detections for each class."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..database import get_collection


def interarrival_times(days: int = 30) -> List[Dict[str, Any]]:
    """Return average and median hours between detections per class.

    Args:
        days: Number of recent days to analyze.
    Returns:
        A list of dictionaries with ``class``, ``avg_hours`` and ``median_hours``.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    cursor = coll.find(
        {"timestamp": {"$gte": start, "$lt": end}},
        {"class": 1, "timestamp": 1},
        sort=[("timestamp", 1)],
    )
    prev: Dict[str, datetime] = {}
    gaps: Dict[str, List[float]] = defaultdict(list)
    for doc in cursor:
        ts: datetime = doc["timestamp"]
        cls = doc.get("class", "unknown")
        if cls in prev:
            delta = (ts - prev[cls]).total_seconds() / 3600.0
            gaps[cls].append(delta)
        prev[cls] = ts
    results: List[Dict[str, Any]] = []
    for cls, values in gaps.items():
        if not values:
            continue
        avg = sum(values) / len(values)
        sorted_vals = sorted(values)
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 0:
            median = (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
        else:
            median = sorted_vals[mid]
        results.append({
            "class": cls,
            "avg_hours": avg,
            "median_hours": median,
        })
    return results
