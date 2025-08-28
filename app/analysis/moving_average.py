"""Compute moving average of daily detection counts per class."""
from collections import defaultdict, deque
from datetime import datetime, timedelta, date
from typing import Any, Dict, List

from ..database import get_collection


def moving_average(days: int = 30, window: int = 7) -> List[Dict[str, Any]]:
    """Return rolling-average detection counts per class.

    Args:
        days: Number of recent days to analyze.
        window: Size of the rolling window in days.
    Returns:
        A list of dictionaries with keys ``date``, ``class`` and ``avg``.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    cursor = coll.find(
        {"timestamp": {"$gte": start, "$lt": end}},
        {"class": 1, "timestamp": 1},
    )
    # Organize counts per class and day
    counts: Dict[str, Dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for doc in cursor:
        day = doc["timestamp"].date()
        cls = doc.get("class", "unknown")
        counts[cls][day] += 1
    results: List[Dict[str, Any]] = []
    for cls, day_counts in counts.items():
        q: deque[Any] = deque()
        running = 0
        for day in sorted(day_counts.keys()):
            c = day_counts[day]
            q.append((day, c))
            running += c
            while q and (day - q[0][0]).days >= window:
                old_day, old_c = q.popleft()
                running -= old_c
            avg = running / len(q)
            results.append({"date": day.isoformat(), "class": cls, "avg": avg})
    return results
