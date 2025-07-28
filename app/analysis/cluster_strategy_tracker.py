"""Analyze movement clusters and generate heatmaps."""

from typing import List, Dict

from .dbscan_cluster import cluster_recent_movements
from .heatmap import generate_heatmap


def analyze_unit(unit_id: str, hours: int = 24) -> List[Dict]:
    """Cluster recent movements for a unit and create a heatmap."""
    clusters = cluster_recent_movements(unit_id, hours)
    if clusters:
        generate_heatmap(unit_id, hours)
    return clusters


def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Cluster unit movements and create heatmap")
    p.add_argument("unit_id", help="Unit identifier")
    p.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    analyze_unit(args.unit_id, args.hours)


if __name__ == "__main__":
    main()
