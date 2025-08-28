"""Compute per-day detection class diversity using Shannon entropy."""
from collections import defaultdict
from datetime import datetime, timedelta
from math import log2
from typing import Any, Dict, List

from ..database import get_collection


def class_diversity(days: int = 30) -> List[Dict[str, Any]]:
    """Return daily class diversity scores.

    Args:
        days: Number of recent days to include.
    Returns:
        A list of dictionaries with ``date`` and ``entropy`` keys.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    pipeline = [
        {"$match": {"timestamp": {"$gte": start, "$lt": end}}},
        {
            "$group": {
                "_id": {
                    "day": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "class": "$class",
                },
                "count": {"$sum": 1},
            }
        },
    ]
    per_day: Dict[str, Dict[str, int]] = defaultdict(dict)
    for doc in coll.aggregate(pipeline):
        day = doc["_id"]["day"]
        cls = doc["_id"].get("class") or "unknown"
        per_day[day][cls] = doc["count"]

    results: List[Dict[str, Any]] = []
    for day, counts in sorted(per_day.items()):
        total = sum(counts.values())
        if total == 0:
            continue
        entropy = 0.0
        for cnt in counts.values():
            p = cnt / total
            entropy -= p * log2(p)
        results.append({"date": day, "entropy": entropy})
    return results
