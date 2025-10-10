"""Assess large-scale military campaign posture from detections and predictions."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

GROUND_FORCE_LABELS = {"troop", "infantry", "armor", "tank", "artillery"}
LOGISTICS_LABELS = {"logistics", "supply", "truck", "fuel"}
AIR_LABELS = {"drone", "uav", "aircraft", "helicopter"}
LONG_RANGE_LABELS = {"artillery", "mlrs", "missile"}


@dataclass
class CampaignAssessment:
    """Structured results for large-scale campaign assessments."""

    front_pressure: str
    tempo: str
    logistics: str
    air_activity: str
    attrition_risk: str
    recommended_actions: List[str]
    metrics: Dict[str, Any]


def _timestamp(record: Dict[str, Any]) -> datetime:
    value = record.get("timestamp")
    if isinstance(value, datetime):
        return value
    try:
        if value:
            return datetime.fromisoformat(str(value))
    except ValueError:
        pass
    return datetime.utcnow()


def _score_band(score: float, *, low: float, high: float) -> str:
    if score >= high:
        return "high"
    if score <= low:
        return "low"
    return "medium"


def _summarise_front_pressure(counts: Counter) -> Dict[str, Any]:
    armor = counts["armor"] + counts["tank"]
    artillery = counts["artillery"] + counts["mlrs"] + counts["missile"]
    infantry = counts["troop"] + counts["infantry"]
    drones = counts["drone"] + counts["uav"]
    pressure_score = armor * 3 + artillery * 2 + infantry + drones * 0.5
    band = _score_band(pressure_score, low=5, high=15)
    posture = {
        "high": "Major offensive pressure detected",
        "medium": "Sustained probing attacks detected",
        "low": "Limited frontline pressure detected",
    }[band]
    return {
        "text": posture,
        "score": pressure_score,
        "band": band,
    }


def _summarise_tempo(predictions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    speeds: List[float] = []
    confidence: List[float] = []
    for pred in predictions:
        speed = pred.get("speed_kmh") or pred.get("avg_speed_kmh")
        if isinstance(speed, (int, float)):
            speeds.append(float(speed))
        surety = pred.get("confidence") or pred.get("confidence_score")
        if isinstance(surety, (int, float)):
            confidence.append(float(surety))
    if not speeds:
        return {
            "text": "Insufficient prediction data to score tempo",
            "score": 0.0,
            "band": "low",
        }
    avg_speed = sum(speeds) / len(speeds)
    avg_conf = sum(confidence) / len(confidence) if confidence else 0.0
    band = _score_band(avg_speed, low=8, high=18)
    text = {
        "high": "Rapid manoeuvre operations underway",
        "medium": "Measured movement tempo observed",
        "low": "Forces manoeuvring cautiously",
    }[band]
    if avg_conf < 0.45:
        text += " (low prediction confidence)"
    return {
        "text": text,
        "score": avg_speed,
        "band": band,
        "avg_confidence": avg_conf,
    }


def _summarise_logistics(counts: Counter) -> Dict[str, Any]:
    frontline = sum(counts[label] for label in GROUND_FORCE_LABELS)
    logistics = sum(counts[label] for label in LOGISTICS_LABELS)
    ratio = logistics / frontline if frontline else 0.0
    band = _score_band(ratio, low=0.1, high=0.35)
    text = {
        "high": "Logistics trains appear healthy",
        "medium": "Logistics present but worth monitoring",
        "low": "Logistics strain likely — resupply limited",
    }[band]
    return {
        "text": text,
        "score": ratio,
        "band": band,
        "frontline": frontline,
        "logistics": logistics,
    }


def _summarise_air_activity(counts: Counter) -> Dict[str, Any]:
    air_ops = sum(counts[label] for label in AIR_LABELS)
    band = _score_band(air_ops, low=2, high=8)
    text = {
        "high": "Sustained drone/air operations detected",
        "medium": "Intermittent air activity observed",
        "low": "Minimal drone or air presence",
    }[band]
    return {"text": text, "score": air_ops, "band": band}


def _summarise_attrition(counts: Counter, detections: List[Dict[str, Any]]) -> Dict[str, Any]:
    long_range = sum(counts[label] for label in LONG_RANGE_LABELS)
    recent = sorted((_timestamp(d), d) for d in detections)[-10:]
    if len(recent) < 2:
        trend = "stable"
    else:
        first_time = recent[0][0]
        last_time = recent[-1][0]
        delta_hours = max((last_time - first_time).total_seconds() / 3600.0, 1e-3)
        rate = len(recent) / delta_hours
        trend = "rising" if rate > 2 else "stable"
    if long_range >= 5 and trend == "rising":
        text = "High attrition risk: heavy fires with rising tempo"
        band = "high"
    elif long_range >= 3:
        text = "Moderate attrition risk from sustained fires"
        band = "medium"
    else:
        text = "Limited attrition risk detected"
        band = "low"
    return {"text": text, "band": band, "long_range_assets": long_range, "trend": trend}


def _compile_recommendations(summary: Dict[str, Dict[str, Any]]) -> List[str]:
    actions: List[str] = []
    if summary["front_pressure"]["band"] == "high":
        actions.append(
            "Prioritise counter-battery coverage and reinforce defensive lines"
        )
    elif summary["front_pressure"]["band"] == "medium":
        actions.append("Maintain reserves ready for localized counter-attacks")
    if summary["logistics"]["band"] == "low":
        actions.append("Interdict enemy supply routes and monitor fuel convoys")
    if summary["air_activity"]["band"] != "low":
        actions.append("Sustain air-defence readiness and electronic warfare coverage")
    if summary["attrition"]["band"] == "high":
        actions.append("Disperse key assets and rotate frontline units to reduce losses")
    if summary["tempo"].get("avg_confidence", 0) < 0.4:
        actions.append("Collect additional ISR to firm up movement tempo estimates")
    if not actions:
        actions.append("Continue routine monitoring; no urgent adjustments flagged")
    return actions


def assess_military_campaign(
    detections: Iterable[Dict[str, Any]],
    predictions: Optional[Iterable[Dict[str, Any]]] = None,
) -> CampaignAssessment:
    """Return a heuristic campaign assessment for operator briefings."""

    detections_list = list(detections)
    counts: Counter = Counter()
    doctrine_rollup: Dict[str, int] = defaultdict(int)
    for det in detections_list:
        label = str(det.get("class_label") or det.get("label") or "unknown").lower()
        counts[label] += 1
        doctrine = str(det.get("doctrine") or det.get("doctrine_label") or "").strip()
        if doctrine:
            doctrine_rollup[doctrine] += 1
    prediction_list = list(predictions or [])

    front = _summarise_front_pressure(counts)
    tempo = _summarise_tempo(prediction_list)
    logistics = _summarise_logistics(counts)
    air = _summarise_air_activity(counts)
    attrition = _summarise_attrition(counts, detections_list)

    summary = {
        "front_pressure": front,
        "tempo": tempo,
        "logistics": logistics,
        "air_activity": air,
        "attrition": attrition,
    }
    recommendations = _compile_recommendations(summary)

    metrics: Dict[str, Any] = {
        "counts": dict(counts),
        "doctrine": dict(doctrine_rollup),
        "front_pressure_score": front["score"],
        "tempo_speed_kmh": tempo["score"],
        "logistics_ratio": logistics["score"],
        "air_activity_count": air["score"],
        "attrition_band": attrition["band"],
    }

    return CampaignAssessment(
        front_pressure=front["text"],
        tempo=tempo["text"],
        logistics=logistics["text"],
        air_activity=air["text"],
        attrition_risk=attrition["text"],
        recommended_actions=recommendations,
        metrics=metrics,
    )


__all__ = ["CampaignAssessment", "assess_military_campaign"]
