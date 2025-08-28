"""Compute time-lag correlation between two detection classes."""
from datetime import datetime, timedelta
from typing import List, Dict

from ..database import get_collection


def _pearson(a: List[int], b: List[int]) -> float:
    """Return the Pearson correlation between two equal-length sequences."""
    n = len(a)
    if n < 2:
        return 0.0
    mean_a = sum(a) / n
    mean_b = sum(b) / n
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a == 0 or var_b == 0:
        return 0.0
    return cov / (var_a ** 0.5 * var_b ** 0.5)


def lag_correlation(
    class_a: str,
    class_b: str,
    hours: int = 24,
    bucket_minutes: int = 60,
    max_lag: int = 3,
) -> List[Dict[str, float]]:
    """Compute correlation of ``class_a`` followed by ``class_b`` across lags.

    Returns a list of dictionaries where each entry contains the lag in minutes
    and the correlation coefficient between the two time series with that lag.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    bucket_seconds = bucket_minutes * 60
    buckets = int(hours * 60 / bucket_minutes)
    counts_a = [0] * buckets
    counts_b = [0] * buckets

    cursor = coll.find(
        {
            "timestamp": {"$gte": start, "$lt": end},
            "class": {"$in": [class_a, class_b]},
        },
        {"class": 1, "timestamp": 1},
    )
    for doc in cursor:
        ts = doc["timestamp"]
        idx = int((ts - start).total_seconds() / bucket_seconds)
        if idx >= buckets:
            idx = buckets - 1
        if doc.get("class") == class_a:
            counts_a[idx] += 1
        else:
            counts_b[idx] += 1

    results: List[Dict[str, float]] = []
    for lag in range(0, max_lag + 1):
        a_series = counts_a[lag:]
        b_series = counts_b[: buckets - lag]
        corr = _pearson(a_series, b_series) if a_series and b_series else 0.0
        results.append({"lag": lag * bucket_minutes, "corr": corr})
    return results
