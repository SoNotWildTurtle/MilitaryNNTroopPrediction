"""Time-based doctrine movement drilldown analytics."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ..database import get_collection
from .movement_stats import compute_stats_from_points

_LEVEL_FIELDS: Dict[str, Tuple[str, ...]] = {
    "unit": ("unit_id", "unit", "unit_name", "unit_code"),
    "group": (
        "group_id",
        "group",
        "unit_group",
        "company",
        "platoon",
    ),
    "battalion": (
        "battalion_id",
        "battalion",
        "unit_battalion",
        "regiment",
    ),
}

_BUCKET_CHOICES = {"hour", "day"}


def _ensure_datetime(value: object) -> datetime:
    """Return a datetime instance for Mongo timestamps or ISO strings."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.utcnow()


def _bucket_start(ts: datetime, bucket: str) -> datetime:
    """Normalise a timestamp to the requested bucket."""
    if bucket == "day":
        return datetime(ts.year, ts.month, ts.day)
    # default to hourly buckets
    return datetime(ts.year, ts.month, ts.day, ts.hour)


def _pick_level_value(doc: Dict, level: str) -> Optional[str]:
    """Extract the identifier for the requested hierarchy level."""
    fields = _LEVEL_FIELDS.get(level, ())
    for field in fields:
        value = doc.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    # fall back to unit id if nothing else resolves so drilldowns still work
    fallback = doc.get("unit_id")
    if isinstance(fallback, str) and fallback.strip():
        return fallback.strip()
    return None


def _matches_identifier(value: str, identifier: Optional[str]) -> bool:
    if not identifier:
        return True
    return value.lower() == identifier.lower()


def _doctrine_label(doc: Dict) -> str:
    doctrine = doc.get("doctrine") or doc.get("doctrine_label")
    if isinstance(doctrine, str) and doctrine.strip():
        return doctrine.strip()
    return "unknown"


def _time_filter(hours: int, start: Optional[datetime], end: Optional[datetime]) -> Dict:
    if start or end:
        clause: Dict[str, datetime] = {}
        if start:
            clause["$gte"] = start
        if end:
            clause["$lte"] = end
        return clause
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    return {"$gte": cutoff}


def doctrine_movement_drilldown(
    level: str = "unit",
    identifier: Optional[str] = None,
    *,
    bucket: str = "hour",
    hours: int = 24,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> Dict[str, object]:
    """Return time-bucketed movement statistics grouped by doctrine.

    Parameters
    ----------
    level:
        Hierarchy level to aggregate (``unit``, ``group``, or ``battalion``).
    identifier:
        Optional identifier to restrict results to a specific unit/group/battalion.
    bucket:
        Time bucket size (``"hour"`` or ``"day"``) used for trend rows.
    hours:
        Lookback window when explicit ``start``/``end`` are not provided.
    start, end:
        Optional datetime bounds for querying stored movement records.
    """

    level = level.lower()
    if level not in _LEVEL_FIELDS:
        raise ValueError(f"Unsupported level '{level}'. Expected one of {tuple(_LEVEL_FIELDS)}")
    if bucket not in _BUCKET_CHOICES:
        raise ValueError(f"Unsupported bucket '{bucket}'. Expected one of {_BUCKET_CHOICES}")

    coll = get_collection("movements")
    time_clause = _time_filter(hours, start, end)
    query: Dict[str, object] = {"timestamp": time_clause}
    cursor = coll.find(query)

    grouped: Dict[Tuple[str, str, datetime], List[Dict]] = defaultdict(list)
    for doc in cursor:
        level_value = _pick_level_value(doc, level)
        if not level_value:
            continue
        if not _matches_identifier(level_value, identifier):
            continue
        ts = _ensure_datetime(doc.get("timestamp"))
        bucket_start = _bucket_start(ts, bucket)
        doctrine = _doctrine_label(doc)
        # copy to avoid mutating the original document that may be reused
        record = dict(doc)
        record["timestamp"] = ts
        grouped[(level_value, doctrine, bucket_start)].append(record)

    rows: List[Dict[str, object]] = []
    doctrine_rollup: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"distance_km": 0.0, "duration_hours": 0.0, "samples": 0.0, "buckets": 0.0}
    )

    for (level_value, doctrine, bucket_start), points in sorted(grouped.items(), key=lambda x: x[0][2]):
        stats = compute_stats_from_points(points)
        if not stats:
            continue
        row = {
            "level_value": level_value,
            "doctrine": doctrine,
            "bucket_start": bucket_start.isoformat(),
            "avg_speed_kmh": stats.get("avg_speed_kmh", 0.0),
            "max_speed_kmh": stats.get("max_speed_kmh", 0.0),
            "distance_km": stats.get("distance_km", 0.0),
            "duration_hours": stats.get("duration_hours", 0.0),
            "samples": stats.get("samples", len(points)),
        }
        rows.append(row)
        rollup = doctrine_rollup[doctrine]
        rollup["distance_km"] += row["distance_km"]
        rollup["duration_hours"] += row["duration_hours"]
        rollup["samples"] += row["samples"]
        rollup["buckets"] += 1

    doctrine_summary: List[Dict[str, object]] = []
    for doctrine, stats in doctrine_rollup.items():
        duration = stats["duration_hours"] or 1e-6
        doctrine_summary.append(
            {
                "doctrine": doctrine,
                "avg_speed_kmh": stats["distance_km"] / duration,
                "distance_km": stats["distance_km"],
                "duration_hours": stats["duration_hours"],
                "samples": int(stats["samples"]),
                "buckets": int(stats["buckets"]),
            }
        )
    doctrine_summary.sort(key=lambda r: r["doctrine"])

    return {
        "level": level,
        "identifier": identifier,
        "bucket": bucket,
        "rows": rows,
        "doctrine_summary": doctrine_summary,
    }


__all__ = ["doctrine_movement_drilldown"]
