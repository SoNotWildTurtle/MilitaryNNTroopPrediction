"""Export detection records to GeoJSON."""
from __future__ import annotations

from typing import Iterable, Dict, Any
import json


def detections_to_geojson(detections: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert a sequence of detection dicts to a GeoJSON FeatureCollection.

    Each detection should contain ``lat`` and ``lon`` fields. All other
    key/value pairs are included under ``properties`` in the output features.
    Records missing coordinates are skipped.
    """
    features = []
    for det in detections:
        lat = det.get("lat")
        lon = det.get("lon")
        if lat is None or lon is None:
            continue
        props = {k: v for k, v in det.items() if k not in {"lat", "lon", "_id"}}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_geojson(detections: Iterable[Dict[str, Any]], path: str) -> None:
    """Write detections to ``path`` in GeoJSON format."""
    geojson = detections_to_geojson(detections)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)
