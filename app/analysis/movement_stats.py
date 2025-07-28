"""Compute movement statistics such as speed and heading."""

from typing import Dict, List
from datetime import datetime
from math import radians, sin, cos, sqrt, atan2, degrees

from ..movement_history import recent_positions

EARTH_RADIUS_KM = 6371.0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in kilometers between two lat/lon points."""
    rlat1 = radians(lat1)
    rlat2 = radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2) ** 2 + cos(rlat1) * cos(rlat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return bearing in degrees from point1 to point2."""
    rlat1 = radians(lat1)
    rlat2 = radians(lat2)
    dlon = radians(lon2 - lon1)

    x = sin(dlon) * cos(rlat2)
    y = cos(rlat1) * sin(rlat2) - sin(rlat1) * cos(rlat2) * cos(dlon)
    brng = atan2(x, y)
    return (degrees(brng) + 360) % 360


def movement_stats(unit_id: str, hours: int = 24) -> Dict[str, float]:
    """Return average speed and heading for a unit."""
    points: List[Dict] = sorted(
        recent_positions(unit_id, hours), key=lambda r: r.get("timestamp", datetime.utcnow())
    )
    if len(points) < 2:
        print("Not enough movement points for statistics")
        return {}

    total_dist = 0.0
    total_time = 0.0
    headings: List[float] = []
    prev = points[0]
    for p in points[1:]:
        lat1, lon1 = float(prev.get("lat", 0)), float(prev.get("lon", 0))
        lat2, lon2 = float(p.get("lat", 0)), float(p.get("lon", 0))
        t1 = prev.get("timestamp") or datetime.utcnow()
        t2 = p.get("timestamp") or datetime.utcnow()
        dist = _haversine(lat1, lon1, lat2, lon2)
        delta_h = max((t2 - t1).total_seconds() / 3600.0, 1e-6)
        total_dist += dist
        total_time += delta_h
        headings.append(_bearing(lat1, lon1, lat2, lon2))
        prev = p

    avg_speed = total_dist / max(total_time, 1e-6)
    max_speed = 0.0
    prev = points[0]
    for p in points[1:]:
        dist = _haversine(
            float(prev.get("lat", 0)),
            float(prev.get("lon", 0)),
            float(p.get("lat", 0)),
            float(p.get("lon", 0)),
        )
        delta_h = max((p.get("timestamp") - prev.get("timestamp")).total_seconds() / 3600.0, 1e-6)
        max_speed = max(max_speed, dist / delta_h)
        prev = p

    avg_heading = sum(headings) / len(headings)
    return {
        "avg_speed_kmh": avg_speed,
        "max_speed_kmh": max_speed,
        "avg_heading_deg": avg_heading,
    }


def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Compute movement statistics")
    p.add_argument("unit_id", help="Unit identifier")
    p.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    stats = movement_stats(args.unit_id, args.hours)
    if stats:
        for k, v in stats.items():
            print(f"{k}: {v:.2f}")


if __name__ == "__main__":
    main()
