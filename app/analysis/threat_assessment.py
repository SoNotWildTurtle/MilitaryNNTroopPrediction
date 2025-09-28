"""Assign threat levels to movement clusters."""

from typing import List, Dict, Tuple
from math import radians, sin, cos, sqrt, atan2, degrees

STRATEGIC_SITES = {
    "airport": (30.456, 50.402),
    "rail": (30.55, 50.45),
}

# Optional risk multipliers for strategic sites. Values >1.0 raise the
# resulting threat score when the cluster is nearest to that site.
SITE_WEIGHTS = {
    "airport": 2.0,
    "rail": 1.5,
}


def _haversine(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Return distance in kilometers between two lat/lon pairs."""
    lat1, lon1 = radians(p1[1]), radians(p1[0])
    lat2, lon2 = radians(p2[1]), radians(p2[0])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return 6371.0 * c


def _bearing(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Return bearing in degrees from p1 to p2."""
    lat1, lon1 = radians(p1[1]), radians(p1[0])
    lat2, lon2 = radians(p2[1]), radians(p2[0])
    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    brng = atan2(x, y)
    return (degrees(brng) + 360) % 360


def score_clusters(clusters: List[Dict]) -> List[Dict]:
    """Compute threat scores and levels for each cluster.

    Each cluster dictionary may contain ``center`` (lon, lat), ``count``, ``heading``
    (deg) and ``avg_speed`` (km/h). The output adds ``nearest_site``, distance in
    kilometers, whether the cluster is ``approaching`` the site, a ``threat_score``
    and a categorical ``threat_level``. ``eta_minutes`` is added when speed is
    known to estimate time until reaching the site.
    """

    results = []
    for c in clusters:
        center = tuple(c.get("center", (0.0, 0.0)))
        count = float(c.get("count", 1))

        # Find closest strategic site
        site_name, site_loc, min_dist = None, None, float("inf")
        for name, loc in STRATEGIC_SITES.items():
            dist = _haversine(center, loc)
            if dist < min_dist:
                site_name, site_loc, min_dist = name, loc, dist

        # Base threat score inversely proportional to distance
        threat = count / max(min_dist, 0.1)

        # Weight certain sites more heavily if configured
        threat *= SITE_WEIGHTS.get(site_name, 1.0)

        # Increase score if moving fast or toward the site
        if c.get("avg_speed"):
            threat *= 1 + float(c["avg_speed"]) / 50.0

        approaching = False
        if c.get("heading") is not None and site_loc:
            bearing = _bearing(center, site_loc)
            diff = abs(bearing - float(c["heading"]))
            if diff > 180:
                diff = 360 - diff
            approaching = diff < 45
            if approaching:
                threat *= 1.5

        eta_minutes = None
        if c.get("avg_speed"):
            speed = float(c["avg_speed"])
            if speed > 0:
                eta_minutes = (min_dist / speed) * 60.0

        level = "low"
        if threat > 10:
            level = "high"
        elif threat > 5:
            level = "medium"
        if eta_minutes is not None and eta_minutes < 60:
            level = "critical"

        results.append(
            {
                **c,
                "nearest_site": site_name,
                "distance_km": min_dist,
                "approaching": approaching,
                "eta_minutes": eta_minutes,
                "threat_score": threat,
                "threat_level": level,
            }
        )

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
