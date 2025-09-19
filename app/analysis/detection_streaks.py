"""Compute longest detection streak per class."""
from collections import defaultdict
from datetime import datetime, timedelta, date
from typing import Any, Dict, List

from ..database import get_collection


def detection_streaks(days: int = 30) -> List[Dict[str, Any]]:
    """Return longest consecutive-day detection streak for each class.

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
    dates: Dict[str, set[date]] = defaultdict(set)
    for doc in cursor:
        ts = doc["timestamp"]
        cls = doc.get("class", "unknown")
        dates[cls].add(ts.date())
    results: List[Dict[str, Any]] = []
    for cls, days_set in dates.items():
        if not days_set:
            continue
        sorted_days = sorted(days_set)
        max_streak = cur_streak = 1
        for prev, curr in zip(sorted_days, sorted_days[1:]):
            if (curr - prev).days == 1:
                cur_streak += 1
            else:
                max_streak = max(max_streak, cur_streak)
                cur_streak = 1
        max_streak = max(max_streak, cur_streak)
        results.append({"class": cls, "max_streak": max_streak})
    return results
