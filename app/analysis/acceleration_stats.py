"""Compute acceleration statistics from movement logs."""
from typing import Dict, List, Optional
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2

from ..movement_history import recent_positions

EARTH_RADIUS_KM = 6371.0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in kilometers between two lat/lon points."""
    rlat1, rlat2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def acceleration_stats(
    unit_id: str,
    hours: int = 24,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Dict[str, float]:
    """Return average and max acceleration for a unit."""
    points: List[Dict] = sorted(
        recent_positions(unit_id, hours, start=start, end=end),
        key=lambda r: r.get("timestamp", datetime.utcnow()),
    )
    if len(points) < 3:
        print("Not enough movement points for acceleration stats")
        return {}

    speeds: List[float] = []
    prev = points[0]
    for p in points[1:]:
        lat1, lon1 = float(prev.get("lat", 0)), float(prev.get("lon", 0))
        lat2, lon2 = float(p.get("lat", 0)), float(p.get("lon", 0))
        t1 = prev.get("timestamp") or datetime.utcnow()
        t2 = p.get("timestamp") or datetime.utcnow()
        dist = _haversine(lat1, lon1, lat2, lon2)
        dt = max((t2 - t1).total_seconds() / 3600.0, 1e-6)
        speeds.append(dist / dt)
        prev = p

    accels: List[float] = []
    prev_speed = speeds[0]
    for i in range(2, len(points)):
        speed = speeds[i - 1]
        t_prev = points[i - 1].get("timestamp") or datetime.utcnow()
        t_curr = points[i].get("timestamp") or datetime.utcnow()
        dt = max((t_curr - t_prev).total_seconds() / 3600.0, 1e-6)
        accels.append((speed - prev_speed) / dt)
        prev_speed = speed

    if not accels:
        return {}
    avg_accel = sum(abs(a) for a in accels) / len(accels)
    max_accel = max(abs(a) for a in accels)
    return {"avg_accel_kmh2": avg_accel, "max_accel_kmh2": max_accel}


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Compute unit acceleration stats")
    p.add_argument("unit_id", help="Unit identifier")
    p.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    args = p.parse_args()
    stats = acceleration_stats(args.unit_id, hours=args.hours)
    if stats:
        for k, v in stats.items():
            print(f"{k}: {v:.2f}")
