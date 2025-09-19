"""Identify time buckets with sudden detection spikes."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ..database import get_collection


def detect_bursts(
    hours: int = 24,
    bucket_minutes: int = 60,
    z_thresh: float = 2.0,
) -> List[Dict[str, Any]]:
    """Return buckets where detection counts exceed a z-score threshold.

    For each class, detections within the lookback window are grouped into
    ``bucket_minutes``-sized intervals. Buckets whose counts are more than
    ``z_thresh`` standard deviations above the mean are flagged.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    cursor = coll.find({"timestamp": {"$gte": start, "$lt": end}}, {"class": 1, "timestamp": 1})

    buckets: Dict[str, Dict[datetime, int]] = defaultdict(lambda: defaultdict(int))
    for doc in cursor:
        cls = doc.get("class", "unknown")
        ts: datetime = doc["timestamp"]
        bucket = ts - timedelta(
            minutes=ts.minute % bucket_minutes,
            seconds=ts.second,
            microseconds=ts.microsecond,
        )
        buckets[cls][bucket] += 1

    results: List[Dict[str, Any]] = []
    for cls, counts in buckets.items():
        values = list(counts.values())
        if len(values) < 2:
            continue
        mean = sum(values) / len(values)
        var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        std = var ** 0.5
        if std == 0:
            continue
        for bucket, count in counts.items():
            z = (count - mean) / std
            if z >= z_thresh:
                results.append(
                    {
                        "class": cls,
                        "bucket_start": bucket.isoformat(),
                        "count": count,
                        "z": z,
                    }
                )
    results.sort(key=lambda r: r["bucket_start"])
    return results


if __name__ == "__main__":
    import argparse, pprint

    parser = argparse.ArgumentParser(description="Detect bursts in detection counts")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--bucket", type=int, default=60, dest="bucket_minutes")
    parser.add_argument("--z", type=float, default=2.0, dest="z_thresh")
    args = parser.parse_args()
    pprint.pprint(
        detect_bursts(hours=args.hours, bucket_minutes=args.bucket_minutes, z_thresh=args.z_thresh)
    )
