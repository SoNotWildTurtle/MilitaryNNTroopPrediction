"""Generate theatre-level outlooks from detections and predictions.

This module provides heuristics that fuse spatial clustering, tempo trends and
prediction bearings into a higher-level synopsis that analysts can skim for
strategic awareness.  It is intentionally self-contained so that it can operate
on synthetic demo data or partially populated Mongo collections without
requiring heavy dependencies.  All heuristics are transparent and degrade
gracefully when information is missing.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Tuple

from ..movement_history import recent_detections, recent_predictions


@dataclass
class _ProcessedDetection:
    label: str
    confidence: Optional[float]
    timestamp: Optional[datetime]
    latitude: Optional[float]
    longitude: Optional[float]
    raw: MutableMapping[str, Any]


@dataclass
class _CorridorStats:
    label_counts: Counter = field(default_factory=Counter)
    confidences: List[float] = field(default_factory=list)
    total: int = 0
    recent: int = 0
    earlier: int = 0

    @property
    def avg_confidence(self) -> Optional[float]:
        if not self.confidences:
            return None
        return mean(self.confidences)

    def momentum(self) -> str:
        if self.recent > self.earlier * 1.2 and self.recent >= 2:
            return "rising"
        if self.earlier > self.recent * 1.2 and self.earlier >= 2:
            return "fading"
        if self.total >= 1:
            return "steady"
        return "inactive"


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalise_label(det: MutableMapping[str, Any]) -> str:
    label = det.get("class") or det.get("label") or det.get("type") or det.get("target")
    if label is None:
        return "unknown"
    return str(label).strip().lower()


def _extract_coords(det: MutableMapping[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    lat_keys = ("lat", "latitude", "y", "northing")
    lon_keys = ("lon", "lng", "longitude", "x", "easting")
    lat = None
    lon = None
    for key in lat_keys:
        if lat is None and key in det:
            lat = _safe_float(det.get(key))
    for key in lon_keys:
        if lon is None and key in det:
            lon = _safe_float(det.get(key))
    return lat, lon


def _processed_detections(
    detections: Iterable[MutableMapping[str, Any]]
) -> Tuple[List[_ProcessedDetection], Optional[datetime]]:
    processed: List[_ProcessedDetection] = []
    latest: Optional[datetime] = None
    for det in detections:
        timestamp = _parse_timestamp(
            det.get("timestamp")
            or det.get("time")
            or det.get("created_at")
            or det.get("detected_at")
        )
        if timestamp and (latest is None or timestamp > latest):
            latest = timestamp
        label = _normalise_label(det)
        confidence = _safe_float(det.get("confidence") or det.get("score"))
        lat, lon = _extract_coords(det)
        processed.append(
            _ProcessedDetection(
                label=label,
                confidence=confidence,
                timestamp=timestamp,
                latitude=lat,
                longitude=lon,
                raw=det,
            )
        )
    return processed, latest


def _centroid(points: Iterable[Tuple[Optional[float], Optional[float]]]) -> Tuple[float, float]:
    lats: List[float] = []
    lons: List[float] = []
    for lat, lon in points:
        if lat is not None and lon is not None:
            lats.append(lat)
            lons.append(lon)
    if not lats:
        return 0.0, 0.0
    return sum(lats) / len(lats), sum(lons) / len(lons)


def _corridor_for_point(lat: Optional[float], lon: Optional[float], ref_lat: float, ref_lon: float) -> str:
    if lat is None or lon is None:
        return "unknown"
    lat_diff = lat - ref_lat
    lon_diff = lon - ref_lon
    if abs(lat_diff) < 0.01 and abs(lon_diff) < 0.01:
        return "central"
    if abs(lat_diff) >= abs(lon_diff):
        return "north" if lat_diff >= 0 else "south"
    return "east" if lon_diff >= 0 else "west"


def _format_corridors(
    stats: Dict[str, _CorridorStats]
) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []
    for corridor, info in stats.items():
        top_classes = [label for label, _ in info.label_counts.most_common(3)]
        formatted.append(
            {
                "corridor": corridor,
                "detections": info.total,
                "avg_confidence": round(info.avg_confidence, 3) if info.avg_confidence else None,
                "momentum": info.momentum(),
                "top_classes": top_classes,
            }
        )
    formatted.sort(key=lambda entry: entry["detections"], reverse=True)
    return formatted


def _heading_from_prediction(pred: MutableMapping[str, Any]) -> Optional[float]:
    heading = pred.get("heading") or pred.get("bearing") or pred.get("azimuth")
    if isinstance(heading, str):
        cleaned = heading.strip().lower()
        cardinals = {
            "n": 0.0,
            "north": 0.0,
            "ne": 45.0,
            "north-east": 45.0,
            "north east": 45.0,
            "e": 90.0,
            "east": 90.0,
            "se": 135.0,
            "south-east": 135.0,
            "south east": 135.0,
            "s": 180.0,
            "south": 180.0,
            "sw": 225.0,
            "south-west": 225.0,
            "south west": 225.0,
            "w": 270.0,
            "west": 270.0,
            "nw": 315.0,
            "north-west": 315.0,
            "north west": 315.0,
        }
        if cleaned in cardinals:
            return cardinals[cleaned]
        try:
            return float(cleaned)
        except ValueError:
            return None
    return _safe_float(heading)


def _heading_from_vectors(pred: MutableMapping[str, Any]) -> Optional[float]:
    dest = pred.get("next_position") or pred.get("forecast_position")
    start = pred.get("current_position") or pred.get("origin")
    if isinstance(dest, dict) and isinstance(start, dict):
        lat2 = _safe_float(dest.get("lat") or dest.get("latitude"))
        lon2 = _safe_float(dest.get("lon") or dest.get("longitude"))
        lat1 = _safe_float(start.get("lat") or start.get("latitude"))
        lon1 = _safe_float(start.get("lon") or start.get("longitude"))
        if None not in (lat1, lon1, lat2, lon2):
            d_lat = lat2 - lat1
            d_lon = lon2 - lon1
            if d_lat == 0 and d_lon == 0:
                return None
            import math

            angle = math.degrees(math.atan2(d_lon, d_lat))
            return (angle + 360.0) % 360.0
    return None


def _axis_name(angle: float) -> str:
    sectors = [
        (22.5, "north"),
        (67.5, "north-east"),
        (112.5, "east"),
        (157.5, "south-east"),
        (202.5, "south"),
        (247.5, "south-west"),
        (292.5, "west"),
        (337.5, "north-west"),
        (360.0, "north"),
    ]
    for threshold, name in sectors:
        if angle < threshold:
            return name
    return "north"


def _summarise_axes(predictions: Iterable[MutableMapping[str, Any]]) -> List[Dict[str, Any]]:
    aggregates: Dict[str, Dict[str, Any]] = {}
    for pred in predictions:
        heading = _heading_from_prediction(pred)
        if heading is None:
            heading = _heading_from_vectors(pred)
        if heading is None:
            continue
        axis = _axis_name(heading)
        confidence = _safe_float(pred.get("confidence"))
        unit = pred.get("unit_id") or pred.get("unit") or pred.get("label")
        record = aggregates.setdefault(
            axis,
            {"count": 0, "confidences": [], "units": []},
        )
        record["count"] += 1
        if confidence is not None:
            record["confidences"].append(confidence)
        if unit:
            record["units"].append(str(unit))
    formatted: List[Dict[str, Any]] = []
    for axis, values in aggregates.items():
        avg_conf = mean(values["confidences"]) if values["confidences"] else None
        formatted.append(
            {
                "axis": axis,
                "count": values["count"],
                "avg_confidence": round(avg_conf, 3) if avg_conf else None,
                "units": sorted(set(values["units"])),
            }
        )
    formatted.sort(key=lambda item: item["count"], reverse=True)
    return formatted


def _risk_level(stats: _CorridorStats) -> str:
    if stats.total >= 8 and (stats.avg_confidence or 0) >= 0.6:
        return "critical"
    if stats.total >= 4:
        return "elevated"
    if stats.total >= 1:
        return "watch"
    return "inactive"


def _risk_hotspots(stats: Dict[str, _CorridorStats]) -> List[Dict[str, Any]]:
    hotspots: List[Dict[str, Any]] = []
    for corridor, info in stats.items():
        if info.total == 0:
            continue
        hotspots.append(
            {
                "corridor": corridor,
                "risk": _risk_level(info),
                "avg_confidence": round(info.avg_confidence, 3) if info.avg_confidence else None,
                "drivers": [label for label, _ in info.label_counts.most_common(3)],
            }
        )
    hotspots.sort(
        key=lambda item: ("critical", "elevated", "watch", "inactive").index(item["risk"]),
    )
    return hotspots


def _tempo_summary(stats: Dict[str, _CorridorStats]) -> Dict[str, Any]:
    recent = sum(info.recent for info in stats.values())
    earlier = sum(info.earlier for info in stats.values())
    total = sum(info.total for info in stats.values())
    if total == 0:
        return {"assessment": "no-activity", "recent": 0, "earlier": 0, "score": 0.0}
    ratio = recent / total
    if ratio >= 0.7:
        assessment = "surging"
    elif ratio >= 0.5:
        assessment = "rising"
    elif ratio <= 0.2:
        assessment = "cooling"
    else:
        assessment = "steady"
    return {
        "assessment": assessment,
        "recent": recent,
        "earlier": earlier,
        "score": round(ratio, 3),
    }


def _recommendations(
    hotspots: Sequence[Dict[str, Any]],
    axes: Sequence[Dict[str, Any]],
    tempo: Dict[str, Any],
) -> List[str]:
    if not hotspots and not axes:
        return [
            "Insufficient detections to produce theatre guidance — prioritise collection and sensor tasking.",
        ]
    recs: List[str] = []
    if hotspots:
        primary = hotspots[0]
        corr = primary["corridor"]
        if primary["risk"] == "critical":
            recs.append(
                f"Reinforce {corr} corridor defences; task artillery and counter-battery assets to disrupt momentum."
            )
        elif primary["risk"] == "elevated":
            recs.append(
                f"Increase ISR coverage over the {corr} corridor to validate build-up signals and cue fires."
            )
        else:
            recs.append(
                f"Maintain routine surveillance on the {corr} corridor while monitoring adjacent routes."
            )
    if axes:
        primary_axis = axes[0]
        axis_name = primary_axis["axis"]
        recs.append(
            f"Expect advances oriented {axis_name}; preposition blocking elements and prepare AT assets accordingly."
        )
    if tempo["assessment"] in {"surging", "rising"}:
        recs.append(
            "Tempo trending upward – review reserve mobilisation timelines and logistics sustainment plans."
        )
    elif tempo["assessment"] == "cooling":
        recs.append(
            "Tempo cooling; exploit the pause with counter-penetration raids and targeted EW/strike packages."
        )
    return recs


def assess_theater_outlook(
    area: str,
    *,
    lookback_hours: int = 36,
    detection_limit: int = 400,
    prediction_limit: int = 100,
    detections: Optional[Sequence[MutableMapping[str, Any]]] = None,
    predictions: Optional[Sequence[MutableMapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate a theatre-level outlook for a given area."""

    det_records = (
        list(detections)
        if detections is not None
        else list(recent_detections(area, detection_limit, lookback_hours=lookback_hours))
    )
    pred_records = (
        list(predictions)
        if predictions is not None
        else list(recent_predictions(area, prediction_limit, lookback_hours=lookback_hours))
    )

    processed, latest_ts = _processed_detections(det_records)
    centroid_lat, centroid_lon = _centroid((det.latitude, det.longitude) for det in processed)

    stats: Dict[str, _CorridorStats] = defaultdict(_CorridorStats)
    lookback_delta = timedelta(hours=max(1, lookback_hours // 3 or 1))
    recent_cutoff = (latest_ts - lookback_delta) if latest_ts else None

    for det in processed:
        corridor = _corridor_for_point(det.latitude, det.longitude, centroid_lat, centroid_lon)
        info = stats[corridor]
        info.total += 1
        info.label_counts[det.label] += 1
        if det.confidence is not None:
            info.confidences.append(det.confidence)
        if det.timestamp and recent_cutoff and det.timestamp >= recent_cutoff:
            info.recent += 1
        else:
            info.earlier += 1

    corridor_summary = _format_corridors(stats)
    axes_summary = _summarise_axes(pred_records)
    hotspots = _risk_hotspots(stats)
    tempo = _tempo_summary(stats)
    recommendations = _recommendations(hotspots, axes_summary, tempo)

    notes: List[str] = []
    if not processed:
        notes.append("No detections found in the selected window.")
    else:
        dominant = corridor_summary[0]["corridor"] if corridor_summary else "unknown"
        notes.append(
            f"Detection centroid near lat {centroid_lat:.3f}, lon {centroid_lon:.3f}; {dominant} corridor currently dominant."
        )
        if axes_summary:
            notes.append(
                f"Primary predicted axis: {axes_summary[0]['axis']} ({axes_summary[0]['count']} projections)."
            )
        notes.append(
            f"Overall tempo assessed as {tempo['assessment'].replace('-', ' ')} with {tempo['recent']} recent vs {tempo['earlier']} earlier detections."
        )

    return {
        "area": area,
        "timeframe": {
            "lookback_hours": lookback_hours,
            "detection_limit": detection_limit,
            "prediction_limit": prediction_limit,
            "latest_detection": latest_ts.isoformat() if latest_ts else None,
            "total_detections": sum(info.total for info in stats.values()),
        },
        "centroid": {
            "lat": centroid_lat,
            "lon": centroid_lon,
        },
        "corridors": corridor_summary,
        "axes_of_advance": axes_summary,
        "tempo": tempo,
        "risk_hotspots": hotspots,
        "recommendations": recommendations,
        "notes": notes,
    }


__all__ = ["assess_theater_outlook"]
