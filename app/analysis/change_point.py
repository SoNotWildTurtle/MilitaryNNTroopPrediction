"""Detect significant changes in daily detection counts."""
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List
import statistics

from ..database import get_collection


def change_points(days: int = 30, z_thresh: float = 2.0) -> List[Dict[str, Any]]:
    """Return change points where daily counts shift sharply.

    Args:
        days: Lookback window in days.
        z_thresh: Minimum z-score of day-to-day change to report.
    """
    coll = get_collection("detections")
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    cursor = coll.find({"timestamp": {"$gte": start, "$lt": end}}, {"class": 1, "timestamp": 1})
    counts: Dict[str, Dict[datetime, int]] = defaultdict(lambda: defaultdict(int))
    for doc in cursor:
        ts = doc["timestamp"].date()
        cls = doc.get("class", "unknown")
        counts[cls][ts] += 1
    results: List[Dict[str, Any]] = []
    for cls, day_map in counts.items():
        dates = sorted(day_map)
        if len(dates) < 2:
            continue
        daily = [day_map[d] for d in dates]
        diffs = [daily[i] - daily[i - 1] for i in range(1, len(daily))]
        if len(diffs) < 2:
            continue
        mean = statistics.mean(diffs)
        std = statistics.pstdev(diffs) or 1.0
        for idx, diff in enumerate(diffs, start=1):
            z = (diff - mean) / std
            if abs(z) >= z_thresh:
                results.append({
                    "class": cls,
                    "date": dates[idx].isoformat(),
                    "change": diff,
                    "z": z,
                })
    return results


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Detect change points in daily counts")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days")
    parser.add_argument("--z", type=float, default=2.0, help="Z-score threshold")
    args = parser.parse_args()
    out = change_points(days=args.days, z_thresh=args.z)
    print(json.dumps(out, indent=2))
