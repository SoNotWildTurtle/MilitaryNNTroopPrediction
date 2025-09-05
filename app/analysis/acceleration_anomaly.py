"""Flag units whose average acceleration deviates from peers."""
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Dict, List

from ..database import get_collection
from .acceleration_stats import acceleration_stats


def acceleration_anomalies(hours: int = 24, z_thresh: float = 2.0) -> List[Dict[str, float]]:
    """Return units with anomalous average accelerations over a window."""
    coll = get_collection("movements")
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    unit_ids = coll.distinct("unit_id", {"timestamp": {"$gte": start, "$lt": end}})

    per_unit: Dict[str, float] = {}
    accels: List[float] = []
    for unit in unit_ids:
        stats = acceleration_stats(unit, hours=hours)
        if stats:
            avg = stats.get("avg_accel_kmh2", 0.0)
            per_unit[unit] = avg
            accels.append(avg)

    if len(accels) < 2:
        return []
    mu = mean(accels)
    sigma = stdev(accels)
    results: List[Dict[str, float]] = []
    for unit, avg in per_unit.items():
        z = (avg - mu) / sigma if sigma else 0.0
        if abs(z) >= z_thresh:
            results.append({"unit_id": unit, "avg_accel_kmh2": avg, "z": z})
    return results


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="List anomalous unit accelerations")
    p.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    p.add_argument("--z", type=float, default=2.0, help="Z-score threshold")
    args = p.parse_args()
    data = acceleration_anomalies(hours=args.hours, z_thresh=args.z)
    for row in data:
        print(f"{row['unit_id']}: {row['avg_accel_kmh2']:.2f} km/h^2 (z={row['z']:.2f})")
