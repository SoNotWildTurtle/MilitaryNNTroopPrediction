"""Interactive map of detections using Folium."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import folium

from ..database import get_collection


def map_detections(
    area: str,
    hours: int = 24,
    output: Optional[Path] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Optional[Path]:
    """Generate an interactive HTML map of detections for the given area."""
    coll = get_collection("detections")
    if start or end:
        time_filter = {}
        if start:
            time_filter["$gte"] = start
        if end:
            time_filter["$lte"] = end
    else:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        time_filter = {"$gte": cutoff}
    cursor = coll.find({"area": area, "timestamp": time_filter})
    coords = [(d.get("lat"), d.get("lon")) for d in cursor if "lat" in d and "lon" in d]

    if not coords:
        print("No detections found for map")
        return None

    lat_center = sum(c[0] for c in coords) / len(coords)
    lon_center = sum(c[1] for c in coords) / len(coords)
    m = folium.Map(location=[lat_center, lon_center], zoom_start=10)

    for lat, lon in coords:
        folium.CircleMarker(location=[lat, lon], radius=4, color="red", fill=True).add_to(m)

    output = Path(output) if output else Path(f"{area}_detections_map.html")
    m.save(output)
    print(f"Saved map to {output}")
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create interactive map of detections")
    parser.add_argument("area", help="Area identifier")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("-o", "--output", type=Path, help="Output HTML file")
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start) if args.start else None
    end = datetime.fromisoformat(args.end) if args.end else None
    map_detections(args.area, args.hours, args.output, start=start, end=end)
