"""Cluster troop movements using DBSCAN and store results."""

from typing import List, Tuple, Dict

from sklearn.cluster import DBSCAN
import numpy as np

from ..movement_history import recent_positions
from ..database import get_collection


def cluster_recent_movements(unit_id: str, hours: int = 24, eps: float = 0.01, min_samples: int = 3) -> List[Dict]:
    """Cluster a unit's recent positions and store results in MongoDB.

    Parameters
    ----------
    unit_id: str
        Identifier of the unit to cluster.
    hours: int
        How many hours back to query movements.
    eps: float
        DBSCAN epsilon parameter for distance clustering.
    min_samples: int
        Minimum samples for a cluster.

    Returns
    -------
    List[Dict]
        Cluster centers and label counts.
    """
    positions = recent_positions(unit_id, hours)
    if not positions:
        print(f"No recent positions found for {unit_id}")
        return []

    coords: List[Tuple[float, float]] = [
        (p["lat"], p["lon"]) for p in positions if "lat" in p and "lon" in p
    ]
    if not coords:
        print("No coordinates to cluster")
        return []

    arr = np.array(coords)
    clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(arr)
    labels = clustering.labels_
    results: List[Dict] = []
    for label in set(labels):
        if label == -1:
            continue  # noise
        mask = labels == label
        center = arr[mask].mean(axis=0)
        results.append({"label": int(label), "center": center.tolist(), "count": int(mask.sum())})

    coll = get_collection("movement_clusters")
    if results:
        docs = [{**r, "unit_id": unit_id} for r in results]
        coll.insert_many(docs)
        print(f"Stored {len(docs)} clusters for {unit_id}")
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("unit_id", help="Unit identifier to cluster")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    parser.add_argument("--eps", type=float, default=0.01, help="DBSCAN eps distance")
    parser.add_argument("--min_samples", type=int, default=3, help="DBSCAN min samples")
    args = parser.parse_args()

    cluster_recent_movements(args.unit_id, args.hours, args.eps, args.min_samples)
