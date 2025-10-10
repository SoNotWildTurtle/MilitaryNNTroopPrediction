"""Drilldown utilities that summarise movement metrics by object type."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..database import get_collection
from .movement_stats import compute_stats_from_points

_TYPE_KEYS = (
    "object_type",
    "unit_type",
    "category",
    "class",
    "label",
    "platform",
)

_OBJECT_ALIASES: Dict[str, List[str]] = {
    "armor": ["armor", "armour", "armored", "armoured", "vehicle", "tank"],
    "aircraft": ["aircraft", "plane", "jet", "helo", "helicopter", "air"],
    "drone": ["drone", "uav", "uas", "quadcopter", "octocopter"],
}


def _normalise(value: str) -> str:
    return value.strip().lower()


def _matches_alias(text: str, target: str) -> bool:
    lookup = _OBJECT_ALIASES.get(target.lower(), [target.lower()])
    text_norm = _normalise(text)
    return any(alias in text_norm for alias in lookup)


def _infer_type(doc: Dict, unit_id: str) -> Optional[str]:
    """Try to infer an object's type from a movement record."""
    for key in _TYPE_KEYS:
        value = doc.get(key)
        if isinstance(value, str) and value.strip():
            return value
    if unit_id:
        return unit_id
    return None


def object_speed_summary(
    object_type: str,
    hours: int = 24,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Dict[str, object]:
    """Return per-unit speed statistics for units of the requested type."""

    coll = get_collection("movements")
    if start or end:
        time_filter: Dict[str, datetime] = {}
        if start:
            time_filter["$gte"] = start
        if end:
            time_filter["$lte"] = end
    else:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        time_filter = {"$gte": cutoff}

    cursor = coll.find({"timestamp": time_filter})
    grouped: Dict[str, List[Dict]] = defaultdict(list)
    requested = object_type.lower()
    for doc in cursor:
        unit_id = str(doc.get("unit_id", "")).strip()
        if not unit_id:
            continue
        inferred = _infer_type(doc, unit_id) or ""
        if requested and inferred:
            if not _matches_alias(str(inferred), requested):
                continue
        grouped[unit_id].append(doc)

    rows = []
    total_distance = 0.0
    total_duration = 0.0
    for unit_id, points in grouped.items():
        stats = compute_stats_from_points(points)
        if not stats:
            continue
        total_distance += stats.get("distance_km", 0.0)
        total_duration += stats.get("duration_hours", 0.0)
        rows.append({
            "unit_id": unit_id,
            "avg_speed_kmh": stats.get("avg_speed_kmh", 0.0),
            "max_speed_kmh": stats.get("max_speed_kmh", 0.0),
            "distance_km": stats.get("distance_km", 0.0),
            "duration_hours": stats.get("duration_hours", 0.0),
            "samples": stats.get("samples", len(points)),
        })

    rows.sort(key=lambda r: r["avg_speed_kmh"], reverse=True)
    overall_avg = 0.0
    if total_duration > 0:
        overall_avg = total_distance / total_duration

    return {
        "object_type": object_type,
        "total_units": len(rows),
        "overall_avg_speed_kmh": overall_avg,
        "rows": rows,
    }

