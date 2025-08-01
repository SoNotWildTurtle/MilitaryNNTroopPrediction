"""Assign threat levels to movement clusters."""

from typing import List, Dict, Tuple
from math import sqrt

STRATEGIC_SITES = {
    "airport": (30.456, 50.402),
    "rail": (30.55, 50.45),
}


def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def score_clusters(clusters: List[Dict]) -> List[Dict]:
    """Compute a simple threat score for each cluster."""
    results = []
    for c in clusters:
        center = tuple(c.get("center", (0, 0)))
        count = c.get("count", 1)
        min_dist = min(_distance(center, loc) for loc in STRATEGIC_SITES.values())
        threat = count / max(min_dist, 0.001)
        results.append({**c, "threat_score": threat})
    return results


def _parse_args():
    import argparse
    import json
    p = argparse.ArgumentParser(description="Compute threat scores from cluster JSON")
    p.add_argument("clusters", type=str, help="JSON array of clusters")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    clusters = []
    try:
        clusters = json.loads(args.clusters)
    except Exception as e:
        print(f"Failed to parse clusters: {e}")
        return
    scores = score_clusters(clusters)
    for s in scores:
        print(s)


if __name__ == "__main__":
    main()
