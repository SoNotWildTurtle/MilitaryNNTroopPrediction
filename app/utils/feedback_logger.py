"""Utilities for logging human feedback to MongoDB."""

from datetime import datetime
from typing import Dict, Any

from ..database import get_collection


def log_feedback(record: Dict[str, Any]) -> None:
    """Insert a feedback record into the `feedback` collection.

    Parameters
    ----------
    record: dict
        Should include at least `filename`, `predicted`, `confidence`, and `correct`.
    """
    data = dict(record)
    data["timestamp"] = datetime.utcnow()
    try:
        col = get_collection("feedback")
        col.insert_one(data)
    except Exception:
        # If MongoDB is unavailable, fail silently so GUI still works
        pass

