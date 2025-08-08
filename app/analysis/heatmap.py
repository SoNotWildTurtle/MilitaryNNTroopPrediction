"""Generate heatmaps from detection logs."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from ..database import get_collection


def generate_heatmap(area: str, hours: int = 24, bins: int = 100, output: Optional[Path] = None) -> Optional[Path]:
    """Create a heatmap of detections for an area within the given timeframe.

    Parameters
    ----------
    area: str
        Area identifier used when storing detections.
    hours: int
        How many hours back to query detections.
    bins: int
        Resolution of the heatmap.
    output: Path, optional
        Path to save the heatmap PNG. Defaults to ``{area}_heatmap.png``.
    """
    coll = get_collection("detections")
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    cursor = coll.find({"area": area, "timestamp": {"$gte": cutoff}})
    coords = [(doc.get("lat"), doc.get("lon")) for doc in cursor if "lat" in doc and "lon" in doc]

    if not coords:
        print("No detections found for heatmap")
        return None

    arr = np.array(coords)
    plt.figure(figsize=(6, 5))
    plt.hist2d(arr[:, 1], arr[:, 0], bins=bins, cmap="hot")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.colorbar(label="Detection density")

    output = output or Path(f"{area}_heatmap.png")
    plt.savefig(output)
    plt.close()
    print(f"Saved heatmap to {output}")
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate detection heatmap")
    parser.add_argument("area", help="Area identifier")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    parser.add_argument("--bins", type=int, default=100, help="Heatmap resolution")
    parser.add_argument("-o", "--output", type=Path, help="Output PNG file")
    args = parser.parse_args()

    generate_heatmap(args.area, args.hours, args.bins, args.output)
