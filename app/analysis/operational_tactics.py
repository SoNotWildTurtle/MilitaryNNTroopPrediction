"""Generate high-level military analysis from detections and predictions.

The helper in this module blends recent detections, doctrine hints and
trajectory predictions into a concise set of operational insights.  The goal is
to give analysts a rapid read on opposing force posture, likely manoeuvre
themes and supporting logistics without requiring a fully populated database.
The heuristics intentionally favour transparency and graceful degradation so
that the same function can operate on synthetic demo data, recorded OSINT
feeds or live battlefield telemetry.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Tuple

from ..movement_history import recent_detections, recent_predictions


_CATEGORY_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "armor": ("armor", "armour", "tank", "ifv", "apc", "bmp", "mbt", "btr"),
    "infantry": (
        "infantry",
        "troop",
        "soldier",
        "squad",
        "platoon",
        "manpad",
        "dismount",
    ),
    "artillery": ("artillery", "howitzer", "mlrs", "rocket", "mortar", "tube"),
    "air": (
        "drone",
        "uav",
        "aircraft",
        "helicopter",
        "plane",
        "jet",
        "su-",
        "mig",
        "bpla",
    ),
    "logistics": (
        "logistic",
        "supply",
        "truck",
        "fuel",
        "ammo",
        "resupply",
        "convoy",
    ),
    "support": (
        "radar",
        "sam",
        "air-defense",
        "air defense",
        "ew",
        "command",
        "hq",
        "comms",
    ),
}


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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


def _normalise_label(det: MutableMapping[str, Any]) -> str:
    label = det.get("class") or det.get("label") or det.get("type") or det.get("target")
    return str(label).strip().lower() if label is not None else "unknown"


def _categorise(label: str) -> str:
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in label for keyword in keywords):
            return category
    if "drone" in label or "uav" in label:
        return "air"
    return "other"


def _split_air_assets(labels: Iterable[str]) -> Tuple[int, int]:
    drones = 0
    crewed = 0
    for label in labels:
        if any(term in label for term in ("drone", "uav", "bpla")):
            drones += 1
        elif any(term in label for term in ("aircraft", "helicopter", "jet", "plane")):
            crewed += 1
    return drones, crewed


def _posture_from_counts(category_counts: Counter) -> Tuple[str, str, Dict[str, float]]:
    maneuver = (
        category_counts.get("armor", 0)
        + category_counts.get("infantry", 0)
        + category_counts.get("artillery", 0)
    )
    support = category_counts.get("logistics", 0) + category_counts.get("support", 0)
    air = category_counts.get("air", 0)

    ratios = {
        "maneuver": float(maneuver),
        "support": float(support),
        "air": float(air),
        "support_to_maneuver": (support / maneuver) if maneuver else float("inf"),
    }

    if maneuver >= max(3, support + 2):
        detail = "Concentrated armour/infantry mass indicates offensive preparations."
        posture = "offensive"
    elif support > maneuver * 1.25:
        detail = "High logistics footprint suggests regrouping or resupply operations."
        posture = "regrouping"
    elif air > maneuver and maneuver <= 2:
        detail = "Air activity outweighs ground manoeuvre, likely reconnaissance-in-force."
        posture = "reconnaissance"
    elif support and maneuver:
        detail = "Balanced ground/support mix – expect limited probing or defensive holds."
        posture = "balanced"
    else:
        detail = "Insufficient detections to assess clear posture."
        posture = "uncertain"

    return posture, detail, ratios


def _tactic_indicators(
    category_counts: Counter, label_counts: Counter, doctrine_counts: Counter
) -> List[str]:
    indicators: List[str] = []
    if (
        category_counts.get("armor", 0) >= 1
        and category_counts.get("infantry", 0) >= 1
        and category_counts.get("air", 0) >= 1
    ):
        indicators.append(
            "Combined-arms grouping detected – armour, infantry and air assets operating together."
        )
    if category_counts.get("artillery", 0) >= max(2, category_counts.get("armor", 0)):
        indicators.append(
            "Artillery mass present – likely shaping fires or siege positioning ahead of manoeuvre."
        )
    if label_counts.get("drone", 0) + label_counts.get("uav", 0) >= 3:
        indicators.append(
            "Persistent drone coverage – expect rapid targeting and battle-damage assessment cycles."
        )
    if doctrine_counts:
        modern = sum(count for key, count in doctrine_counts.items() if "modern" in key.lower())
        legacy = sum(count for key, count in doctrine_counts.items() if "legacy" in key.lower())
        if modern > legacy:
            indicators.append(
                "Doctrine tags skew modern – anticipate faster manoeuvre tempo and integrated fires."
            )
        elif legacy > modern:
            indicators.append(
                "Doctrine mix leans legacy – expect rigid axis advance and predictable artillery cycles."
            )
    return indicators


def _logistics_assessment(category_counts: Counter) -> Tuple[str, List[str], float]:
    maneuver = (
        category_counts.get("armor", 0)
        + category_counts.get("infantry", 0)
        + category_counts.get("artillery", 0)
    )
    support = category_counts.get("logistics", 0) + category_counts.get("support", 0)
    ratio = (support / maneuver) if maneuver else float("inf")
    notes: List[str] = []
    if maneuver and ratio < 0.25:
        status = "strained"
        notes.append(
            "Ground forces outpace logistics – interdict resupply routes to degrade sustainment."
        )
    elif ratio < 0.45:
        status = "watch"
        notes.append("Logistics footprint modest; monitor for convoy build-up or bridging assets.")
    else:
        status = "sustained"
        notes.append("Support assets aligned with manoeuvre – expect continued pressure.")
    if category_counts.get("logistics", 0) == 0 and maneuver >= 3:
        notes.append("No dedicated supply units detected – likely relying on rear-area staging.")
    if category_counts.get("support", 0):
        notes.append("Support elements (EW/air defence) active – anticipate contested airspace.")
    return status, notes, ratio


def _air_activity_summary(labels: Iterable[str]) -> Dict[str, Any]:
    drones, crewed = _split_air_assets(labels)
    total = drones + crewed
    if total >= 5:
        assessment = "dominant"
        notes = [
            "High sortie rate – ensure air defence and EW are prioritised along approach lanes.",
        ]
    elif total >= 2:
        assessment = "active"
        notes = ["Regular air presence – expect quick reconnaissance-to-strike loops."]
    elif total == 1:
        assessment = "limited"
        notes = ["Single air asset detected – likely spot recon or artillery adjustment."]
    else:
        assessment = "minimal"
        notes = ["No air assets observed in window – maintain radar watch for pop-up sorties."]
    if drones >= 3:
        notes.append("Drone saturation indicates emphasis on ISR and precision fires.")
    return {
        "total": total,
        "drones": drones,
        "crewed": crewed,
        "assessment": assessment,
        "notes": notes,
    }


def _timeline_summary(timestamps: List[datetime], lookback_hours: int) -> Dict[str, Any]:
    if not timestamps:
        return {"trend": "unknown", "recent": 0, "earlier": 0, "lookback_hours": lookback_hours}
    now = max(timestamps + [datetime.now(timezone.utc)])
    recent_window = max(3, min(lookback_hours, 12))
    threshold = now - timedelta(hours=recent_window)
    recent = sum(1 for ts in timestamps if ts >= threshold)
    earlier = len(timestamps) - recent
    if recent >= max(1, int(earlier * 1.3)):
        trend = "surging"
    elif earlier >= max(1, int(recent * 1.3)):
        trend = "slowing"
    else:
        trend = "steady"
    return {
        "trend": trend,
        "recent": recent,
        "earlier": earlier,
        "recent_window_hours": recent_window,
        "lookback_hours": lookback_hours,
    }


def _prediction_summary(predictions: Sequence[MutableMapping[str, Any]]) -> Tuple[Dict[str, Any], List[str]]:
    if not predictions:
        return {"count": 0, "avg_confidence": None}, []
    confidences: List[float] = []
    surety_scores: List[float] = []
    noted_units: List[str] = []
    for pred in predictions:
        conf = _safe_float(pred.get("confidence"))
        if conf is not None:
            confidences.append(conf)
        surety = pred.get("surety") or {}
        if isinstance(surety, dict):
            overall = _safe_float(surety.get("overall"))
            if overall is not None:
                surety_scores.append(overall)
        unit = pred.get("unit_id") or pred.get("unit") or pred.get("label")
        if unit:
            noted_units.append(str(unit))
    summary = {
        "count": len(predictions),
        "avg_confidence": round(mean(confidences), 3) if confidences else None,
        "avg_surety": round(mean(surety_scores), 3) if surety_scores else None,
    }
    insights: List[str] = []
    if confidences:
        insights.append(
            f"{len(confidences)} trajectory forecasts average {summary['avg_confidence']:.2f} confidence."
        )
    if surety_scores:
        insights.append(
            f"Prediction surety averages {summary['avg_surety']:.2f} – integrate into movement tracking."
        )
    if noted_units:
        unique = sorted(set(noted_units))
        insights.append("Forecast coverage includes: " + ", ".join(unique[:6]))
    return summary, insights


def _top_classes(
    class_counts: Counter, confidence_map: Dict[str, List[float]], limit: int = 5
) -> List[Dict[str, Any]]:
    top: List[Dict[str, Any]] = []
    for label, count in class_counts.most_common(limit):
        confidences = confidence_map.get(label, [])
        avg_conf = round(mean(confidences), 3) if confidences else None
        top.append({"label": label, "count": count, "avg_confidence": avg_conf})
    return top


def assess_operational_tactics(
    area: str,
    *,
    detections: Optional[Sequence[MutableMapping[str, Any]]] = None,
    predictions: Optional[Sequence[MutableMapping[str, Any]]] = None,
    lookback_hours: int = 24,
    detection_limit: int = 200,
    prediction_limit: int = 100,
) -> Dict[str, Any]:
    """Compile large-scale operational insights for an area."""

    raw_detections = list(detections) if detections is not None else list(
        recent_detections(area, limit=detection_limit)
    )
    raw_predictions = list(predictions) if predictions is not None else list(
        recent_predictions(area, limit=prediction_limit)
    )

    class_counts: Counter = Counter()
    category_counts: Counter = Counter()
    doctrine_counts: Counter = Counter()
    confidence_map: Dict[str, List[float]] = defaultdict(list)
    timestamps: List[datetime] = []
    labels_for_air: List[str] = []

    for det in raw_detections:
        label = _normalise_label(det)
        class_counts[label] += 1
        confidence = _safe_float(det.get("confidence") or det.get("score"))
        if confidence is not None:
            confidence_map[label].append(confidence)
        category = _categorise(label)
        category_counts[category] += 1
        ts = _parse_timestamp(
            det.get("timestamp")
            or det.get("detected_at")
            or det.get("time")
            or det.get("created_at")
        )
        if ts:
            timestamps.append(ts)
        doctrine = det.get("doctrine") or det.get("doctrine_label")
        if doctrine:
            doctrine_counts[str(doctrine).lower()] += 1
        if category == "air":
            labels_for_air.append(label)

    posture, detail, ratios = _posture_from_counts(category_counts)
    tactic_indicators = _tactic_indicators(category_counts, class_counts, doctrine_counts)
    logistics_status, logistics_notes, logistics_ratio = _logistics_assessment(category_counts)
    air_picture = _air_activity_summary(labels_for_air)
    timeline = _timeline_summary(timestamps, lookback_hours)
    prediction_summary, prediction_insights = _prediction_summary(raw_predictions)

    recommendations: List[str] = []
    if posture == "offensive":
        recommendations.append(
            "Deploy blocking positions along the primary axis and reinforce counter-battery assets."
        )
    elif posture == "regrouping":
        recommendations.append(
            "Exploit regrouping window with long-range fires and interdiction strikes."
        )
    elif posture == "reconnaissance":
        recommendations.append(
            "Increase EMCON discipline and disperse high-value units to frustrate targeting."
        )
    if logistics_status != "sustained":
        recommendations.append(
            "Task ISR to locate logistics nodes and queue precision fires against convoys."
        )
    if air_picture["assessment"] in {"dominant", "active"}:
        recommendations.append("Ensure SHORAD batteries are forward and deconflicted with manoeuvre units.")
    if not raw_predictions:
        recommendations.append("Collect additional movement tracks to refine trajectory estimates.")

    recommendations = list(dict.fromkeys(recommendations))

    insights = prediction_insights

    return {
        "area": area,
        "force_composition": {
            "total_detections": sum(class_counts.values()),
            "category_counts": dict(category_counts),
            "top_classes": _top_classes(class_counts, confidence_map),
            "doctrine_counts": dict(doctrine_counts),
        },
        "posture": {
            "posture": posture,
            "detail": detail,
            "metrics": ratios,
        },
        "logistics": {
            "status": logistics_status,
            "notes": logistics_notes,
            "support_to_maneuver": logistics_ratio,
        },
        "air_activity": air_picture,
        "tactic_indicators": tactic_indicators,
        "movement": {
            "timeline": timeline,
            "prediction_summary": prediction_summary,
            "insights": insights,
        },
        "timeline": timeline,
        "recommendations": recommendations,
    }


__all__ = ["assess_operational_tactics"]
