"""Utility for querying recent movement data from MongoDB."""
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from .database import get_collection


def recent_positions(
    unit_id: str,
    hours: int = 24,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Dict]:
    """Return positions for a unit within a timeframe.

    Parameters
    ----------
    unit_id: str
        Identifier of the unit to query.
    hours: int, optional
        Lookback window in hours if ``start``/``end`` not provided.
    start: datetime, optional
        Start timestamp for the query.
    end: datetime, optional
        End timestamp for the query.
    """
    coll = get_collection("movements")
    if start or end:
        time_filter: Dict[str, datetime] = {}
        if start:
            time_filter["$gte"] = start
        if end:
            time_filter["$lte"] = end
    else:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        time_filter = {"$gte": cutoff}
    query = {"unit_id": unit_id, "timestamp": time_filter}
    print(f"Querying movements: {query}")
    return list(coll.find(query))


def recent_detections(area: str, limit: int = 10) -> List[Dict]:
    """Return recent detections for an area."""
    coll = get_collection("detections")
    query = {"area": area}
    cursor = coll.find(query).sort("_id", -1).limit(limit)
    return list(cursor)


def recent_predictions(area: str, limit: int = 10) -> List[Dict]:
    """Return recent trajectory predictions for an area."""
    coll = get_collection("predictions")
    query = {"area": area}
    cursor = coll.find(query).sort("_id", -1).limit(limit)
    return list(cursor)
