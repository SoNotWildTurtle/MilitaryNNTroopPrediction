"""Compute class co-occurrence counts from recent detections."""
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from typing import Dict, Any, List

from ..database import get_collection


def class_cooccurrence(window_hours: int = 24) -> Dict[str, Dict[str, int]]:
    """Return pairwise co-occurrence counts for detection classes.

    Detections are grouped by their exact timestamp. For each detection event,
    the set of unique classes is used to increment counts for every class pair
    appearing together. The result is a nested mapping where ``matrix[a][b]``
    is the number of events containing both classes ``a`` and ``b`` within the
    lookback window.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(hours=window_hours)
    cursor = coll.find({"timestamp": {"$gte": start, "$lt": end}}, {"class": 1, "timestamp": 1})

    events: Dict[datetime, set] = defaultdict(set)
    for doc in cursor:
        ts = doc["timestamp"]
        cls = doc.get("class", "unknown")
        events[ts].add(cls)

    matrix: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for classes in events.values():
        for a, b in combinations(sorted(classes), 2):
            matrix[a][b] += 1
            matrix[b][a] += 1

    # Convert nested defaultdicts to normal dicts for easier consumption
    return {a: dict(b) for a, b in matrix.items()}
