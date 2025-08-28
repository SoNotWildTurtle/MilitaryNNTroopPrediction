"""Analyze movement clusters and generate heatmaps."""

from typing import List, Dict, Optional
from datetime import datetime

from .dbscan_cluster import cluster_recent_movements
from .heatmap import generate_heatmap


def analyze_unit(
    unit_id: str,
    hours: int = 24,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[Dict]:
    """Cluster movements for a unit and create a heatmap."""
    clusters = cluster_recent_movements(
        unit_id, hours, start=start, end=end
    )
    if clusters:
        generate_heatmap(unit_id, hours, start=start, end=end)
    return clusters


def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Cluster unit movements and create heatmap")
    p.add_argument("unit_id", help="Unit identifier")
    p.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    p.add_argument("--start", type=str, help="Start date YYYY-MM-DD")
    p.add_argument("--end", type=str, help="End date YYYY-MM-DD")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    start = datetime.fromisoformat(args.start) if args.start else None
    end = datetime.fromisoformat(args.end) if args.end else None
    analyze_unit(args.unit_id, args.hours, start=start, end=end)


if __name__ == "__main__":
    main()
