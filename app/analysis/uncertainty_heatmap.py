"""Generate blurred uncertainty heatmaps from low-confidence detections."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import cv2
import matplotlib.pyplot as plt
import numpy as np

from ..database import get_collection


def generate_uncertainty_heatmap(
    area: str,
    hours: int = 24,
    threshold: float = 0.8,
    bins: int = 100,
    blur: int = 11,
    output: Optional[Path] = None,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Optional[Path]:
    """Create a blurred heatmap emphasising uncertain detections.

    Parameters
    ----------
    area: str
        Area identifier to query.
    hours: int, default 24
        Lookback window when ``start``/``end`` are not given.
    threshold: float, default 0.8
        Detections with confidence below this value are considered uncertain.
    bins: int, default 100
        Resolution of the heatmap.
    blur: int, default 11
        Gaussian blur kernel size (odd). Set to 0 for no blur.
    output: Path, optional
        File to save the heatmap PNG. Defaults to ``{area}_uncertainty.png``.
    start, end: datetime, optional
        Explicit time window to query.
    """
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
    coords = []
    weights = []
    for doc in cursor:
        lat = doc.get("lat")
        lon = doc.get("lon")
        conf = doc.get("confidence")
        if lat is None or lon is None or conf is None:
            continue
        if conf < threshold:
            coords.append((lat, lon))
            weights.append(1.0 - conf)

    if not coords:
        print("No uncertain detections found")
        return None

    arr = np.array(coords)
    weight_arr = np.array(weights)
    heat, xedges, yedges = np.histogram2d(
        arr[:, 1], arr[:, 0], bins=bins, weights=weight_arr
    )

    if blur and blur % 2 == 1:
        heat = cv2.GaussianBlur(heat, (blur, blur), 0)

    plt.figure(figsize=(6, 5))
    plt.imshow(
        heat,
        cmap="hot",
        origin="lower",
        extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]],
        aspect="auto",
    )
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")
    plt.colorbar(label="Uncertainty")

    output = output or Path(f"{area}_uncertainty.png")
    plt.savefig(output)
    plt.close()
    print(f"Saved uncertainty heatmap to {output}")
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate uncertainty heatmap")
    parser.add_argument("area", help="Area identifier")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    parser.add_argument("--threshold", type=float, default=0.8, help="Confidence threshold")
    parser.add_argument("--bins", type=int, default=100, help="Heatmap resolution")
    parser.add_argument("--blur", type=int, default=11, help="Gaussian blur kernel size (odd)")
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("-o", "--output", type=Path, help="Output PNG file")
    args = parser.parse_args()

    start = datetime.fromisoformat(args.start) if args.start else None
    end = datetime.fromisoformat(args.end) if args.end else None
    generate_uncertainty_heatmap(
        args.area,
        hours=args.hours,
        threshold=args.threshold,
        bins=args.bins,
        blur=args.blur,
        output=args.output,
        start=start,
        end=end,
    )
