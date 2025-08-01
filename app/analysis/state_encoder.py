"""Encode detection history into a grid tensor."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np

from ..database import get_collection


def encode_state(area: str, hours: int = 24, resolution: int = 20) -> Optional[np.ndarray]:
    """Return a grid tensor showing detection counts over the specified period."""
    coll = get_collection("detections")
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    cursor = coll.find({"area": area, "timestamp": {"$gte": cutoff}})
    coords = [(d.get("lat"), d.get("lon")) for d in cursor if "lat" in d and "lon" in d]

    if not coords:
        print("No detections found for encoding")
        return None

    lats = [c[0] for c in coords]
    lons = [c[1] for c in coords]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    grid = np.zeros((resolution, resolution), dtype=np.float32)
    lat_range = max_lat - min_lat or 1e-6
    lon_range = max_lon - min_lon or 1e-6

    for lat, lon in coords:
        x_idx = int((lon - min_lon) / lon_range * (resolution - 1))
        y_idx = int((lat - min_lat) / lat_range * (resolution - 1))
        grid[y_idx, x_idx] += 1.0

    return grid


def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Encode detections into a grid tensor")
    p.add_argument("area", help="Area identifier")
    p.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    p.add_argument("--res", type=int, default=20, help="Grid resolution")
    p.add_argument("-o", "--output", type=Path, help="Output .npy file")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    grid = encode_state(args.area, args.hours, args.res)
    if grid is None:
        return
    if args.output:
        np.save(args.output, grid)
        print(f"Saved grid to {args.output}")
    else:
        print(grid)


if __name__ == "__main__":
    main()
