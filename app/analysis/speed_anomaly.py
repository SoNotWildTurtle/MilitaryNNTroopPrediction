"""Flag units whose average speed deviates significantly from peers."""
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Dict, List

from ..database import get_collection
from .movement_stats import movement_stats


def speed_anomalies(hours: int = 24, z_thresh: float = 2.0) -> List[Dict[str, float]]:
    """Return units with anomalous average speeds over a lookback window.

    Parameters
    ----------
    hours: int
        Number of recent hours to analyze.
    z_thresh: float
        Minimum absolute z-score required to flag a unit.
    """
    coll = get_collection("movements")
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    unit_ids = coll.distinct("unit_id", {"timestamp": {"$gte": start, "$lt": end}})
    speeds: List[float] = []
    per_unit: Dict[str, float] = {}
    for unit in unit_ids:
        stats = movement_stats(unit, hours=hours)
        if stats:
            avg = stats.get("avg_speed_kmh", 0.0)
            per_unit[unit] = avg
            speeds.append(avg)
    if len(speeds) < 2:
        return []
    mu = mean(speeds)
    sigma = stdev(speeds)
    results: List[Dict[str, float]] = []
    for unit, avg in per_unit.items():
        z = (avg - mu) / sigma if sigma else 0.0
        if abs(z) >= z_thresh:
            results.append({"unit_id": unit, "avg_speed_kmh": avg, "z": z})
    return results


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="List anomalous unit speeds")
    p.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    p.add_argument("--z", type=float, default=2.0, help="Z-score threshold")
    args = p.parse_args()
    data = speed_anomalies(hours=args.hours, z_thresh=args.z)
    for row in data:
        print(f"{row['unit_id']}: {row['avg_speed_kmh']:.2f} km/h (z={row['z']:.2f})")
