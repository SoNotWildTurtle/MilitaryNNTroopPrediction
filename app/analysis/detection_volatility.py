"""Compute detection count volatility per class."""
from collections import defaultdict
from datetime import datetime, timedelta, date
from typing import Any, Dict, List

from ..database import get_collection


def detection_volatility(days: int = 30) -> List[Dict[str, Any]]:
    """Return average and standard deviation of daily counts per class.

    Args:
        days: Number of recent days to analyze.
    Returns:
        A list of dictionaries with ``class``, ``avg`` and ``std`` keys.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    cursor = coll.find(
        {"timestamp": {"$gte": start, "$lt": end}},
        {"class": 1, "timestamp": 1},
    )
    counts: Dict[str, Dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for doc in cursor:
        day = doc["timestamp"].date()
        cls = doc.get("class", "unknown")
        counts[cls][day] += 1
    results: List[Dict[str, Any]] = []
    for cls, day_counts in counts.items():
        vals = list(day_counts.values())
        avg = sum(vals) / len(vals)
        var = sum((v - avg) ** 2 for v in vals) / len(vals)
        std = var ** 0.5
        results.append({"class": cls, "avg": avg, "std": std})
    return results
