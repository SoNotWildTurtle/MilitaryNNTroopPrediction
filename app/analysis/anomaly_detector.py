"""Detect anomalous spikes in detection counts."""
from datetime import datetime, timedelta
from typing import Dict, List
from ..database import get_collection


def detect_anomalies(hours: int = 24, baseline_days: int = 7, z_thresh: float = 2.0) -> List[Dict[str, float]]:
    """Return classes whose recent detection rate deviates from baseline.

    Parameters
    ----------
    hours: lookback window for recent activity.
    baseline_days: number of days prior to the window used for baseline rates.
    z_thresh: minimum z-score required to mark a class anomalous.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    baseline_start = start - timedelta(days=baseline_days)

    classes = coll.distinct("class")
    anomalies: List[Dict[str, float]] = []

    for cls in classes:
        recent = coll.count_documents({
            "class": cls,
            "timestamp": {"$gte": start, "$lt": end},
        })
        baseline = coll.count_documents({
            "class": cls,
            "timestamp": {"$gte": baseline_start, "$lt": start},
        })
        baseline_hours = baseline_days * 24
        recent_rate = recent / hours if hours else 0
        baseline_rate = baseline / baseline_hours if baseline_hours else 0
        if baseline_rate <= 0:
            z = float("inf") if recent_rate > 0 else 0
        else:
            std = baseline_rate ** 0.5
            z = (recent_rate - baseline_rate) / std if std else 0
        if z >= z_thresh:
            anomalies.append({
                "class": cls,
                "recent_per_hr": recent_rate,
                "baseline_per_hr": baseline_rate,
                "z": z,
            })
    return anomalies
