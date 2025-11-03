"""Compose a consolidated intelligence brief from stored telemetry."""
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Tuple

from pymongo.errors import PyMongoError

from ..database import get_collection
from ..movement_history import recent_detections, recent_predictions
from .meta_analysis import meta_analysis
from .threat_assessment import score_clusters


def _utcnow() -> datetime:
    """Return the current UTC time."""
    return datetime.now(UTC)


def _normalize_document(doc: MutableMapping[str, Any]) -> Dict[str, Any]:
    """Return a JSON-serialisable copy of a MongoDB document."""
    payload: Dict[str, Any] = {k: v for k, v in doc.items() if k != "_id"}
    if doc.get("_id") is not None:
        payload["id"] = str(doc["_id"])
    return payload


def _has_timestamp(collection_name: str) -> bool:
    """Return ``True`` if a collection stores timestamp fields."""
    try:
        coll = get_collection(collection_name)
        return coll.count_documents({"timestamp": {"$exists": True}}, limit=1) > 0
    except Exception:
        return False


def _recent_documents(
    collection_name: str,
    *,
    hours: int,
    limit: int,
    area: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch a capped list of recent documents from a collection."""
    coll = get_collection(collection_name)
    query: Dict[str, Any] = {}
    if area:
        query["area"] = area

    cursor = None
    if _has_timestamp(collection_name):
        cutoff = _utcnow() - timedelta(hours=hours)
        query["timestamp"] = {"$gte": cutoff}
        cursor = coll.find(query).sort("timestamp", -1).limit(limit)
    else:
        cursor = coll.find(query).sort("_id", -1).limit(limit)

    return [_normalize_document(doc) for doc in cursor]


def _recent_clusters(hours: int, area: Optional[str]) -> List[Dict[str, Any]]:
    """Load recent movement clusters for threat scoring."""
    coll = get_collection("movement_clusters")
    query: Dict[str, Any] = {}
    if area:
        query["area"] = area

    has_ts = _has_timestamp("movement_clusters")
    if has_ts:
        query["timestamp"] = {"$gte": _utcnow() - timedelta(hours=hours)}
        cursor = coll.find(query).sort("timestamp", -1)
    else:
        cursor = coll.find(query)

    clusters = [_normalize_document(doc) for doc in cursor]
    return clusters


def _coerce_utc_datetime(value: Any) -> Optional[datetime]:
    """Convert supported timestamp formats to a timezone-aware UTC datetime."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    return None


def _latest_timestamp(records: Iterable[MutableMapping[str, Any]]) -> Optional[datetime]:
    """Return the most recent timestamp found in an iterable of records."""

    latest: Optional[datetime] = None
    for record in records:
        timestamp = _coerce_utc_datetime(
            record.get("timestamp")
            or record.get("created_at")
            or record.get("updated_at")
        )
        if timestamp is None:
            continue
        if latest is None or timestamp > latest:
            latest = timestamp
    return latest


def _freshness_status(
    *,
    minutes_old: Optional[float],
    warn_threshold: float,
    stale_threshold: float,
) -> str:
    """Categorise data recency using configured thresholds."""

    if minutes_old is None:
        return "unknown"
    if minutes_old <= warn_threshold:
        return "fresh"
    if minutes_old <= stale_threshold:
        return "warning"
    return "stale"


def _append_recommendation(target: Dict[str, Any], message: str) -> None:
    """Append a recommendation to the brief if it is not already listed."""

    if not message:
        return
    existing = target.setdefault("recommendations", [])
    if message not in existing:
        existing.append(message)


def _analyse_detection_quality(meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evaluate detection summary metadata for confidence and coverage gaps."""

    detections = meta.get("detections") if isinstance(meta, dict) else None
    if not isinstance(detections, dict) or not detections:
        return None

    total_count = 0
    weighted_conf_total = 0.0
    active_classes = 0
    low_confidence: List[str] = []
    sparse_classes: List[str] = []

    for cls, stats in detections.items():
        if not isinstance(stats, dict):
            continue
        count = stats.get("count")
        avg_conf = stats.get("avg_conf")

        numeric_count = int(count) if isinstance(count, (int, float)) else 0
        numeric_conf = float(avg_conf) if isinstance(avg_conf, (int, float)) else None

        if numeric_count > 0:
            total_count += numeric_count
            active_classes += 1
            if numeric_conf is not None:
                weighted_conf_total += numeric_conf * numeric_count
            if numeric_count < 3:
                sparse_classes.append(cls)
        else:
            sparse_classes.append(cls)

        if numeric_conf is not None and numeric_conf < 0.55:
            low_confidence.append(cls)
        elif numeric_conf is None:
            # Unknown confidence is a coverage gap when paired with detections.
            if numeric_count > 0:
                sparse_classes.append(cls)

    if total_count == 0 and not low_confidence and not sparse_classes:
        return None

    weighted_avg_conf: Optional[float] = None
    if total_count:
        weighted_avg_conf = round(weighted_conf_total / total_count, 3)

    diversity_ratio: Optional[float] = None
    if detections:
        diversity_ratio = round(active_classes / max(len(detections), 1), 3)

    notes: List[str] = []
    if weighted_avg_conf is not None:
        if weighted_avg_conf < 0.6:
            notes.append(
                "Average detection confidence is degrading below 0.60 across active classes."
            )
        elif weighted_avg_conf < 0.7:
            notes.append("Average detection confidence is trending below 0.70.")

    quality: Dict[str, Any] = {
        "total_detections": total_count,
        "active_classes": active_classes,
    }
    if weighted_avg_conf is not None:
        quality["weighted_avg_confidence"] = weighted_avg_conf
    if diversity_ratio is not None:
        quality["active_class_ratio"] = diversity_ratio
    if low_confidence:
        quality["low_confidence_classes"] = sorted(set(low_confidence))
    if sparse_classes:
        quality["sparse_class_coverage"] = sorted(set(sparse_classes))
    if notes:
        quality["notes"] = notes

    return quality


def _derive_response_pressure(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Synthesise analyst workload pressure from activity and quality signals."""

    activity_summary = brief.get("activity_summary") or {}
    readiness = brief.get("response_readiness") or {}
    detection_quality = brief.get("detection_quality") or {}
    meta = brief.get("meta") or {}

    detections = activity_summary.get("detections")
    predictions = activity_summary.get("predictions")
    detection_rate = activity_summary.get("detection_rate_per_hour")

    det_count = int(detections) if isinstance(detections, (int, float)) else 0
    pred_count = int(predictions) if isinstance(predictions, (int, float)) else 0
    rate_per_hour = float(detection_rate) if isinstance(detection_rate, (int, float)) else None

    if det_count == 0 and pred_count == 0:
        return None

    backlog = max(pred_count - det_count, 0)
    unmatched = max(det_count - pred_count, 0)
    ratio = None
    if det_count > 0 or pred_count > 0:
        ratio = round(pred_count / max(det_count, 1), 2)

    backlog_major = max(4, math.ceil(pred_count * 0.5))
    backlog_minor = max(2, math.ceil(pred_count * 0.25))
    shortfall_major = max(4, math.ceil(det_count * 0.4))
    shortfall_minor = max(2, math.ceil(det_count * 0.2))

    drivers: List[str] = []
    actions: List[str] = []
    severity = 0
    status = "balanced"

    if pred_count and det_count == 0:
        severity = 2
        status = "critical_backlog"
        drivers.append("Predictions are unaddressed with no corresponding detections processed.")
        actions.append("Assign surge analysts to triage queued predictions immediately.")
    elif backlog >= backlog_major:
        severity = 2
        status = "critical_backlog"
        drivers.append("Predictions are outpacing detections creating a critical analyst backlog.")
        actions.append("Assign surge analysts to triage queued predictions immediately.")
    elif backlog >= backlog_minor:
        severity = max(severity, 1)
        status = "backlog"
        drivers.append("Analyst queue is building as predictions exceed detections.")
        actions.append("Schedule additional analysts to work through the prediction queue.")

    if det_count and pred_count == 0:
        severity = 2
        status = "prediction_gap"
        drivers.append("Detections lack matching predictions indicating modelling gaps.")
        actions.append("Coordinate with modelling teams to regenerate predictions for unmatched detections.")
    elif unmatched >= shortfall_major:
        severity = 2
        status = "prediction_gap"
        drivers.append("Detection volume is outpacing predictions signalling modelling drift.")
        actions.append("Coordinate with modelling teams to regenerate predictions for unmatched detections.")
    elif unmatched >= shortfall_minor:
        severity = max(severity, 1)
        if status == "balanced":
            status = "prediction_gap_watch"
        drivers.append("Detections are trending higher than predictions; monitor modelling coverage.")
        actions.append("Audit prediction pipeline for missed detection classes.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        severity = max(severity, 1)
        drivers.append("Low weighted detection confidence is slowing analyst triage cycles.")
        actions.append("Pair analysts with sensor engineers to revalidate low-confidence detections.")
        if status == "balanced":
            status = "quality_watch"

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.6:
        severity = 2
        drivers.append("Feedback accuracy is degraded, extending review loops.")
        actions.append("Initiate focused feedback calibration to restore analyst confidence.")
        if status in {"balanced", "quality_watch"}:
            status = "feedback_strain"

    readiness_level = (readiness.get("level") or "").lower()
    if readiness_level in {"critical", "strained"}:
        drivers.append("Response readiness is already strained, limiting analyst slack.")

    clearance: Optional[float] = None
    if rate_per_hour and backlog:
        clearance = round(backlog / max(rate_per_hour, 0.01), 2)

    support_window = readiness.get("support_window_hours")
    if isinstance(support_window, (float, int)):
        clearance = min(clearance, float(support_window)) if clearance else float(support_window)

    drivers = list(dict.fromkeys(drivers))
    actions = list(dict.fromkeys(actions))

    pressure: Dict[str, Any] = {
        "status": status,
        "pending_predictions": backlog,
        "unmatched_detections": unmatched,
        "inbox_ratio": ratio,
        "severity": severity,
    }
    if clearance is not None:
        pressure["estimated_clearance_hours"] = clearance
    if drivers:
        pressure["drivers"] = drivers
    if actions:
        pressure["recommended_actions"] = actions

    return pressure


def _derive_support_priorities(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Translate analytics into concrete cross-team support priorities."""

    readiness = brief.get("response_readiness") or {}
    posture = brief.get("operational_posture") or {}
    pressure = brief.get("response_pressure") or {}
    freshness = brief.get("data_freshness") or {}
    detection_quality = brief.get("detection_quality") or {}
    gaps = brief.get("intelligence_gaps") or []
    health = brief.get("health") or {}

    priorities: List[Dict[str, Any]] = []
    drivers: List[str] = []
    actions: List[str] = []
    severity = 0

    def _add_priority(
        team: str,
        urgency: str,
        reason: str,
        *,
        window: Optional[float] = None,
        action: Optional[str] = None,
    ) -> None:
        entry: Dict[str, Any] = {"team": team, "urgency": urgency, "reason": reason}
        if isinstance(window, (float, int)):
            entry["support_window_hours"] = round(float(window), 2)
        priorities.append(entry)
        drivers.append(reason)
        if action:
            actions.append(action)

    readiness_level = str(readiness.get("level", "")).lower()
    support_window = readiness.get("support_window_hours")
    if readiness_level == "critical":
        severity = max(severity, 2)
        _add_priority(
            "Command Liaison",
            "immediate",
            "Response readiness is critical and requires leadership intervention.",
            window=support_window,
            action="Notify command staff and mobilise reserve teams to restore readiness.",
        )
    elif readiness_level == "strained":
        severity = max(severity, 1)
        _add_priority(
            "Command Liaison",
            "next_shift",
            "Response readiness is strained and needs staffing adjustments.",
            window=support_window,
            action="Coordinate staffing adjustments to relieve strained readiness levels.",
        )

    posture_status = str(posture.get("status", "")).lower()
    if posture_status == "recover":
        severity = max(severity, 2)
        _add_priority(
            "Command Liaison",
            "immediate",
            "Operational posture is in recovery and needs executive oversight.",
            window=support_window,
            action="Stand up an incident bridge to steer recovery operations.",
        )
    elif posture_status == "reinforce":
        severity = max(severity, 1)
        _add_priority(
            "Operations Planning",
            "next_shift",
            "Operational posture requires reinforcement across watch rotations.",
            window=support_window,
            action="Extend watch rotations and confirm reinforcement resources are booked.",
        )

    pressure_status = str(pressure.get("status", "")).lower()
    backlog = pressure.get("pending_predictions")
    unmatched = pressure.get("unmatched_detections")
    clearance = pressure.get("estimated_clearance_hours")
    if pressure_status == "critical_backlog":
        severity = max(severity, 2)
        _add_priority(
            "Analysis Cell",
            "immediate",
            "Analyst queue is critically backlogged and requires surge staffing.",
            window=clearance,
            action="Deploy surge analysts to clear the critical prediction backlog.",
        )
    elif pressure_status == "backlog":
        severity = max(severity, 1)
        _add_priority(
            "Analysis Cell",
            "next_shift",
            "Analyst workload backlog is forming as predictions outpace detections.",
            window=clearance,
            action="Schedule additional analysts to work down the prediction backlog.",
        )

    if pressure_status in {"prediction_gap", "prediction_gap_watch"} or (
        isinstance(unmatched, (int, float)) and unmatched > 0
    ):
        severity = max(severity, 2 if pressure_status == "prediction_gap" else 1)
        _add_priority(
            "Model Operations",
            "immediate" if pressure_status == "prediction_gap" else "next_shift",
            "Detections are outpacing predictions and require model support.",
            window=clearance,
            action="Task model operations to regenerate predictions for unmatched detections.",
        )

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        status = str(feed_info.get("status", "")).lower()
        age = feed_info.get("age_minutes")
        if status == "stale":
            severity = max(severity, 2)
            _add_priority(
                "Telemetry Operations",
                "immediate",
                f"{feed_name.capitalize()} feed is stale and requires recovery support.",
                window=age,
                action=f"Deploy telemetry engineers to restore the {feed_name} feed immediately.",
            )
        elif status == "warning":
            severity = max(severity, 1)
            _add_priority(
                "Telemetry Operations",
                "next_shift",
                f"{feed_name.capitalize()} feed freshness is degrading and needs attention.",
                window=age,
                action=f"Schedule telemetry checks to stabilise the {feed_name} feed before it stalls.",
            )

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        severity = max(severity, 1)
        _add_priority(
            "Sensor Engineering",
            "next_shift",
            "Weighted detection confidence is degrading below 0.60.",
            action="Partner with sensor engineering to uplift low-confidence detections.",
        )

    low_conf_classes = detection_quality.get("low_confidence_classes")
    if isinstance(low_conf_classes, list) and low_conf_classes:
        severity = max(severity, 1)
        classes = ", ".join(sorted(set(str(cls) for cls in low_conf_classes)))
        _add_priority(
            "Sensor Engineering",
            "next_shift",
            f"Low-confidence detections detected for classes: {classes}.",
            action="Calibrate affected sensors to restore confidence in highlighted classes.",
        )

    sparse_classes = detection_quality.get("sparse_class_coverage")
    if isinstance(sparse_classes, list) and sparse_classes:
        severity = max(severity, 1)
        classes = ", ".join(sorted(set(str(cls) for cls in sparse_classes)))
        _add_priority(
            "Collection Planning",
            "next_shift",
            f"Detection coverage is sparse for classes: {classes}.",
            action="Task collection planning to expand coverage for the sparse classes.",
        )

    gap_team_map = {
        "prediction_coverage": "Model Operations",
        "prediction_visibility": "Model Operations",
        "detections_freshness": "Telemetry Operations",
        "predictions_freshness": "Telemetry Operations",
        "clusters_freshness": "Telemetry Operations",
        "feedback_accuracy": "Analyst Enablement",
        "cluster_scoring": "Data Science Ops",
    }

    for gap in gaps if isinstance(gaps, list) else []:
        gap_name = str(gap.get("gap", ""))
        team = gap_team_map.get(gap_name)
        if not team:
            continue
        detail = str(gap.get("detail", "")) or "Gap detected."
        severity = max(severity, 2 if gap.get("severity") == "critical" else 1)
        urgency = "immediate" if gap.get("severity") == "critical" else "next_shift"
        action = gap.get("recommended_action")
        _add_priority(team, urgency, detail, action=action)

    risk_level = str(health.get("risk_level", "")).lower()
    if risk_level in {"high", "severe"}:
        severity = max(severity, 2)
        _add_priority(
            "Incident Management",
            "immediate",
            f"Overall risk level is {risk_level} and warrants a coordinated response.",
            action="Convene cross-functional leadership to manage the elevated risk.",
        )
    elif risk_level in {"elevated"}:
        severity = max(severity, 1)
        _add_priority(
            "Incident Management",
            "next_shift",
            "Risk level is elevated and benefits from additional oversight.",
            action="Assign an incident coordinator to monitor elevated risk conditions.",
        )

    if not priorities and severity == 0:
        return {"status": "monitor"}

    unique_priorities: List[Dict[str, Any]] = []
    seen = set()
    for entry in priorities:
        key = (entry.get("team"), entry.get("reason"))
        if key in seen:
            continue
        seen.add(key)
        unique_priorities.append(entry)

    priorities = unique_priorities
    drivers = list(dict.fromkeys(drivers))
    actions = list(dict.fromkeys(actions))

    status = "monitor"
    if severity >= 2:
        status = "mobilise"
    elif severity == 1:
        status = "reinforce"

    summary: Dict[str, Any] = {
        "status": status,
        "severity": severity,
    }
    if priorities:
        summary["priorities"] = priorities
        summary["teams"] = sorted({entry["team"] for entry in priorities})
    if drivers:
        summary["drivers"] = drivers
    if actions:
        summary["recommended_actions"] = actions

    return summary


def _derive_intelligence_gaps(brief: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """Highlight critical intelligence coverage or fidelity gaps.

    The brief already aggregates numerous signals (tempo, freshness, posture,
    health, etc.).  This helper scans those pre-computed blocks to surface
    concrete gaps analysts should close quickly.  Each gap carries a severity
    indicator and an optional remediation action that feeds back into the
    consolidated recommendations list.
    """

    gaps: List[Dict[str, Any]] = []

    def _add_gap(key: str, *, severity: str, detail: str, action: Optional[str] = None) -> None:
        entry: Dict[str, Any] = {"gap": key, "severity": severity, "detail": detail}
        if action:
            entry["recommended_action"] = action
        gaps.append(entry)

    activity_summary = brief.get("activity_summary") or {}
    detections = activity_summary.get("detections")
    predictions = activity_summary.get("predictions")
    coverage = activity_summary.get("prediction_coverage")

    if isinstance(coverage, (float, int)):
        if coverage < 0.4:
            _add_gap(
                "prediction_coverage",
                severity="critical",
                detail="Prediction coverage is critically low (below 40%).",
                action="Escalate inference pipeline recovery to restore prediction coverage.",
            )
        elif coverage < 0.7:
            _add_gap(
                "prediction_coverage",
                severity="major",
                detail="Prediction coverage is drifting under 70%.",
                action="Audit inference workloads to improve prediction throughput.",
            )
    elif isinstance(detections, (float, int)) and detections and not predictions:
        _add_gap(
            "prediction_visibility",
            severity="major",
            detail="Predictions are missing despite active detections.",
            action="Verify prediction exports are enabled for the selected window.",
        )

    freshness = brief.get("data_freshness") or {}
    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        status = str(feed_info.get("status", "")).lower()
        age = feed_info.get("age_minutes")
        if status == "stale":
            detail = (
                f"{feed_name.capitalize()} feed is stale"
                + (f" (~{age:.0f} minutes old)." if isinstance(age, (float, int)) else ".")
            )
            _add_gap(
                f"{feed_name}_freshness",
                severity="critical",
                detail=detail,
                action="Dispatch telemetry recovery for the stale data feed.",
            )
        elif status == "warning":
            detail = (
                f"{feed_name.capitalize()} feed freshness is degrading"
                + (f" (~{age:.0f} minutes old)." if isinstance(age, (float, int)) else ".")
            )
            _add_gap(
                f"{feed_name}_freshness",
                severity="major",
                detail=detail,
                action="Investigate latency before the feed becomes stale.",
            )
        elif status == "unknown":
            _add_gap(
                f"{feed_name}_freshness",
                severity="minor",
                detail=f"Freshness for the {feed_name} feed is unknown.",
            )

    meta = brief.get("meta") or {}
    feedback_accuracy = meta.get("feedback_accuracy")
    if feedback_accuracy is None:
        _add_gap(
            "feedback_accuracy",
            severity="major",
            detail="Feedback accuracy telemetry is unavailable for this window.",
            action="Resume feedback capture to restore analyst accuracy tracking.",
        )
    elif isinstance(feedback_accuracy, (float, int)):
        if feedback_accuracy < 0.6:
            _add_gap(
                "feedback_accuracy",
                severity="critical",
                detail="Feedback accuracy is below 60%.",
                action="Schedule immediate analyst calibration to lift accuracy.",
            )
        elif feedback_accuracy < 0.75:
            _add_gap(
                "feedback_accuracy",
                severity="major",
                detail="Feedback accuracy is trending below 75%.",
                action="Plan refresher training to stabilise analyst accuracy.",
            )

    cluster_count = meta.get("cluster_count")
    if isinstance(cluster_count, (int, float)) and cluster_count > 0 and not brief.get("cluster_threats"):
        _add_gap(
            "cluster_scoring",
            severity="major",
            detail="Movement clusters are present but threat scoring is unavailable.",
            action="Validate the cluster scoring service is healthy.",
        )

    if not gaps:
        return None

    # Deduplicate gaps by (gap, detail) pairs in case heuristics overlap.
    unique: List[Dict[str, Any]] = []
    seen = set()
    for gap in gaps:
        key = (gap.get("gap"), gap.get("detail"))
        if key in seen:
            continue
        seen.add(key)
        unique.append(gap)

    return unique


def _derive_intelligence_confidence(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Synthesize a confidence index across telemetry quality signals."""

    meta = brief.get("meta") or {}
    detection_quality = brief.get("detection_quality") or {}
    freshness = brief.get("data_freshness") or {}
    gaps = brief.get("intelligence_gaps") or []
    health = brief.get("health") or {}

    score = 100.0
    drivers: List[str] = []
    actions: List[str] = []
    components: Dict[str, Any] = {}

    def penalise(amount: float, reason: str, action: Optional[str] = None) -> None:
        nonlocal score
        score = max(0.0, score - float(amount))
        if reason:
            drivers.append(reason)
        if action:
            actions.append(action)

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)):
        accuracy = max(0.0, min(1.0, float(feedback_accuracy)))
        components["feedback_accuracy"] = round(accuracy, 3)
        if accuracy < 0.5:
            penalise(
                30,
                "Feedback accuracy has fallen below 50%, reducing confidence in labelling telemetry.",
                "Schedule immediate analyst calibration to restore feedback accuracy.",
            )
        elif accuracy < 0.7:
            penalise(
                18,
                "Feedback accuracy is trending under 70%, signalling noisy validation loops.",
                "Run targeted spot-checks with senior analysts to uplift feedback accuracy.",
            )
        elif accuracy < 0.85:
            penalise(
                8,
                "Feedback accuracy is dipping below 85%, warranting close observation.",
            )
    else:
        penalise(
            10,
            "Feedback accuracy telemetry is unavailable for this window, introducing uncertainty.",
            "Ensure analysts continue logging feedback accuracy so confidence metrics remain trustworthy.",
        )

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)):
        weighted = max(0.0, min(1.0, float(weighted_conf)))
        components["weighted_confidence"] = round(weighted, 3)
        if weighted < 0.5:
            penalise(
                28,
                "Weighted detection confidence has collapsed below 0.50.",
                "Coordinate sensor and model recalibration to restore detection confidence.",
            )
        elif weighted < 0.65:
            penalise(
                16,
                "Weighted detection confidence is trending under 0.65, signalling classifier drift.",
                "Prioritise sensor calibration and model refresh to stabilise confidence scores.",
            )
        elif weighted < 0.75:
            penalise(
                6,
                "Weighted detection confidence is edging below 0.75.",
            )
    elif detection_quality:
        penalise(
            12,
            "Detection quality is available but missing weighted confidence metrics.",
            "Review detection quality logging to ensure weighted confidence is captured.",
        )
    else:
        penalise(
            14,
            "Detection quality telemetry is unavailable, obscuring classifier trust signals.",
            "Re-enable detection quality analytics to monitor classifier health.",
        )

    active_ratio = detection_quality.get("active_class_ratio")
    if isinstance(active_ratio, (float, int)):
        ratio = max(0.0, min(1.0, float(active_ratio)))
        components["active_class_ratio"] = round(ratio, 3)
        if ratio < 0.4:
            penalise(
                18,
                "Only a small fraction of tracked classes are appearing in detections.",
                "Expand collection coverage or validate sensor placement to diversify detections.",
            )
        elif ratio < 0.6:
            penalise(
                8,
                "Detection coverage across classes is limited, reducing confidence breadth.",
            )

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    telemetry_summary: Dict[str, Any] = {}
    if isinstance(feeds, dict) and feeds:
        stale = [name for name, feed in feeds.items() if feed.get("status") == "stale"]
        warn = [name for name, feed in feeds.items() if feed.get("status") == "warning"]
        if stale:
            penalise(
                24 + 4 * (len(stale) - 1),
                f"Stale telemetry detected for feeds: {', '.join(sorted(stale))}.",
                "Escalate telemetry recovery to restore stale feeds and protect decision confidence.",
            )
            telemetry_summary["stale_feeds"] = sorted(stale)
        if warn:
            penalise(
                10 + 2 * (len(warn) - 1),
                f"Telemetry latency warnings across feeds: {', '.join(sorted(warn))}.",
                "Schedule telemetry checks to prevent warning feeds from degrading into outages.",
            )
            telemetry_summary["warning_feeds"] = sorted(warn)
    else:
        telemetry_summary["feeds_tracked"] = 0

    if telemetry_summary:
        components["telemetry"] = telemetry_summary

    critical_gaps = 0
    major_gaps = 0
    for gap in gaps if isinstance(gaps, list) else []:
        severity = str(gap.get("severity", "")).lower()
        if severity == "critical":
            critical_gaps += 1
        elif severity == "major":
            major_gaps += 1

    if critical_gaps:
        penalise(
            20 + 6 * (critical_gaps - 1),
            f"{critical_gaps} critical intelligence gap(s) are open.",
            "Stand up incident coordination to close critical intelligence gaps quickly.",
        )
    if major_gaps:
        penalise(
            10 + 3 * (major_gaps - 1),
            f"{major_gaps} major intelligence gap(s) remain unresolved.",
            "Task follow-up owners to remediate major intelligence gaps before they escalate.",
        )
    if critical_gaps or major_gaps:
        components["gap_summary"] = {
            "critical": critical_gaps,
            "major": major_gaps,
        }

    risk_level = str(health.get("risk_level", "")).lower()
    if risk_level in {"high", "severe"}:
        penalise(
            12 if risk_level == "high" else 18,
            "Overall brief health risk level is elevated, tempering intelligence confidence.",
        )
    confidence_band = str(health.get("confidence", "")).lower()
    if confidence_band == "low":
        penalise(10, "Health assessment reports low confidence across supporting signals.")
    elif confidence_band == "moderate":
        penalise(4, "Health assessment is only moderately confident in current telemetry.")

    score = max(0.0, min(100.0, score))
    if score >= 80:
        level = "high"
        status = "stable"
    elif score >= 60:
        level = "guarded"
        status = "watch"
    else:
        level = "low"
        status = "recover"

    drivers = list(dict.fromkeys(drivers))
    actions = list(dict.fromkeys(actions))

    confidence: Dict[str, Any] = {
        "score": round(score, 1),
        "level": level,
        "status": status,
    }
    if components:
        confidence["components"] = components
    if drivers:
        confidence["drivers"] = drivers
    if actions:
        confidence["recommended_actions"] = actions

    return confidence


def _derive_operational_outlook(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Project the near-term operational outlook from fused telemetry."""

    activity_summary = brief.get("activity_summary") or {}
    readiness = brief.get("response_readiness") or {}
    posture = brief.get("operational_posture") or {}
    pressure = brief.get("response_pressure") or {}
    freshness = brief.get("data_freshness") or {}
    detection_quality = brief.get("detection_quality") or {}
    health = brief.get("health") or {}
    support = brief.get("support_priorities") or {}
    confidence = brief.get("intelligence_confidence") or {}
    gaps = brief.get("intelligence_gaps") or []
    threats = brief.get("cluster_threats") or []

    if not any(
        [
            activity_summary,
            readiness,
            posture,
            pressure,
            freshness,
            detection_quality,
            health,
            support,
            confidence,
            gaps,
            threats,
        ]
    ):
        return None

    severity = 0
    drivers: List[str] = []
    actions: List[str] = []
    focus_areas: List[str] = []
    horizon_candidates: List[float] = []

    def _add_driver(message: str) -> None:
        if message:
            drivers.append(message)

    def _add_action(message: str) -> None:
        if message:
            actions.append(message)

    def _add_focus(area: str) -> None:
        if area:
            focus_areas.append(area)

    tempo = str(activity_summary.get("tempo", "")).lower()
    if tempo == "surge":
        severity += 2
        _add_driver("Operational tempo is surging across the assessment window.")
        _add_focus("Tempo management")
    elif tempo == "elevated":
        severity += 1
        _add_driver("Operational tempo remains elevated across the assessment window.")
        _add_focus("Tempo management")

    coverage = activity_summary.get("prediction_coverage")
    if isinstance(coverage, (float, int)):
        ratio = float(coverage)
        if ratio < 0.5:
            severity += 2
            _add_driver("Prediction coverage has fallen below 50% in the current window.")
            _add_focus("Prediction coverage")
        elif ratio < 0.75:
            severity += 1
            _add_driver("Prediction coverage is trending under 75%, signalling drift.")
            _add_focus("Prediction coverage")

    highest_threat_level: Optional[str] = None
    if threats:
        highest = max(
            threats,
            key=lambda cluster: (
                _threat_level_rank(cluster.get("threat_level")),
                cluster.get("threat_score", 0),
            ),
        )
        highest_threat_level = highest.get("threat_level")
        location = highest.get("nearest_site")
        rank = _threat_level_rank(highest_threat_level)
        if rank >= 3:
            severity += 4
            detail = "Critical movement clusters detected with imminent threat levels."
            if location:
                detail = f"Critical movement cluster activity is converging near {location}."
            _add_driver(detail)
            _add_focus("Critical movement clusters")
        elif rank == 2:
            severity += 3
            detail = "High-risk movement clusters are active within the window."
            if location:
                detail = f"High-risk movement clusters are tracking toward {location}."
            _add_driver(detail)
            _add_focus("High-risk clusters")
        elif rank == 1:
            severity += 1
            _add_driver("Moderate threat movement clusters require continued observation.")
            _add_focus("Cluster surveillance")

    risk_level = health.get("risk_level")
    risk_rank = _risk_level_rank(risk_level)
    if risk_rank >= 4:
        severity += 3
        _add_driver("Overall health assessment is severe and needs executive focus.")
        _add_focus("Risk mitigation")
    elif risk_rank >= 3:
        severity += 2
        _add_driver("Overall health risk remains high across the brief.")
        _add_focus("Risk mitigation")
    elif risk_rank >= 2:
        severity += 1
        _add_driver("Health risk is elevated and warrants stabilisation planning.")
        _add_focus("Risk mitigation")

    readiness_level = str(readiness.get("level", "")).lower()
    support_window = readiness.get("support_window_hours")
    if isinstance(support_window, (float, int)) and support_window > 0:
        horizon_candidates.append(float(support_window))
    if readiness_level == "critical":
        severity += 3
        _add_driver("Response readiness is critical and requires immediate reinforcement.")
        _add_focus("Staffing reinforcement")
        _add_action("Mobilise reserve analysts and command liaisons to restore readiness.")
    elif readiness_level == "strained":
        severity += 2
        _add_driver("Response readiness is strained with limited staffing slack.")
        _add_focus("Staffing reinforcement")
        _add_action("Coordinate staffing adjustments to relieve strained readiness levels.")
    elif readiness_level:
        _add_driver(f"Response readiness is {readiness_level} for this window.")

    posture_status = str(posture.get("status", "")).lower()
    posture_horizon = posture.get("horizon_hours")
    if isinstance(posture_horizon, (float, int)) and posture_horizon > 0:
        horizon_candidates.append(float(posture_horizon))
    if posture_status == "recover":
        severity += 3
        _add_driver("Operational posture is in recovery mode after telemetry degradations.")
        _add_focus("Telemetry recovery")
        _add_action("Sustain the telemetry recovery bridge until feeds stabilise.")
    elif posture_status == "reinforce":
        severity += 2
        _add_driver("Operational posture calls for reinforcement across watch rotations.")
        _add_focus("Reinforcement planning")
    elif posture_status == "stabilise":
        severity += 1
        _add_driver("Operational posture prioritises stabilisation activities.")
        _add_focus("Stabilisation planning")

    pressure_status = str(pressure.get("status", "")).lower()
    clearance = pressure.get("estimated_clearance_hours")
    if isinstance(clearance, (float, int)) and clearance > 0:
        horizon_candidates.append(float(clearance))
    if pressure_status == "critical_backlog":
        severity += 3
        _add_driver("Analyst backlog is critical with predictions outpacing triage capacity.")
        _add_focus("Analyst throughput")
        _add_action("Stand up a surge triage cell to burn down the backlog.")
    elif pressure_status in {"prediction_gap", "feedback_strain"}:
        severity += 2
        _add_driver("Analyst pressure highlights modelling or feedback shortfalls.")
        _add_focus("Analyst throughput")
    elif pressure_status in {"backlog", "quality_watch", "prediction_gap_watch"}:
        severity += 1
        _add_driver("Analyst workload is building and needs close monitoring.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    stale_feeds: List[str] = []
    warn_feeds: List[str] = []
    if isinstance(feeds, dict) and feeds:
        for name, feed in feeds.items():
            status = str(feed.get("status", "")).lower()
            if status == "stale":
                stale_feeds.append(str(name))
            elif status == "warning":
                warn_feeds.append(str(name))
        if stale_feeds:
            severity += 3
            names = ", ".join(sorted(stale_feeds))
            _add_driver(f"Stale telemetry detected for feeds: {names}.")
            _add_focus("Telemetry recovery")
            _add_action("Restore stale telemetry pipelines to close critical blind spots.")
        elif warn_feeds:
            severity += 1
            names = ", ".join(sorted(warn_feeds))
            _add_driver(f"Telemetry freshness warnings for feeds: {names}.")
            _add_focus("Telemetry monitoring")
    worst_minutes = freshness.get("worst_case_minutes")
    if isinstance(worst_minutes, (float, int)) and worst_minutes > 0:
        horizon_candidates.append(float(worst_minutes) / 60.0)

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)):
        weighted = float(weighted_conf)
        if weighted < 0.55:
            severity += 2
            _add_driver("Weighted detection confidence has dropped below 0.55.")
            _add_focus("Sensor calibration")
            _add_action("Pair analysts with sensor engineers to revalidate low-confidence detections.")
        elif weighted < 0.7:
            severity += 1
            _add_driver("Weighted detection confidence is trending below 0.70.")
            _add_focus("Sensor calibration")
    elif detection_quality:
        _add_driver("Detection quality telemetry is incomplete for this window.")

    sparse_classes = detection_quality.get("sparse_class_coverage")
    if isinstance(sparse_classes, list) and sparse_classes:
        _add_focus("Collection balance")

    critical_gaps = sum(1 for gap in gaps if gap.get("severity") == "critical")
    major_gaps = sum(1 for gap in gaps if gap.get("severity") == "major")
    if critical_gaps:
        severity += min(4, critical_gaps * 2)
        _add_driver(f"{critical_gaps} critical intelligence gap(s) remain unresolved.")
        _add_focus("Intelligence gaps")
        _add_action("Assign owners to close critical intelligence gaps before the next shift.")
    elif major_gaps:
        severity += 1
        _add_driver(f"{major_gaps} major intelligence gap(s) need follow-up.")
        _add_focus("Intelligence gaps")

    support_status = str(support.get("status", "")).lower()
    if support_status == "mobilise":
        severity += 2
        _add_driver("Support coordination recommends immediate mobilisation across teams.")
        _add_focus("Cross-team coordination")
    elif support_status == "reinforce":
        severity += 1
        _add_driver("Support coordination recommends reinforcement tasks across teams.")
        _add_focus("Cross-team coordination")

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        severity += 2
        _add_driver("Intelligence confidence is low, limiting trust in recommendations.")
        _add_focus("Telemetry validation")
        _add_action("Launch a telemetry validation sprint to rebuild intelligence confidence.")
    elif confidence_level == "guarded":
        severity += 1
        _add_driver("Intelligence confidence is guarded and needs validation work.")
        _add_focus("Telemetry validation")

    drivers = list(dict.fromkeys(drivers))
    actions = list(dict.fromkeys(actions))
    focus_areas = list(dict.fromkeys(focus_areas))

    if severity >= 12:
        status = "escalation_imminent"
    elif severity >= 8:
        status = "rapid_response"
    elif severity >= 5:
        status = "heightened_watch"
    elif severity >= 3:
        status = "stabilise"
    else:
        status = "steady_watch"

    if severity >= 12:
        _add_action("Brief senior leadership on imminent escalation scenarios and activate contingency plans.")
    elif severity >= 8:
        _add_action("Maintain a rapid response posture and pre-stage reinforcement assets for the next few hours.")
    elif severity >= 5:
        _add_action("Sustain heightened watch rotations and coordinate targeted mitigations.")
    elif severity >= 3:
        _add_action("Execute stabilisation measures to relieve operational pressure.")

    planning_horizon: Optional[float] = None
    positive_windows = [window for window in horizon_candidates if window and window > 0]
    if positive_windows:
        planning_horizon = round(min(positive_windows), 2)

    outlook: Dict[str, Any] = {
        "status": status,
        "severity_score": int(severity),
    }
    if planning_horizon is not None:
        outlook["planning_horizon_hours"] = planning_horizon
    if focus_areas:
        outlook["focus_areas"] = focus_areas
    if drivers:
        outlook["drivers"] = drivers
    if actions:
        outlook["recommended_actions"] = actions
    if confidence_level:
        outlook["intelligence_confidence"] = confidence_level
    if highest_threat_level:
        outlook["dominant_threat_level"] = highest_threat_level
    if critical_gaps or major_gaps:
        outlook["gap_summary"] = {"critical": int(critical_gaps), "major": int(major_gaps)}

    pending_predictions = pressure.get("pending_predictions")
    if isinstance(pending_predictions, (int, float)):
        outlook["pending_predictions"] = int(pending_predictions)
    unmatched = pressure.get("unmatched_detections")
    if isinstance(unmatched, (int, float)):
        outlook["unmatched_detections"] = int(unmatched)

    return outlook


def _derive_command_directives(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Synthesize leadership-facing directives from fused analytics."""

    outlook = brief.get("operational_outlook") or {}
    posture = brief.get("operational_posture") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    confidence = brief.get("intelligence_confidence") or {}
    health = brief.get("health") or {}
    gaps = brief.get("intelligence_gaps") or []
    recommendations = brief.get("recommendations") or []

    if not any(
        [
            outlook,
            posture,
            readiness,
            pressure,
            support,
            confidence,
            health,
            gaps,
            recommendations,
        ]
    ):
        return None

    severity = 0
    drivers: List[str] = []
    focus_areas: List[str] = []
    coordination_teams: List[str] = []
    window_candidates: List[float] = []
    directives: List[Dict[str, Any]] = []
    seen_actions: set[str] = set()

    priority_order = {"immediate": 0, "next_shift": 1, "monitor": 2}

    def _add_driver(message: str) -> None:
        if message:
            drivers.append(message)

    def _add_focus(text: str) -> None:
        if text:
            focus_areas.append(text)

    def _add_team(team: Optional[str]) -> None:
        if team:
            coordination_teams.append(str(team))

    def _register_window(value: Any) -> None:
        if isinstance(value, (float, int)) and value > 0:
            window_candidates.append(float(value))

    def _normalise_priority(priority: Any) -> str:
        key = str(priority or "").lower()
        return key if key in priority_order else "monitor"

    def _add_directive(
        priority: Any,
        action: Any,
        *,
        source: str,
        context: Optional[str] = None,
        window: Any = None,
    ) -> None:
        text = str(action or "").strip()
        if not text:
            return
        if text.lower() in seen_actions:
            return
        seen_actions.add(text.lower())
        normalized_priority = _normalise_priority(priority)
        entry: Dict[str, Any] = {
            "priority": normalized_priority,
            "action": text,
            "source": source,
        }
        if context:
            entry["context"] = context
        if isinstance(window, (float, int)) and window > 0:
            entry["window_hours"] = round(float(window), 2)
        directives.append(entry)

    def _bump_severity(amount: int) -> None:
        nonlocal severity
        severity += max(0, int(amount))

    outlook_severity = outlook.get("severity_score")
    if isinstance(outlook_severity, (int, float)):
        _bump_severity(int(outlook_severity))
    if isinstance(outlook.get("focus_areas"), list):
        for area in outlook["focus_areas"]:
            _add_focus(str(area))
    _register_window(outlook.get("planning_horizon_hours"))
    if outlook.get("recommended_actions"):
        outlook_priority = "immediate" if severity >= 12 else ("next_shift" if severity >= 6 else "monitor")
        for action in outlook.get("recommended_actions", []):
            _add_directive(outlook_priority, action, source="Operational outlook")

    posture_status = str(posture.get("status", "")).lower()
    posture_focus = posture.get("focus")
    if isinstance(posture_focus, str) and posture_focus:
        _add_focus(posture_focus)
    _register_window(posture.get("horizon_hours"))
    if posture_status == "recover":
        _bump_severity(5)
        _add_driver("Operational posture is in recovery mode and needs immediate steering.")
    elif posture_status == "stabilise":
        _bump_severity(3)
        _add_driver("Operational posture recommends stabilisation efforts across the shift.")
    elif posture_status == "reinforce":
        _bump_severity(2)
        _add_driver("Operational posture calls for reinforcement of monitoring teams.")

    readiness_level = str(readiness.get("level", "")).lower()
    _register_window(readiness.get("support_window_hours"))
    readiness_priority = "monitor"
    if readiness_level == "critical":
        _bump_severity(6)
        readiness_priority = "immediate"
        _add_driver("Response readiness is critical and needs leadership intervention.")
    elif readiness_level == "strained":
        _bump_severity(3)
        readiness_priority = "next_shift"
        _add_driver("Response readiness is strained and requires reinforcement.")
    for action in readiness.get("priority_actions", []):
        _add_directive(readiness_priority, action, source="Response readiness")

    pressure_status = str(pressure.get("status", "")).lower()
    _register_window(pressure.get("estimated_clearance_hours"))
    pressure_priority = "monitor"
    if pressure_status == "critical_backlog":
        _bump_severity(5)
        pressure_priority = "immediate"
        _add_driver("Analyst response pressure reports a critical backlog of predictions.")
    elif pressure_status == "prediction_gap":
        _bump_severity(4)
        pressure_priority = "immediate"
        _add_driver("Prediction gaps require immediate model support.")
    elif pressure_status in {"feedback_strain", "backlog", "prediction_gap_watch"}:
        _bump_severity(3)
        pressure_priority = "next_shift"
        _add_driver("Analyst workload is straining and needs targeted relief.")
    elif pressure_status in {"quality_watch"}:
        _bump_severity(1)
        pressure_priority = "monitor"
    for action in pressure.get("recommended_actions", []):
        _add_directive(pressure_priority, action, source="Response pressure")

    support_status = str(support.get("status", "")).lower()
    support_priority = "monitor"
    if support_status == "mobilise":
        _bump_severity(5)
        support_priority = "immediate"
        _add_driver("Support coordination recommends immediate mobilisation across teams.")
    elif support_status == "reinforce":
        _bump_severity(3)
        support_priority = "next_shift"
        _add_driver("Support coordination calls for reinforcement tasks across teams.")
    for action in support.get("recommended_actions", []):
        _add_directive(support_priority, action, source="Support priorities")
    for entry in support.get("priorities", []):
        if not isinstance(entry, dict):
            continue
        reason = str(entry.get("reason", "")).strip()
        if not reason:
            continue
        urgency = entry.get("urgency")
        team = entry.get("team")
        _add_team(team)
        _register_window(entry.get("support_window_hours"))
        _add_directive(urgency, reason, source="Support priorities", context=str(team or ""), window=entry.get("support_window_hours"))
    for team in support.get("teams", []):
        _add_team(team)

    confidence_level = str(confidence.get("level", "")).lower()
    confidence_priority = "monitor"
    if confidence_level == "low":
        _bump_severity(3)
        confidence_priority = "immediate"
        _add_driver("Intelligence confidence is low and demands validation work.")
    elif confidence_level == "guarded":
        _bump_severity(1)
        confidence_priority = "next_shift"
        _add_driver("Intelligence confidence is guarded and should be monitored.")
    for action in confidence.get("recommended_actions", []):
        _add_directive(confidence_priority, action, source="Intelligence confidence")

    risk_level = str(health.get("risk_level", "")).lower()
    health_priority = "monitor"
    if risk_level in {"severe", "critical"}:
        _bump_severity(5)
        health_priority = "immediate"
        _add_driver("Health assessment reports severe risk conditions.")
    elif risk_level == "high":
        _bump_severity(4)
        health_priority = "immediate"
        _add_driver("Health assessment reports high operational risk.")
    elif risk_level == "elevated":
        _bump_severity(2)
        health_priority = "next_shift"
        _add_driver("Health assessment remains elevated and needs oversight.")
    for action in health.get("recommended_actions", []):
        _add_directive(health_priority, action, source="Health assessment")

    critical_gaps = 0
    major_gaps = 0
    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity_label = str(gap.get("severity", "")).lower()
        action = gap.get("recommended_action")
        detail = str(gap.get("detail", ""))
        if severity_label == "critical":
            critical_gaps += 1
            _bump_severity(4)
            _add_directive("immediate", action or detail, source="Intelligence gaps", context=str(gap.get("gap", "")))
        elif severity_label == "major":
            major_gaps += 1
            _bump_severity(2)
            _add_directive("next_shift", action or detail, source="Intelligence gaps", context=str(gap.get("gap", "")))
        elif action:
            _add_directive("monitor", action, source="Intelligence gaps", context=str(gap.get("gap", "")))
    if critical_gaps:
        _add_driver(f"{critical_gaps} critical intelligence gap(s) remain open.")
    if major_gaps:
        _add_driver(f"{major_gaps} major intelligence gap(s) require follow-up.")

    if not directives and recommendations:
        default_priority = "monitor"
        if severity >= 12:
            default_priority = "immediate"
        elif severity >= 6:
            default_priority = "next_shift"
        for action in recommendations:
            _add_directive(default_priority, action, source="Brief summary")

    drivers = list(dict.fromkeys(drivers))
    focus_areas = list(dict.fromkeys(focus_areas))
    coordination_teams = sorted({team for team in coordination_teams if team})
    directives.sort(key=lambda item: (priority_order.get(item.get("priority", "monitor"), 2), item.get("action", "")))

    severity = max(0, min(severity, 30))
    if severity >= 20:
        status = "escalate"
    elif severity >= 12:
        status = "accelerate"
    elif severity >= 6:
        status = "focus"
    else:
        status = "monitor"

    planning_window: Optional[float] = None
    positive_windows = [window for window in window_candidates if window and window > 0]
    if positive_windows:
        planning_window = round(min(positive_windows), 2)

    directive_counts = {
        label: sum(1 for entry in directives if entry.get("priority") == label)
        for label in priority_order
    }
    directive_counts = {key: value for key, value in directive_counts.items() if value}

    payload: Dict[str, Any] = {
        "status": status,
        "severity": severity,
    }
    if planning_window is not None:
        payload["planning_window_hours"] = planning_window
    if directives:
        payload["directives"] = directives
    if directive_counts:
        payload["directive_counts"] = directive_counts
    if focus_areas:
        payload["focus_areas"] = focus_areas
    if drivers:
        payload["drivers"] = drivers
    if coordination_teams:
        payload["coordination_teams"] = coordination_teams

    return payload if payload else None


def _derive_operational_recovery(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Derive an operational recovery roadmap from mission resilience telemetry."""

    continuity = brief.get("operational_continuity") or {}
    resilience = brief.get("operational_resilience") or {}
    assurance = brief.get("mission_assurance") or {}
    sustainment = brief.get("resource_sustainment") or {}
    alignment = brief.get("command_alignment") or {}
    directives = brief.get("command_directives") or {}
    support = brief.get("support_priorities") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    escalation = brief.get("escalation_readiness") or {}
    outlook = brief.get("operational_outlook") or {}
    risks = brief.get("operational_risks") or {}
    contingency = brief.get("contingency_plans") or {}
    communication = brief.get("communication_plan") or {}
    confidence = brief.get("intelligence_confidence") or {}
    gaps = brief.get("intelligence_gaps") or []
    freshness = brief.get("data_freshness") or {}

    if not any(
        [
            continuity,
            resilience,
            assurance,
            sustainment,
            alignment,
            directives,
            support,
            readiness,
            pressure,
            escalation,
            outlook,
            risks,
            contingency,
            communication,
            confidence,
            gaps,
            freshness,
        ]
    ):
        return None

    score = 100.0
    drivers: List[str] = []
    momentum: List[str] = []
    actions: List[str] = []
    stabilisation: List[str] = []
    dependencies: List[str] = []
    watch_items: List[str] = []
    windows: List[float] = []
    tracks: List[Dict[str, Any]] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = max(0.0, score - float(amount))
        if note:
            drivers.append(str(note))

    def _reward(message: Optional[str]) -> None:
        if message:
            momentum.append(str(message))

    def _collect_actions(values: Optional[Iterable[Any]], *, stabilise: bool = False) -> None:
        for value in values or []:
            if not value:
                continue
            text = str(value)
            actions.append(text)
            if stabilise:
                stabilisation.append(text)

    def _collect_drivers(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                drivers.append(str(value))

    def _collect_dependencies(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            label: Optional[str] = None
            if isinstance(value, dict):
                for key in ("name", "resource", "reason", "focus", "constraint", "detail", "gap"):
                    if value.get(key):
                        label = str(value[key])
                        break
            elif value:
                label = str(value)
            if label:
                dependencies.append(label)

    def _collect_watch(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                watch_items.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    def _build_track(
        name: str,
        *,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        focus: Optional[str] = None,
        action_candidates: Optional[Iterable[Any]] = None,
    ) -> None:
        entries: List[str] = []
        for value in action_candidates or []:
            if value:
                entries.append(str(value))
        if not (name and (focus or entries)):
            return
        track: Dict[str, Any] = {"name": name}
        if status:
            track["status"] = str(status)
        if owner:
            track["owner"] = str(owner)
        if focus:
            track["focus"] = str(focus)
        if entries:
            track["actions"] = list(dict.fromkeys(entries))[:5]
        tracks.append(track)

    continuity_status = str(continuity.get("status", "")).lower()
    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)):
        if continuity_score < 55:
            _penalise(24, "Continuity posture is critical and requires recovery focus.")
        elif continuity_score < 70:
            _penalise(16, "Continuity posture is strained and limits restoration efforts.")
        elif continuity_score < 82:
            _penalise(8, "Continuity posture is on watch for degradation.")
        else:
            _reward("Continuity controls are sustaining core services.")
    elif continuity_status in {"critical", "strained"}:
        _penalise(16, "Continuity status indicates recovery pressure.")

    _collect_actions(continuity.get("recommended_actions"), stabilise=True)
    _collect_drivers(continuity.get("drivers"))
    _collect_dependencies(continuity.get("primary_constraints"))
    _collect_watch(continuity.get("continuity_risks"))
    _collect_watch(continuity.get("watch_items"))
    _register_window(continuity.get("continuity_horizon_hours"))

    resilience_status = str(resilience.get("status", "")).lower()
    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)):
        if resilience_score < 55:
            _penalise(18, "Operational resilience is degraded and prolongs recovery.")
        elif resilience_score < 70:
            _penalise(10, "Operational resilience remains vulnerable during recovery.")
        elif resilience_score >= 82:
            _reward("Resilience measures reinforce the recovery roadmap.")
    elif resilience_status in {"critical", "vulnerable"}:
        _penalise(12, "Operational resilience status is stressed.")

    _collect_actions(resilience.get("recommended_actions"), stabilise=True)
    _collect_drivers(resilience.get("drivers"))
    _collect_watch(resilience.get("weak_spots"))
    _collect_watch(resilience.get("reinforcing_factors"))
    _register_window(resilience.get("stability_window_hours"))

    assurance_status = str(assurance.get("status", "")).lower()
    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)):
        if assurance_score < 55:
            _penalise(18, "Mission assurance blockers threaten recovery cadence.")
        elif assurance_score < 70:
            _penalise(12, "Mission assurance remains at risk.")
        elif assurance_score >= 85:
            _reward("Mission assurance is reinforcing the recovery path.")
    elif assurance_status in {"critical", "at_risk"}:
        _penalise(12, "Mission assurance status requires recovery oversight.")

    _collect_actions(assurance.get("recommended_actions"), stabilise=True)
    _collect_drivers(assurance.get("drivers"))
    _collect_drivers(assurance.get("focus_areas"))
    _collect_dependencies(assurance.get("blockers"))
    _register_window(assurance.get("next_checkpoint_hours"))

    sustain_status = str(sustainment.get("status", "")).lower()
    if sustain_status == "surge":
        _penalise(14, "Resource sustainment is in surge mode.")
    elif sustain_status == "accelerate":
        _penalise(10, "Resource sustainment must accelerate to meet recovery goals.")
    elif sustain_status == "reinforce":
        _penalise(6, "Resource sustainment requires reinforcement for recovery.")
    elif sustain_status in {"monitor", "steady"}:
        _reward("Resource sustainment is steady.")

    _collect_actions(sustainment.get("recommended_actions"))
    _collect_dependencies(sustainment.get("resource_needs"))
    _collect_drivers(sustainment.get("resource_needs"))
    allocation_plan = sustainment.get("allocation_plan")
    if isinstance(allocation_plan, list):
        _collect_dependencies(allocation_plan)
    _register_window(sustainment.get("resupply_window_hours"))

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status == "misaligned":
        _penalise(12, "Command alignment is misaligned and slows recovery integration.")
    elif alignment_status == "at_risk":
        _penalise(8, "Command alignment is at risk during recovery.")
    elif alignment_status == "aligned":
        _reward("Command alignment supports unified recovery tasks.")

    _collect_actions(alignment.get("recommended_actions"))
    _collect_drivers(alignment.get("drivers"))
    _collect_drivers(alignment.get("focus_areas"))
    _collect_dependencies(alignment.get("coordination_gaps"))
    _register_window(alignment.get("next_sync_hours"))

    directive_status = str(directives.get("status", "")).lower()
    if directive_status == "escalate":
        _penalise(10, "Command directives escalated for recovery.")
    elif directive_status in {"accelerate", "focus"}:
        _penalise(6, "Command directives prioritise recovery tracks.")
    elif directive_status == "monitor":
        _reward("Command directives remain steady.")

    _collect_actions(directives.get("recommended_actions"))
    _collect_drivers(directives.get("coordination_teams"))
    _collect_drivers(directives.get("focus_areas"))
    _register_window(directives.get("planning_window_hours"))

    support_status = str(support.get("status", "")).lower()
    if support_status == "mobilise":
        _penalise(8, "Support teams are mobilising to recover operations.")
    elif support_status == "reinforce":
        _penalise(6, "Support teams are reinforcing recovery tracks.")
    elif support_status == "monitor":
        _reward("Support teams remain on monitor posture.")

    _collect_actions(support.get("recommended_actions"))
    priorities = support.get("priorities")
    if isinstance(priorities, list):
        for entry in priorities:
            if not isinstance(entry, dict):
                continue
            reason = entry.get("reason")
            team = entry.get("team")
            if reason:
                dependencies.append(str(reason))
            if team:
                drivers.append(str(team))
            _register_window(entry.get("support_window_hours"))

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level == "critical":
        _penalise(12, "Response readiness is critical during recovery.")
    elif readiness_level == "strained":
        _penalise(8, "Response readiness is strained and needs support.")
    elif readiness_level in {"steady", "reinforced"}:
        _reward("Response readiness provides steady coverage.")

    _collect_actions(readiness.get("priority_actions"), stabilise=True)
    _collect_drivers(readiness.get("drivers"))
    _register_window(readiness.get("support_window_hours"))

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "prediction_gap"}:
        _penalise(12, "Analyst pressure is critical and slows recovery decisions.")
    elif pressure_status in {"backlog", "feedback_strain", "quality_watch"}:
        _penalise(8, "Analyst pressure is elevated during recovery.")
    elif pressure_status == "balanced":
        _reward("Analyst throughput is balanced.")

    _collect_actions(pressure.get("recommended_actions"))
    _collect_drivers(pressure.get("drivers"))
    _register_window(pressure.get("estimated_clearance_hours"))

    escalation_status = str(escalation.get("status", "")).lower()
    if escalation_status == "escalate":
        _penalise(10, "Escalation posture is triggered during recovery.")
    elif escalation_status == "prepare":
        _penalise(6, "Escalation posture is preparing, tightening recovery horizon.")
    elif escalation_status in {"monitor", "standby"}:
        _reward("Escalation posture remains stable.")

    _collect_actions(escalation.get("recommended_actions"))
    _collect_dependencies(escalation.get("escalation_pathways"))
    _collect_watch(escalation.get("escalation_signals"))
    _collect_watch(escalation.get("watch_items"))
    _collect_drivers(escalation.get("drivers"))
    _collect_drivers(escalation.get("stability_factors"))
    _register_window(escalation.get("next_review_hours"))

    outlook_status = str(outlook.get("status", "")).lower()
    if outlook_status == "escalation_imminent":
        _penalise(8, "Operational outlook flags imminent escalation during recovery.")
    elif outlook_status == "rapid_response":
        _penalise(6, "Operational outlook demands rapid response in recovery plan.")
    elif outlook_status in {"stabilise", "steady_watch"}:
        _reward("Operational outlook supports stabilisation.")

    _collect_actions(outlook.get("recommended_actions"))
    _collect_drivers(outlook.get("drivers"))
    _collect_drivers(outlook.get("focus_areas"))
    _register_window(outlook.get("planning_horizon_hours"))

    risk_score = risks.get("severity_score")
    if isinstance(risk_score, (float, int)):
        if risk_score >= 18:
            _penalise(12, "Operational risk register reports critical items.")
        elif risk_score >= 12:
            _penalise(8, "Operational risk register is elevated.")
        elif risk_score <= 3:
            _reward("Operational risk register remains contained.")

    _collect_actions(risks.get("recommended_actions"))
    _collect_drivers(risks.get("focus_areas"))
    _collect_watch(risks.get("continuity_risks"))
    _register_window(risks.get("next_review_hours"))

    contingency_status = str(contingency.get("status", "")).lower()
    if contingency_status == "activate":
        _penalise(8, "Contingency plans near activation and influence recovery.")
    elif contingency_status == "ready":
        _penalise(5, "Contingency plans are ready and require coordination.")
    elif contingency_status in {"watch", "steady"}:
        _reward("Contingency planning remains on watch.")

    _collect_actions(contingency.get("recommended_actions"))
    _collect_drivers(
        entry.get("name")
        for entry in contingency.get("scenarios", [])
        if isinstance(entry, dict) and entry.get("name")
    )
    _collect_watch(contingency.get("watch_items"))
    _register_window(contingency.get("activation_window_hours"))

    communication_status = str(communication.get("status", "")).lower()
    if communication_status in {"crisis", "escalated"}:
        _penalise(6, "Communication cadence is escalated for recovery operations.")
    elif communication_status in {"reinforce", "heightened"}:
        _penalise(4, "Communication cadence is heightened during recovery.")
    elif communication_status in {"steady", "routine", "focused"}:
        _reward("Communication cadence is steady and supporting recovery.")

    _collect_actions(communication.get("recommended_actions"))
    _collect_drivers(communication.get("key_messages"))
    audiences = communication.get("audiences")
    if isinstance(audiences, list):
        for entry in audiences:
            if isinstance(entry, dict):
                _collect_drivers([entry.get("focus")])
    _register_window(communication.get("update_cadence_minutes"))

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(6, "Intelligence confidence is low and slows recovery.")
    elif confidence_level == "guarded":
        _penalise(4, "Intelligence confidence is guarded.")
    elif confidence_level == "high":
        _reward("Intelligence confidence supports decisive recovery actions.")

    _collect_actions(confidence.get("recommended_actions"))
    _collect_drivers(confidence.get("drivers"))

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for name, info in (feeds or {}).items():
        if not isinstance(info, dict):
            continue
        status = str(info.get("status", "")).lower()
        label = f"{str(name).capitalize()} feed"
        if status == "stale":
            _penalise(8, f"{label} is stale and blocking recovery decisions.")
        elif status == "warning":
            _penalise(4, f"{label} is nearing stale thresholds.")
        elif status == "fresh":
            _reward(f"{label} remains fresh for recovery planning.")

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity = str(gap.get("severity", "")).lower()
        detail = str(gap.get("detail", "")).strip() or str(gap.get("gap", ""))
        if severity == "critical":
            _penalise(8, f"Critical intelligence gap: {detail}.")
            watch_items.append(f"Critical gap: {detail}")
        elif severity == "major":
            _penalise(5, f"Major intelligence gap: {detail}.")
        elif severity:
            _penalise(3)

    continuity_focus = None
    constraints = continuity.get("primary_constraints")
    if isinstance(constraints, list) and constraints:
        continuity_focus = str(constraints[0])
    elif continuity.get("drivers"):
        continuity_focus = str(next(iter(continuity.get("drivers")), ""))

    resource_focus = None
    needs = sustainment.get("resource_needs")
    if isinstance(needs, list) and needs:
        resource_focus = str(needs[0])
    elif isinstance(priorities, list):
        for entry in priorities:
            if isinstance(entry, dict) and entry.get("reason"):
                resource_focus = str(entry["reason"])
                break

    command_focus = None
    coordination_gaps = alignment.get("coordination_gaps")
    if isinstance(coordination_gaps, list) and coordination_gaps:
        command_focus = str(coordination_gaps[0])
    elif directives.get("focus_areas"):
        command_focus = str(next(iter(directives.get("focus_areas")), ""))
    elif communication.get("key_messages"):
        command_focus = str(next(iter(communication.get("key_messages")), ""))

    _build_track(
        "Continuity stabilisation",
        status=continuity_status or resilience_status,
        owner="Operations Coordination",
        focus=continuity_focus or "Stabilise core services",
        action_candidates=(
            (continuity.get("recommended_actions") or [])
            + (resilience.get("recommended_actions") or [])
            + (assurance.get("recommended_actions") or [])
        ),
    )

    _build_track(
        "Resource reinforcement",
        status=sustain_status or support_status or readiness_level,
        owner="Support & Logistics",
        focus=resource_focus or "Reinforce recovery staffing",
        action_candidates=(
            (sustainment.get("recommended_actions") or [])
            + (support.get("recommended_actions") or [])
            + (readiness.get("priority_actions") or [])
            + (pressure.get("recommended_actions") or [])
        ),
    )

    _build_track(
        "Command synchronisation",
        status=alignment_status or directive_status or escalation_status,
        owner="Command Integration",
        focus=command_focus or "Synchronise directives and communications",
        action_candidates=(
            (directives.get("recommended_actions") or [])
            + (alignment.get("recommended_actions") or [])
            + (communication.get("recommended_actions") or [])
            + (escalation.get("recommended_actions") or [])
        ),
    )

    dependencies = list(dict.fromkeys(filter(None, dependencies)))
    actions = list(dict.fromkeys(filter(None, actions)))
    stabilisation = list(dict.fromkeys(filter(None, stabilisation)))
    drivers = list(dict.fromkeys(filter(None, drivers)))
    momentum = list(dict.fromkeys(filter(None, momentum)))
    watch_items = list(dict.fromkeys(filter(None, watch_items)))
    windows = [value for value in windows if isinstance(value, (float, int)) and value > 0]

    recovery_score = int(round(score))
    if recovery_score >= 85:
        status = "sustain"
    elif recovery_score >= 70:
        status = "stabilise"
    elif recovery_score >= 55:
        status = "recover"
    else:
        status = "rebuild"

    phase_map = {
        "sustain": "stability",
        "stabilise": "stabilisation",
        "recover": "recovery",
        "rebuild": "reconstitution",
    }

    payload: Dict[str, Any] = {
        "status": status,
        "recovery_score": recovery_score,
        "recovery_phase": phase_map.get(status),
    }
    if dependencies:
        payload["critical_dependencies"] = dependencies
    if actions:
        payload["recommended_actions"] = actions
    if stabilisation:
        payload["stabilisation_actions"] = stabilisation[:5]
    if drivers:
        payload["insight_drivers"] = drivers
    if momentum:
        payload["momentum_factors"] = momentum
    if watch_items:
        payload["watch_items"] = watch_items
    if windows:
        payload["recovery_window_hours"] = min(windows)
    if tracks:
        payload["recovery_tracks"] = tracks

    return payload


def _derive_operational_transformation(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Derive a transformation roadmap that links recovery to long-term gains."""

    recovery = brief.get("operational_recovery") or {}
    continuity = brief.get("operational_continuity") or {}
    resilience = brief.get("operational_resilience") or {}
    assurance = brief.get("mission_assurance") or {}
    sustainment = brief.get("resource_sustainment") or {}
    alignment = brief.get("command_alignment") or {}
    directives = brief.get("command_directives") or {}
    support = brief.get("support_priorities") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    outlook = brief.get("operational_outlook") or {}
    risks = brief.get("operational_risks") or {}
    communication = brief.get("communication_plan") or {}
    contingency = brief.get("contingency_plans") or {}
    confidence = brief.get("intelligence_confidence") or {}
    health = brief.get("health") or {}

    if not any(
        [
            recovery,
            continuity,
            resilience,
            assurance,
            sustainment,
            alignment,
            directives,
            support,
            readiness,
            pressure,
            outlook,
            risks,
            communication,
            contingency,
            confidence,
            health,
        ]
    ):
        return None

    score = 100.0
    enablers: List[str] = []
    constraints: List[str] = []
    quick_wins: List[str] = []
    initiatives: List[str] = []
    watch_items: List[str] = []
    focus_areas: List[str] = []
    metrics: List[str] = []
    actions: List[str] = []
    tracks: List[Dict[str, Any]] = []
    review_windows: List[float] = []
    stage_markers: List[str] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = max(0.0, score - float(amount))
        if note:
            constraints.append(str(note))

    def _reward(message: Optional[str]) -> None:
        if message:
            enablers.append(str(message))

    def _collect_actions(values: Optional[Iterable[Any]], *, bucket: str) -> None:
        for value in values or []:
            if not value:
                continue
            text = str(value)
            actions.append(text)
            if bucket == "quick":
                quick_wins.append(text)
            elif bucket == "horizon":
                initiatives.append(text)

    def _collect_focus(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                focus_areas.append(str(value))

    def _collect_watch(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                watch_items.append(str(value))

    def _collect_metrics(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                metrics.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            review_windows.append(round(float(value), 2))

    def _register_track(
        name: Optional[str],
        *,
        status: Optional[str] = None,
        owner: Optional[str] = None,
        focus: Optional[str] = None,
        actions: Optional[Iterable[Any]] = None,
    ) -> None:
        if not name:
            return
        entry: Dict[str, Any] = {"name": str(name)}
        if status:
            entry["status"] = str(status)
        if owner:
            entry["owner"] = str(owner)
        if focus:
            entry["focus"] = str(focus)
        steps: List[str] = []
        for value in actions or []:
            if value:
                steps.append(str(value))
        if steps:
            entry["actions"] = list(dict.fromkeys(steps))[:5]
        tracks.append(entry)

    recovery_status = str(recovery.get("status", "")).lower()
    if recovery_status:
        stage_markers.append(recovery_status)
    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)):
        if recovery_score >= 85:
            _reward("Recovery programme is sustaining momentum.")
        elif recovery_score >= 70:
            _reward("Recovery efforts are stabilising core services.")
        elif recovery_score >= 55:
            _penalise(8, "Recovery is still rebuilding priority services.")
        else:
            _penalise(18, "Recovery score remains in reconstitution range.")
    _collect_actions(recovery.get("stabilisation_actions"), bucket="quick")
    _collect_actions(recovery.get("recommended_actions"), bucket="horizon")
    _collect_focus(
        [
            track.get("focus")
            for track in recovery.get("recovery_tracks", [])
            if isinstance(track, dict)
        ]
    )
    for track in recovery.get("recovery_tracks", []) or []:
        if isinstance(track, dict):
            _register_track(
                track.get("name"),
                status=track.get("status"),
                owner=track.get("owner"),
                focus=track.get("focus"),
                actions=track.get("actions"),
            )
    _collect_watch(recovery.get("watch_items"))
    _collect_metrics(recovery.get("momentum_factors"))
    _collect_metrics(recovery.get("insight_drivers"))
    _collect_watch(recovery.get("critical_dependencies"))
    for dependency in recovery.get("critical_dependencies", []) or []:
        if dependency:
            constraints.append(str(dependency))
    _register_window(recovery.get("recovery_window_hours"))

    continuity_status = str(continuity.get("status", "")).lower()
    if continuity_status in {"strained", "critical"}:
        _penalise(10, "Continuity posture is strained and threatens long-term plans.")
    elif continuity_status in {"stabilise", "steady"}:
        _reward("Continuity plan is holding steady for transformation work.")
    _collect_actions(continuity.get("recommended_actions"), bucket="horizon")
    primary_constraints = continuity.get("primary_constraints")
    _collect_focus(primary_constraints)
    for constraint in primary_constraints or []:
        if constraint:
            constraints.append(str(constraint))
    _collect_watch(continuity.get("watch_items"))
    _collect_metrics(continuity.get("drivers"))
    _register_window(continuity.get("continuity_horizon_hours"))

    resilience_status = str(resilience.get("status", "")).lower()
    if resilience_status in {"vulnerable", "degraded"}:
        _penalise(12, "Resilience posture is vulnerable during transformation.")
    elif resilience_status in {"reinforced", "resilient"}:
        _reward("Resilience factors are reinforcing transformation pacing.")
    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)) and resilience_score < 60:
        _penalise(6, "Resilience score is below target for sustained change.")
    _collect_actions(resilience.get("recommended_actions"), bucket="horizon")
    _collect_metrics(resilience.get("reinforcing_factors"))
    _collect_focus(resilience.get("weak_spots"))
    _register_window(resilience.get("stability_window_hours"))

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status in {"at_risk", "critical"}:
        _penalise(10, "Mission assurance blockers are slowing transformation.")
    elif assurance_status in {"secure", "steady"}:
        _reward("Mission assurance is supporting transformation focus.")
    _collect_actions(assurance.get("recommended_actions"), bucket="horizon")
    _collect_focus(assurance.get("focus_areas"))
    _collect_watch(assurance.get("blockers"))
    _collect_metrics(assurance.get("drivers"))
    _register_window(assurance.get("next_checkpoint_hours"))

    sustain_status = str(sustainment.get("status", "")).lower()
    if sustain_status in {"surge", "accelerate"}:
        _penalise(8, "Sustainment posture is consuming reserves during change.")
    elif sustain_status in {"reinforce", "steady"}:
        _reward("Sustainment is reinforcing transformation pacing.")
    _collect_actions(sustainment.get("recommended_actions"), bucket="quick")
    _collect_focus(sustainment.get("resource_needs"))
    _register_window(sustainment.get("resupply_window_hours"))
    for allocation in sustainment.get("allocation_plan", []) or []:
        if isinstance(allocation, dict):
            _register_track(
                allocation.get("resource") or allocation.get("team"),
                status=allocation.get("status"),
                owner=allocation.get("owner") or allocation.get("team"),
                focus=allocation.get("focus"),
                actions=[allocation.get("detail"), allocation.get("action")],
            )

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status in {"escalate", "accelerate"}:
        _penalise(9, "Command alignment gaps are delaying transformation syncs.")
    elif alignment_status in {"focus", "monitor"}:
        _reward("Alignment cadence is supporting transformation threads.")
    _collect_actions(alignment.get("recommended_actions"), bucket="quick")
    _collect_focus(alignment.get("focus_areas"))
    _collect_watch(alignment.get("coordination_gaps"))
    _register_window(alignment.get("next_sync_hours"))

    directive_status = str(directives.get("status", "")).lower()
    if directive_status == "escalate":
        _penalise(14, "Directive queue is escalated and blocking transformation bandwidth.")
    elif directive_status == "accelerate":
        _penalise(7, "Directive queue is accelerating execution focus.")
    directive_severity = directives.get("severity")
    if isinstance(directive_severity, (float, int)) and directive_severity >= 12:
        _penalise(5, "Directive severity is high during transformation.")
    _collect_actions(directives.get("recommended_actions"), bucket="quick")
    _collect_focus(directives.get("focus_areas"))
    _collect_metrics(directives.get("coordination_teams"))
    _register_window(directives.get("planning_window_hours"))

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "reinforce"}:
        _penalise(6, "Support teams are stretched while transformation runs.")
    _collect_actions(support.get("recommended_actions"), bucket="quick")
    for entry in support.get("priorities", []) or []:
        if not isinstance(entry, dict):
            continue
        _collect_focus([entry.get("team"), entry.get("reason"), entry.get("focus")])
        _collect_watch([entry.get("reason")])
        _register_window(entry.get("support_window_hours"))
        _register_track(
            entry.get("team") or entry.get("name") or entry.get("focus"),
            status=entry.get("status"),
            owner=entry.get("owner") or entry.get("team"),
            focus=entry.get("focus") or entry.get("reason"),
            actions=[entry.get("follow_up"), entry.get("recommended_action"), entry.get("action")],
        )

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level in {"critical", "strained"}:
        _penalise(12, "Response readiness is strained and needs reinforcement.")
    elif readiness_level in {"steady", "ready"}:
        _reward("Response readiness can support transformation change.")
    _collect_actions(readiness.get("priority_actions"), bucket="quick")
    _collect_watch(readiness.get("drivers"))
    _register_window(readiness.get("support_window_hours"))

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "prediction_gap"}:
        _penalise(12, "Analyst pressure is slowing strategic transformation.")
    elif pressure_status in {"backlog", "feedback_strain", "quality_watch"}:
        _penalise(6, "Analyst pressure needs attention during change.")
    _collect_actions(pressure.get("recommended_actions"), bucket="quick")
    _collect_watch(pressure.get("drivers"))
    _register_window(pressure.get("estimated_clearance_hours"))

    outlook_score = outlook.get("severity_score")
    if isinstance(outlook_score, (float, int)) and outlook_score >= 12:
        _penalise(8, "Operational outlook is elevated and constraining options.")
    outlook_status = str(outlook.get("status", "")).lower()
    if outlook_status:
        stage_markers.append(outlook_status)
    _collect_actions(outlook.get("recommended_actions"), bucket="horizon")
    _collect_focus(outlook.get("focus_areas"))
    _collect_metrics(outlook.get("drivers"))
    _register_window(outlook.get("planning_horizon_hours"))

    risk_score = risks.get("severity_score")
    if isinstance(risk_score, (float, int)):
        if risk_score >= 18:
            _penalise(16, "Operational risk register is critical for transformation.")
        elif risk_score >= 12:
            _penalise(10, "Operational risk register is escalated and needs owners.")
        elif risk_score >= 6:
            _penalise(5, "Operational risk register remains elevated.")
    _collect_actions(risks.get("recommended_actions"), bucket="horizon")
    _collect_focus(risks.get("focus_areas"))
    for entry in risks.get("risks", []) or []:
        if isinstance(entry, dict):
            _collect_watch([entry.get("name"), entry.get("detail"), entry.get("drivers")])
    _register_window(risks.get("next_review_hours"))

    comm_status = str(communication.get("status", "")).lower()
    if comm_status in {"escalated", "heightened"}:
        _penalise(6, "Communication cadence is consuming leadership bandwidth.")
    _collect_actions(communication.get("recommended_actions"), bucket="quick")
    _collect_focus(communication.get("key_messages"))
    _collect_focus([entry.get("focus") for entry in communication.get("audiences", []) if isinstance(entry, dict)])
    _register_window(
        (communication.get("update_cadence_minutes") or 0) / 60.0
        if isinstance(communication.get("update_cadence_minutes"), (float, int))
        else None
    )

    contingency_status = str(contingency.get("status", "")).lower()
    if contingency_status in {"activate", "prepare"}:
        _penalise(5, "Contingency planning is drawing focus during transformation.")
    _collect_actions(contingency.get("recommended_actions"), bucket="horizon")
    for scenario in contingency.get("scenarios", []) or []:
        if isinstance(scenario, dict):
            _collect_watch([scenario.get("name")])
            _collect_focus([scenario.get("focus"), scenario.get("category")])
    _collect_watch(contingency.get("watch_items"))
    _register_window(contingency.get("activation_window_hours"))

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level in {"low", "guarded"}:
        _penalise(6, "Telemetry confidence is guarded and slowing automation.")
    elif confidence_level in {"steady", "high"}:
        _reward("Telemetry confidence is supporting transformation.")
    _collect_actions(confidence.get("recommended_actions"), bucket="horizon")
    _collect_watch(confidence.get("drivers"))

    health_status = str(health.get("risk_level", "")).lower()
    if health_status in {"critical", "high"}:
        _penalise(8, "Overall health score is high risk during transformation.")
    _collect_actions(health.get("recommended_actions"), bucket="quick")
    _collect_metrics(health.get("reinforcing_factors"))

    enablers = list(dict.fromkeys(filter(None, enablers)))
    constraints = list(dict.fromkeys(filter(None, constraints)))
    quick_wins = list(dict.fromkeys(filter(None, quick_wins)))
    initiatives = list(dict.fromkeys(filter(None, initiatives)))
    watch_items = list(dict.fromkeys(filter(None, watch_items)))
    focus_areas = list(dict.fromkeys(filter(None, focus_areas)))
    metrics = list(dict.fromkeys(filter(None, metrics)))
    actions = list(dict.fromkeys(filter(None, actions)))
    review_windows = [value for value in review_windows if isinstance(value, (float, int)) and value > 0]

    deduped_tracks: List[Dict[str, Any]] = []
    seen_names: set[str] = set()
    for track in tracks:
        name = track.get("name")
        key = str(name).lower()
        if not name or key in seen_names:
            continue
        seen_names.add(key)
        deduped_tracks.append(track)

    final_score = int(round(score))
    if final_score >= 85:
        status = "advancing"
    elif final_score >= 70:
        status = "progressing"
    elif final_score >= 55:
        status = "watch"
    else:
        status = "intervene"

    maturity = "stabilisation"
    if "sustain" in stage_markers and final_score >= 80:
        maturity = "optimisation"
    elif "stabilise" in stage_markers and final_score >= 65:
        maturity = "integration"
    elif "recover" in stage_markers and final_score >= 55:
        maturity = "recovery_bridge"
    elif final_score < 55:
        maturity = "reset"

    payload: Dict[str, Any] = {
        "status": status,
        "transformation_score": final_score,
    }
    if maturity:
        payload["maturity_stage"] = maturity
    if deduped_tracks:
        payload["focus_tracks"] = deduped_tracks
    if quick_wins:
        payload["quick_wins"] = quick_wins[:8]
    if initiatives:
        payload["long_horizon_initiatives"] = initiatives[:8]
    if enablers:
        payload["enablers"] = enablers[:8]
    if constraints:
        payload["constraints"] = constraints[:10]
    if watch_items:
        payload["watch_indicators"] = watch_items[:10]
    if metrics:
        payload["metrics_to_watch"] = metrics[:8]
    if focus_areas:
        payload["transformation_focus"] = focus_areas[:8]
    if actions:
        payload["recommended_actions"] = actions[:10]
    if review_windows:
        payload["next_review_hours"] = min(review_windows)

    return payload if payload else None


def _derive_frontline_support(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fuse sustainment telemetry into a frontline support posture."""

    sustainment = brief.get("resource_sustainment") or {}
    support = brief.get("support_priorities") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    continuity = brief.get("operational_continuity") or {}
    resilience = brief.get("operational_resilience") or {}
    recovery = brief.get("operational_recovery") or {}
    outlook = brief.get("operational_outlook") or {}
    risks = brief.get("operational_risks") or {}
    assurance = brief.get("mission_assurance") or {}
    alignment = brief.get("command_alignment") or {}
    transformation = brief.get("operational_transformation") or {}
    freshness = brief.get("data_freshness") or {}
    detection_quality = brief.get("detection_quality") or {}
    gaps = brief.get("intelligence_gaps") or []
    meta = brief.get("meta") or {}
    activity = brief.get("activity_summary") or {}

    if not any(
        [
            sustainment,
            support,
            readiness,
            pressure,
            continuity,
            resilience,
            recovery,
            outlook,
            risks,
            assurance,
            alignment,
            transformation,
            freshness,
            detection_quality,
            gaps,
            meta,
            activity,
        ]
    ):
        return None

    score = 92.0
    severity = 0
    drivers: List[str] = []
    signals: List[str] = []
    actions: List[str] = []
    corridors: List[str] = []
    priority_units: List[str] = []
    brigade_support: List[Dict[str, Any]] = []
    operator_notes: List[str] = []
    windows: List[float] = []

    def _penalise(amount: float, driver: Optional[str] = None, *, signal: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(amount)
        score = max(0.0, score - float(amount) * 1.5)
        if driver:
            drivers.append(driver)
        if signal:
            signals.append(signal)

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(float(value))

    def _extend_actions(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                actions.append(str(value))

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "critical"}:
        _penalise(
            10,
            "Support priorities call for immediate mobilisation to sustain frontline brigades.",
            signal="Support cell requests mobilisation",
        )
        operator_notes.append(
            "Забезпечте оперативне підсилення для бригад, які запросили термінову допомогу."
        )
    elif support_status in {"reinforce", "accelerate"}:
        _penalise(
            6,
            "Support queues indicate reinforcement is required across engaged units.",
            signal="Support cadence elevated",
        )
    elif support_status in {"watch"}:
        _penalise(2, "Support teams report emerging needs to monitor.")
    _extend_actions(support.get("recommended_actions"))

    for priority in support.get("priorities", []) or []:
        if not isinstance(priority, dict):
            continue
        name = priority.get("name")
        focus = priority.get("focus")
        window = priority.get("support_window_hours")
        if name:
            priority_units.append(str(name))
        descriptor = str(name or focus or "Support focus")
        if isinstance(window, (float, int)):
            corridors.append(f"{descriptor} ({float(window):.1f}h)")
            _register_window(float(window))
        elif focus:
            corridors.append(descriptor)
        if focus and focus not in priority_units:
            priority_units.append(str(focus))

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "mobilise"}:
        _penalise(
            9,
            "Sustainment plan is in surge posture and risks frontline shortfalls.",
            signal="Sustainment surge declared",
        )
        operator_notes.append(
            "Виведіть резервні колони забезпечення на визначені логістичні коридори."
        )
    elif sustainment_status in {"accelerate", "reinforce"}:
        _penalise(5, "Sustainment posture requires reinforcement to stabilise supply lines.")
    elif sustainment_status in {"watch"}:
        _penalise(2, "Sustainment metrics signal elevated monitoring requirements.")

    _extend_actions(sustainment.get("recommended_actions"))

    for entry in sustainment.get("allocation_plan", []) or []:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        focus = entry.get("focus")
        priority = entry.get("priority")
        quantity = entry.get("quantity")
        window = entry.get("window_hours")
        if isinstance(window, (float, int)):
            _register_window(float(window))
        if focus and focus not in priority_units:
            priority_units.append(str(focus))
        support_entry: Dict[str, Any] = {
            "unit": str(focus or resource or "Support element"),
            "resource": str(resource or focus or "Support"),
        }
        if priority:
            support_entry["priority"] = str(priority)
        if isinstance(quantity, (float, int)) and quantity > 0:
            support_entry["quantity"] = int(math.ceil(float(quantity)))
        if isinstance(window, (float, int)) and window > 0:
            support_entry["window_hours"] = round(float(window), 2)
        brigade_support.append(support_entry)

    readiness_level = str(readiness.get("level", "")).lower()
    readiness_window = readiness.get("support_window_hours")
    _register_window(readiness_window if isinstance(readiness_window, (float, int)) else None)
    if readiness_level == "critical":
        _penalise(
            8,
            "Response readiness is critical, limiting coverage for Ukrainian formations.",
            signal="Readiness at critical levels",
        )
        operator_notes.append("Негайно посильте чергові зміни та відновіть ротації операторів.")
    elif readiness_level == "strained":
        _penalise(5, "Response readiness is strained and needs reinforcement.")
    elif readiness_level == "watch":
        _penalise(2, "Readiness indicators are trending down and require monitoring.")
    _extend_actions(readiness.get("priority_actions"))

    pressure_status = str(pressure.get("status", "")).lower()
    clearance = pressure.get("estimated_clearance_hours")
    _register_window(clearance if isinstance(clearance, (float, int)) else None)
    if pressure_status == "critical_backlog":
        _penalise(
            8,
            "Analyst pressure indicates a critical backlog impacting targeting cycles.",
            signal="Backlog blocking targeting",
        )
    elif pressure_status in {"backlog", "prediction_gap"}:
        _penalise(5, "Analyst queues are delaying response options for supported brigades.")
    elif pressure_status in {"prediction_gap_watch", "quality_watch"}:
        _penalise(3, "Pressure metrics highlight prediction coverage strain.")

    continuity_status = str(continuity.get("status", "")).lower()
    if continuity_status in {"constrained", "degraded"}:
        _penalise(5, "Operational continuity is constrained across priority corridors.")
    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)) and continuity_score < 55:
        _penalise(3, "Continuity score is below 55 indicating fragile sustainment routes.")

    resilience_status = str(resilience.get("status", "")).lower()
    if resilience_status in {"fragile", "stressed"}:
        _penalise(4, "Operational resilience is fragile and requires reinforcing logistics.")
    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)) and resilience_score < 60:
        _penalise(2, "Resilience score is sliding below 60 across frontline support.")

    recovery_status = str(recovery.get("status", "")).lower()
    if recovery_status in {"stalled", "recover"}:
        _penalise(3, "Recovery tracks are still stabilising, limiting sustainment capacity.")

    outlook_severity = outlook.get("severity")
    if isinstance(outlook_severity, (float, int)) and outlook_severity >= 70:
        _penalise(4, "Operational outlook severity is elevated for frontline sectors.")

    risk_score = risks.get("severity_score")
    if isinstance(risk_score, (float, int)):
        if risk_score >= 90:
            _penalise(6, "Risk register flags critical sustainment blockers.")
        elif risk_score >= 75:
            _penalise(4, "Risk register highlights major sustainment threats.")

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status in {"strained", "critical"}:
        _penalise(4, "Mission assurance is strained, signalling leadership focus on logistics.")

    alignment_score = alignment.get("alignment_score")
    if isinstance(alignment_score, (float, int)) and alignment_score < 60:
        _penalise(3, "Command alignment is lagging on sustainment priorities.")

    transform_score = transformation.get("transformation_score")
    if isinstance(transform_score, (float, int)) and transform_score < 60:
        _penalise(2, "Transformation programme needs reinforcement around support modernisation.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else None
    if isinstance(feeds, dict):
        for name, info in feeds.items():
            status = str(info.get("status", "")).lower()
            if status == "stale":
                _penalise(4, f"{name.title()} feed is stale and threatens targeting responsiveness.")
            elif status == "warning":
                _penalise(2, f"{name.title()} feed is ageing and should be refreshed.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.65:
        _penalise(3, "Detection confidence is below 0.65, raising doubts around fires requests.")

    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        severity_label = str(gap.get("severity", "")).lower()
        description = gap.get("description") or gap.get("name")
        if severity_label == "critical":
            _penalise(5, f"Critical intelligence gap: {description or 'Unspecified'}")
        elif severity_label in {"major", "high"}:
            _penalise(3, f"Major intelligence gap: {description or 'Unspecified'}")

    detection_counts = meta.get("detections") if isinstance(meta, dict) else None
    if isinstance(detection_counts, dict) and detection_counts:
        total = 0
        for stats in detection_counts.values():
            count = stats.get("count") if isinstance(stats, dict) else None
            if isinstance(count, (int, float)):
                total += int(count)
        if total <= 2:
            _penalise(2, "Minimal detections in window reduce confidence for frontline tasking.")

    tempo = str(activity.get("tempo", "")).lower()
    if tempo == "surge":
        _penalise(3, "Operational tempo is surging on frontline sectors.")
    elif tempo == "elevated":
        _penalise(2, "Operational tempo remains elevated for engaged brigades.")

    actions.extend(
        [
            "Coordinate with Ukrainian Joint Forces logistics cell to accelerate brigade resupply.",
            "Pair operational planners with sustainment officers to lock in convoy windows.",
        ]
    )

    operator_notes.append(
        "Використовуйте наявні вогневі та БПЛА-ресурси пріоритетно на напрямках з найвищим тиском."
    )

    def _dedupe_strings(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            if not value:
                continue
            if value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

    priority_units = _dedupe_strings(priority_units)
    corridors = _dedupe_strings(corridors)
    drivers = _dedupe_strings(drivers)
    signals = _dedupe_strings(signals)
    actions = _dedupe_strings(actions)
    operator_notes = _dedupe_strings(operator_notes)

    unique_support: List[Dict[str, Any]] = []
    seen_support = set()
    for entry in brigade_support:
        key = (
            entry.get("unit"),
            entry.get("resource"),
            entry.get("priority"),
            entry.get("window_hours"),
        )
        if key in seen_support:
            continue
        seen_support.add(key)
        unique_support.append(entry)
    brigade_support = unique_support

    coordination_window: Optional[float] = None
    positive_windows = [value for value in windows if value > 0]
    if positive_windows:
        coordination_window = round(min(positive_windows), 2)

    status = "steady"
    if severity >= 24:
        status = "critical"
    elif severity >= 15:
        status = "mobilise"
    elif severity >= 8:
        status = "reinforce"
    elif severity >= 3:
        status = "watch"

    payload: Dict[str, Any] = {
        "status": status,
        "support_score": int(round(score)) if score is not None else None,
    }
    if coordination_window is not None:
        payload["coordination_window_hours"] = coordination_window
    if priority_units:
        payload["priority_units"] = priority_units
    if corridors:
        payload["support_corridors"] = corridors
    if brigade_support:
        payload["brigade_support"] = brigade_support
    if drivers:
        payload["drivers"] = drivers
    if signals:
        payload["signals"] = signals
    if actions:
        payload["recommended_actions"] = actions
    if operator_notes:
        payload["ukrainian_operator_notes"] = operator_notes

    return payload if payload else None


def _derive_automation_playbook(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Assemble an automation playbook for Ukrainian duty teams."""

    directives = brief.get("command_directives") or {}
    communications = brief.get("communication_plan") or {}
    governance = brief.get("operational_governance") or {}
    sustainment = brief.get("resource_sustainment") or {}
    frontline = brief.get("frontline_support") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    assurance = brief.get("mission_assurance") or {}
    transformation = brief.get("operational_transformation") or {}
    alignment = brief.get("command_alignment") or {}
    confidence = brief.get("intelligence_confidence") or {}
    detection_quality = brief.get("detection_quality") or {}
    freshness = brief.get("data_freshness") or {}
    risks = brief.get("operational_risks") or {}
    gaps = brief.get("intelligence_gaps") or []
    meta = brief.get("meta") or {}

    if not any(
        [
            directives,
            communications,
            governance,
            sustainment,
            frontline,
            readiness,
            pressure,
            support,
            resilience,
            continuity,
            recovery,
            assurance,
            transformation,
            alignment,
            confidence,
            detection_quality,
            freshness,
            risks,
            gaps,
            meta,
        ]
    ):
        return None

    score = 88.0
    severity = 0
    drivers: List[str] = []
    blockers: List[str] = []
    triggers: List[str] = []
    automation_tracks: List[str] = []
    tasks: List[Dict[str, Any]] = []
    monitoring_channels: List[str] = []
    actions: List[str] = []
    operator_prompts: List[str] = []
    windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(amount)
        score = max(0.0, score - float(amount) * 1.4)
        if note:
            blockers.append(str(note))

    def _boost(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            drivers.append(str(note))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    def _add_task(
        task: Optional[str],
        *,
        owner: Optional[str] = None,
        window: Optional[float] = None,
        mode: str = "automated",
    ) -> None:
        if not task:
            return
        entry: Dict[str, Any] = {"task": str(task), "mode": mode}
        if owner:
            entry["owner"] = str(owner)
        if isinstance(window, (float, int)) and window > 0:
            entry["window_hours"] = round(float(window), 2)
            windows.append(entry["window_hours"])
        tasks.append(entry)

    directive_status = str(directives.get("status", "")).lower()
    directive_severity = directives.get("severity")
    if directive_status in {"escalate", "accelerate"}:
        _penalise(6, "Command directives require leadership steering before automation.")
        triggers.append("Command directives escalated")
    elif directive_status in {"stabilise", "synchronise"}:
        _boost(4, "Command directives aligned around automation-friendly tracks.")
    if isinstance(directive_severity, (float, int)) and directive_severity >= 18:
        _penalise(5, "Directive severity above 18 demands manual confirmation of outputs.")

    directives_window = directives.get("planning_window_hours")
    _register_window(
        directives_window if isinstance(directives_window, (float, int)) else None
    )
    for entry in directives.get("directives", []) or []:
        if not isinstance(entry, dict):
            continue
        priority = str(entry.get("priority", "")).lower()
        action = entry.get("action")
        owner = entry.get("owner") or entry.get("team")
        window = entry.get("window_hours") or entry.get("support_window_hours")
        mode = "guided" if priority in {"immediate", "critical"} else "automated"
        _add_task(action, owner=owner, window=window, mode=mode)
        if priority in {"immediate", "critical"}:
            triggers.append(f"Directive: {action}")

    communication_status = str(communications.get("status", "")).lower()
    if communication_status in {"crisis", "accelerate"}:
        _penalise(4, "Communication cadence is in crisis mode; automation must be guarded.")
    elif communication_status in {"stabilise", "synchronise"}:
        _boost(3, "Communication plan already aligned to automation handoffs.")

    for cadence in communications.get("audience_cadence", []) or []:
        if not isinstance(cadence, dict):
            continue
        audience = cadence.get("audience")
        window = cadence.get("cadence_hours")
        if cadence.get("mode") == "manual":
            _penalise(2, f"{audience or 'Audience'} requires manual comms handoff.")
        else:
            automation_tracks.append(f"Comms: {audience or 'Audience'} cadence")
            _add_task(
                f"Push update to {audience}",
                owner=audience,
                window=window,
                mode="automated",
            )

    governance_status = str(governance.get("status", "")).lower()
    if governance_status in {"degraded", "intervene"}:
        _penalise(4, "Governance cadence degraded; automation checkpoints mandatory.")
    elif governance_status in {"steady", "stabilise"}:
        _boost(3, "Governance cadence ready to absorb autonomous execution.")

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "mobilise"}:
        _penalise(5, "Sustainment surge requires dual confirmation on logistics automations.")
        triggers.append("Sustainment surge active")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"critical", "mobilise"}:
        _penalise(6, "Frontline posture critical; automation must escalate to duty officer.")
        operator_prompts.append(
            "Підтвердіть автоматизовані рішення із черговим офіцером перед виконанням."
        )
    elif frontline_status in {"reinforce", "steady"}:
        _boost(2, "Frontline support posture steady enough for automated routines.")

    readiness_level = str(readiness.get("level", "")).lower()
    readiness_window = readiness.get("support_window_hours")
    _register_window(
        readiness_window if isinstance(readiness_window, (float, int)) else None
    )
    if readiness_level == "critical":
        _penalise(6, "Critical readiness requires human oversight of automation outcomes.")
    elif readiness_level in {"strained", "watch"}:
        _penalise(3, "Readiness constrained; automation must surface confirmation prompts.")

    pressure_status = str(pressure.get("status", "")).lower()
    clearance = pressure.get("estimated_clearance_hours")
    _register_window(clearance if isinstance(clearance, (float, int)) else None)
    if pressure_status == "critical_backlog":
        _penalise(6, "Analyst backlog critical; escalate automation of triage tasks.")
        triggers.append("Analyst backlog critical")
        automation_tracks.append("Prediction triage automation")
    elif pressure_status in {"backlog", "prediction_gap"}:
        _penalise(4, "Backlog forming; monitor automation throughput closely.")
    elif pressure_status in {"quality_watch", "prediction_gap_watch"}:
        _penalise(2, "Pressure watch active; enable notifications for Ukrainian teams.")

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "accelerate"}:
        _penalise(4, "Support teams mobilising; automation should pre-stage workflows.")
    elif support_status in {"reinforce", "watch"}:
        triggers.append("Support queues elevated")

    resilience_status = str(resilience.get("status", "")).lower()
    if resilience_status in {"fragile", "stressed"}:
        _penalise(3, "Resilience fragile; add resilience checks to automation tasks.")

    continuity_status = str(continuity.get("status", "")).lower()
    if continuity_status in {"constrained", "degraded"}:
        _penalise(3, "Continuity degraded; hold fallback playbooks ready for automation.")

    recovery_status = str(recovery.get("status", "")).lower()
    if recovery_status in {"stalled", "recover"}:
        _penalise(2, "Recovery still stabilising; include manual checkpoints in automation.")

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status in {"strained", "critical"}:
        _penalise(3, "Mission assurance strained; require leadership review of automations.")

    transform_score = transformation.get("transformation_score")
    if isinstance(transform_score, (float, int)) and transform_score >= 72:
        _boost(4, "Transformation tracks delivering automation-ready maturity.")
    elif isinstance(transform_score, (float, int)) and transform_score < 55:
        _penalise(3, "Transformation maturity low; automation adoption limited.")

    alignment_score = alignment.get("alignment_score")
    if isinstance(alignment_score, (float, int)) and alignment_score < 60:
        _penalise(3, "Command alignment below 60; ensure approvals captured in workflow.")
    elif isinstance(alignment_score, (float, int)) and alignment_score >= 75:
        _boost(3, "Command alignment strong, empowering automated coordination.")

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level in {"low", "very_low"}:
        _penalise(5, "Telemetry confidence low; automation must prompt validation runs.")
    elif confidence_level in {"moderate", "improving"}:
        _boost(2, "Confidence moderate; automation alerts can auto-publish summaries.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        _penalise(3, "Detection confidence below 0.6; gate automation outputs.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else None
    if isinstance(feeds, dict):
        for name, details in feeds.items():
            status = str(details.get("status", "")).lower()
            if status == "stale":
                _penalise(4, f"{name.title()} feed stale; automation must wait for refresh.")
            elif status == "warning":
                triggers.append(f"{name.title()} feed warning")

    risk_score = risks.get("severity_score")
    if isinstance(risk_score, (float, int)) and risk_score >= 80:
        _penalise(4, "Risk register elevated; attach automation monitoring hooks.")

    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        severity_label = str(gap.get("severity", "")).lower()
        description = gap.get("description") or gap.get("detail") or gap.get("name")
        if severity_label == "critical":
            _penalise(4, f"Critical gap blocking automation: {description or 'Gap'}")
        elif severity_label in {"major", "high"}:
            _penalise(2, f"Major gap to monitor: {description or 'Gap'}")

    detections_meta = meta.get("detections") if isinstance(meta, dict) else None
    if isinstance(detections_meta, dict) and detections_meta:
        total = 0
        for stats in detections_meta.values():
            count = stats.get("count") if isinstance(stats, dict) else None
            if isinstance(count, (int, float)):
                total += int(count)
        if total <= 1:
            _penalise(2, "Minimal detections in window; avoid unchecked automated triage.")

    for queue in support.get("priorities", []) or []:
        if not isinstance(queue, dict):
            continue
        team = queue.get("team") or queue.get("name")
        window = queue.get("support_window_hours")
        reason = queue.get("reason") or queue.get("focus")
        if team:
            automation_tracks.append(f"Support: {team}")
        _add_task(
            reason or "Support coordination",
            owner=team,
            window=window,
            mode="guided",
        )

    monitoring_channels.extend(
        [
            "Дежурний офіцер",
            "Автоматизований штабний канал",
            "UAF Ops Automation Dashboard",
        ]
    )

    actions.extend(
        [
            "Enable double-confirm prompts for automation that impacts frontline brigades.",
            "Schedule nightly automation health checks with the Ukrainian operations desk.",
        ]
    )
    operator_prompts.extend(
        [
            "Перевіряйте автоматичні розсилки перед передачею бригадам.",
            "Записуйте винятки у журналі автоматизації для зміни наступної зміни.",
        ]
    )

    def _dedupe_strings(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            if not value:
                continue
            if value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

    blockers = _dedupe_strings(blockers)
    drivers = _dedupe_strings(drivers)
    triggers = _dedupe_strings(triggers)
    automation_tracks = _dedupe_strings(automation_tracks)
    monitoring_channels = _dedupe_strings(monitoring_channels)
    actions = _dedupe_strings(actions)
    operator_prompts = _dedupe_strings(operator_prompts)

    unique_tasks: List[Dict[str, Any]] = []
    seen_task = set()
    for entry in tasks:
        key = (
            entry.get("task"),
            entry.get("owner"),
            entry.get("mode"),
            entry.get("window_hours"),
        )
        if key in seen_task:
            continue
        seen_task.add(key)
        unique_tasks.append(entry)
    tasks = unique_tasks

    automation_window: Optional[float] = None
    positive_windows = [value for value in windows if value > 0]
    if positive_windows:
        automation_window = round(min(positive_windows), 2)

    status = "autonomous"
    if severity >= 18 or score < 55:
        status = "manual_override"
    elif severity >= 10 or score < 68:
        status = "guided"
    elif severity >= 5 or score < 75:
        status = "tune"

    payload: Dict[str, Any] = {
        "status": status,
        "automation_score": round(score, 1),
    }
    if blockers:
        payload["blockers"] = blockers
    if drivers:
        payload["drivers"] = drivers
    if triggers:
        payload["triggers"] = triggers
    if automation_tracks:
        payload["automation_tracks"] = automation_tracks
    if tasks:
        payload["automation_tasks"] = tasks
    if monitoring_channels:
        payload["monitoring_channels"] = monitoring_channels
    if actions:
        payload["recommended_actions"] = actions
    if operator_prompts:
        payload["ukrainian_operator_prompts"] = operator_prompts
    if automation_window is not None:
        payload["automation_window_hours"] = automation_window

    return payload if payload else None


def _derive_automation_guardrails(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Assess automation guardrails and supervision posture."""

    automation = brief.get("automation_playbook") or {}
    frontline = brief.get("frontline_support") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    governance = brief.get("operational_governance") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    sustainment = brief.get("resource_sustainment") or {}
    support = brief.get("support_priorities") or {}
    alignment = brief.get("command_alignment") or {}
    directives = brief.get("command_directives") or {}
    communication = brief.get("communication_plan") or {}
    outlook = brief.get("operational_outlook") or {}
    confidence = brief.get("intelligence_confidence") or {}
    detection_quality = brief.get("detection_quality") or {}
    freshness = brief.get("data_freshness") or {}
    gaps = brief.get("intelligence_gaps") or []
    risks = brief.get("operational_risks") or {}
    meta = brief.get("meta") or {}

    if not any(
        [
            automation,
            frontline,
            readiness,
            pressure,
            governance,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            sustainment,
            support,
            alignment,
            directives,
            communication,
            outlook,
            confidence,
            detection_quality,
            freshness,
            gaps,
            risks,
            meta,
        ]
    ):
        return None

    score = 97.0
    severity = 0
    guardrails: List[str] = []
    safety_checks: List[str] = []
    overrides: List[str] = []
    monitoring: List[str] = []
    focus: List[str] = []
    actions: List[str] = []
    checklist: List[str] = []
    automation_candidates: List[str] = []
    review_windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            guardrails.append(str(note))

    def _boost(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            focus.append(str(note))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            review_windows.append(round(float(value), 2))

    def _extend_actions(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                actions.append(str(value))

    def _extend_monitoring(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                monitoring.append(str(value))

    readiness_level = str(readiness.get("level", "")).lower()
    support_window = readiness.get("support_window_hours")
    _register_window(support_window if isinstance(support_window, (float, int)) else None)
    if readiness_level == "critical":
        _penalise(
            14,
            "Response readiness is critical; dual approvals required for automation runs.",
        )
        overrides.append("Duty officer sign-off required before executing automation tasks.")
        checklist.append(
            "Отримайте підтвердження чергового офіцера перед запуском будь-якої автоматизації."
        )
    elif readiness_level == "strained":
        _penalise(
            8,
            "Response readiness is strained and limits unattended automation windows.",
        )
        overrides.append("Pair analysts with automation to supervise outputs in real time.")
        checklist.append("Закріпіть аналітика-наставника за кожним автоматизованим процесом.")
    elif readiness_level == "steady":
        _boost(2, "Readiness coverage supports supervised automation windows.")

    pressure_status = str(pressure.get("status", "")).lower()
    clearance = pressure.get("estimated_clearance_hours")
    _register_window(clearance if isinstance(clearance, (float, int)) else None)
    if pressure_status == "critical_backlog":
        _penalise(
            12,
            "Analyst backlog is critical; automation guardrails must be enforced.",
        )
        safety_checks.append(
            "Route high-priority queues through manual validation before auto-dispatch."
        )
        checklist.append(
            "Виконуйте ручну перевірку для черг з критичним пріоритетом перед відправкою."
        )
    elif pressure_status in {"backlog", "prediction_gap", "prediction_gap_watch"}:
        _penalise(6, "Analyst queue pressure requires automation oversight.")
        safety_checks.append("Enable sampling checks on automated triage outputs each hour.")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"critical", "mobilise"}:
        _penalise(
            9,
            "Frontline support is mobilising; automation must coordinate with brigade liaisons.",
        )
        overrides.append("Notify brigade liaison before executing frontline automation tasks.")
        checklist.append("Попередьте офіцера зв'язку бригади про автоматизовані дії.")
    elif frontline_status in {"reinforce", "watch"}:
        _penalise(4, "Frontline sustainment is sensitive; maintain automation guardrails.")

    automation_status = str(automation.get("status", "")).lower()
    automation_score = automation.get("automation_score")
    _register_window(automation.get("automation_window_hours"))
    if isinstance(automation_score, (float, int)):
        if automation_score < 55:
            _penalise(14, "Automation score is degraded and requires manual guardrails.")
        elif automation_score < 68:
            _penalise(7, "Automation score is trending low; keep supervision engaged.")
        elif automation_score >= 80:
            _boost(4, "Automation score indicates strong readiness for semi-autonomous ops.")
    if automation_status == "manual_override":
        _penalise(10, "Automation currently in manual override posture.")
        overrides.append("Automation remains in manual override until guardrails cleared.")
    elif automation_status == "guided":
        _penalise(5, "Automation is guided and must retain human confirmation steps.")

    for blocker in automation.get("blockers", []) or []:
        guardrails.append(str(blocker))
    _extend_actions(automation.get("recommended_actions"))
    _extend_monitoring(automation.get("monitoring_channels"))

    for task in automation.get("automation_tasks", []) or []:
        if not isinstance(task, dict):
            continue
        name = task.get("task") or task.get("name")
        mode = task.get("mode") or "guided"
        owner = task.get("owner")
        if name:
            automation_candidates.append(f"{name} ({mode})")
        if owner:
            overrides.append(f"Confirm owner {owner} acknowledges automation output.")
        window = task.get("window_hours")
        _register_window(window if isinstance(window, (float, int)) else None)

    governance_score = governance.get("governance_score")
    _register_window(governance.get("next_review_hours"))
    if isinstance(governance_score, (float, int)) and governance_score < 60:
        _penalise(6, "Governance cadence is weak; schedule automation oversight councils.")

    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)) and assurance_score < 60:
        _penalise(6, "Mission assurance is strained; keep automation under supervision.")

    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)) and resilience_score < 60:
        _penalise(5, "Operational resilience is vulnerable; enforce guardrails.")

    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)) and continuity_score < 60:
        _penalise(4, "Continuity constraints limit unattended automation windows.")

    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)) and recovery_score < 60:
        _penalise(4, "Recovery roadmap still stabilising; maintain automation supervision.")

    transform_score = transformation.get("transformation_score")
    if isinstance(transform_score, (float, int)) and transform_score >= 75:
        _boost(3, "Transformation tracks unlock automation-ready workflows.")
    elif isinstance(transform_score, (float, int)) and transform_score < 55:
        _penalise(3, "Transformation maturity is low; automation adoption must be gated.")

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "accelerate"}:
        _penalise(5, "Sustainment plan is strained; automation must protect logistics cues.")

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "reinforce"}:
        _penalise(5, "Support priorities elevated; confirm automation with support cell.")

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status in {"misaligned", "drift", "at_risk"}:
        _penalise(6, "Command alignment gaps require tighter automation guardrails.")
        _extend_actions(alignment.get("recommended_actions"))

    directive_status = str(directives.get("status", "")).lower()
    if directive_status in {"escalate", "crisis"}:
        _penalise(7, "Command directives demand crisis posture; automation must sync hourly.")
    _extend_actions(directives.get("recommended_actions"))

    comm_status = str(communication.get("status", "")).lower()
    if comm_status in {"crisis", "escalated"}:
        _penalise(6, "Communication cadence in crisis; automation outputs require briefing.")
    _extend_actions(communication.get("recommended_actions"))

    outlook_status = str(outlook.get("status", "")).lower()
    if outlook_status in {"heightened", "heightened_watch", "escalate"}:
        _penalise(5, "Operational outlook elevated; automation requires leadership watch.")

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(7, "Intelligence confidence low; automation outputs must be verified.")
        safety_checks.append("Run validation sampling on every automated insight package.")
    elif confidence_level == "guarded":
        _penalise(4, "Telemetry confidence guarded; keep automation under review.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        _penalise(5, "Detection confidence below 0.6; pause auto-publication of detections.")
        safety_checks.append("Require analyst confirmation before publishing automated detections.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        minutes = feed_info.get("age_minutes")
        if isinstance(minutes, (float, int)):
            _register_window(minutes / 60 if minutes > 0 else None)
        if status == "stale":
            _penalise(8, f"{str(feed_name).title()} feed is stale; automation must halt on this feed.")
            safety_checks.append(
                f"Disable unattended automation on {str(feed_name).title()} feed until refreshed."
            )
        elif status == "warning":
            _penalise(4, f"{str(feed_name).title()} feed ageing; tighten automation windows.")

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity_label = str(gap.get("severity", "")).lower()
        description = gap.get("description") or gap.get("name") or gap.get("detail")
        if severity_label == "critical":
            _penalise(8, f"Critical intelligence gap: {description or 'Gap'}")
        elif severity_label in {"major", "high"}:
            _penalise(5, f"Major intelligence gap: {description or 'Gap'}")

    severity_score = risks.get("severity_score")
    if isinstance(severity_score, (float, int)) and severity_score >= 80:
        _penalise(6, "Operational risk register is elevated; maintain guardrails.")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.65:
        _penalise(5, "Feedback accuracy under 0.65; restrict unsupervised automation.")

    focus.extend(frontline.get("priority_units", []) or [])
    focus.extend(sustainment.get("resource_needs", []) or [])
    focus.extend(support.get("priorities", []) or [])

    actions.extend(
        [
            "Brief the Ukrainian automation officer on guardrail posture at shift start.",
            "Log every override and guardrail change in the automation journal for audits.",
        ]
    )

    checklist.extend(
        [
            "Зафіксуйте усі зміни в журналі автоматизації та передайте зміні наступного чергового.",
            "Перевірте канали моніторингу автоматизації на наявність збоїв кожні 2 години.",
        ]
    )

    monitoring.extend(
        [
            "Automation Ops Room",
            "UAF Automation Watch Channel",
        ]
    )

    def _dedupe_strings(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            if not value:
                continue
            text = str(value)
            if text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    guardrails = _dedupe_strings(guardrails)
    safety_checks = _dedupe_strings(safety_checks)
    overrides = _dedupe_strings(overrides)
    monitoring = _dedupe_strings(monitoring)
    focus = _dedupe_strings([
        item if isinstance(item, str) else item.get("name") or item.get("focus")
        for item in focus
    ])
    actions = _dedupe_strings(actions)
    checklist = _dedupe_strings(checklist)
    automation_candidates = _dedupe_strings(automation_candidates)

    next_review: Optional[float] = None
    positive_windows = [value for value in review_windows if value and value > 0]
    if positive_windows:
        next_review = round(min(positive_windows), 2)

    status = "autonomous"
    if severity >= 26 or score < 55:
        status = "locked_down"
    elif severity >= 18 or score < 65:
        status = "manual_guarded"
    elif severity >= 10 or score < 75:
        status = "supervised"
    elif severity >= 5 or score < 85:
        status = "pilot"

    payload: Dict[str, Any] = {
        "status": status,
        "autonomy_score": round(score, 1),
    }
    if guardrails:
        payload["guardrails"] = guardrails
    if safety_checks:
        payload["safety_checks"] = safety_checks
    if overrides:
        payload["operator_overrides"] = overrides
    if monitoring:
        payload["monitoring_channels"] = monitoring
    if focus:
        payload["oversight_focus"] = focus
    if actions:
        payload["recommended_actions"] = actions
    if checklist:
        payload["ukrainian_checklist"] = checklist
    if automation_candidates:
        payload["automation_candidates"] = automation_candidates
    if next_review is not None:
        payload["next_review_hours"] = next_review

    return payload if payload else None


def _derive_automation_mission_control(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Coordinate automation mission control posture for Ukrainian operators."""

    automation = brief.get("automation_playbook") or {}
    guardrails = brief.get("automation_guardrails") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    frontline = brief.get("frontline_support") or {}
    governance = brief.get("operational_governance") or {}
    directives = brief.get("command_directives") or {}
    communication = brief.get("communication_plan") or {}
    alignment = brief.get("command_alignment") or {}
    support = brief.get("support_priorities") or {}
    sustainment = brief.get("resource_sustainment") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    outlook = brief.get("operational_outlook") or {}
    escalation = brief.get("escalation_readiness") or {}
    confidence = brief.get("intelligence_confidence") or {}
    detection_quality = brief.get("detection_quality") or {}
    meta = brief.get("meta") or {}

    if not any(
        [
            automation,
            guardrails,
            readiness,
            pressure,
            frontline,
            governance,
            directives,
            communication,
            alignment,
            support,
            sustainment,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            outlook,
            escalation,
            confidence,
            detection_quality,
            meta,
        ]
    ):
        return None

    score = 95.0
    severity = 0
    control_focus: List[str] = []
    mission_channels: List[str] = []
    handoffs: List[str] = []
    actions: List[str] = []
    watch_items: List[str] = []
    operator_prompts: List[str] = []
    automation_tracks: List[str] = []
    supervisor_actions: List[str] = []
    critical_guardrails: List[str] = []
    windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            watch_items.append(str(note))

    def _boost(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            control_focus.append(str(note))

    def _collect(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if not value:
                continue
            target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    readiness_level = str(readiness.get("level", "")).lower()
    _register_window(
        readiness.get("support_window_hours")
        if isinstance(readiness.get("support_window_hours"), (float, int))
        else None
    )
    if readiness_level == "critical":
        _penalise(12, "Readiness critical: mission control must authorise automation runs.")
        handoffs.append("Duty officer must sign automation tasks before execution.")
        operator_prompts.append("Погодьте кожне автоматизоване завдання з черговим офіцером.")
    elif readiness_level == "strained":
        _penalise(7, "Readiness strained: mission control stays paired with automation.")
        handoffs.append("Pair analysts with automation queue during strained readiness.")
        operator_prompts.append("Призначте наставника до автоматизованої черги на зміні.")
    elif readiness_level in {"steady", "reinforced"}:
        _boost(3, "Readiness coverage supports supervised automation windows.")

    pressure_status = str(pressure.get("status", "")).lower()
    _register_window(
        pressure.get("estimated_clearance_hours")
        if isinstance(pressure.get("estimated_clearance_hours"), (float, int))
        else None
    )
    if pressure_status == "critical_backlog":
        _penalise(10, "Critical backlog: prioritise manual validation of automation output.")
        supervisor_actions.append("Route critical automation outputs through manual validation queue.")
    elif pressure_status in {"backlog", "prediction_gap", "prediction_gap_watch"}:
        _penalise(6, "Queue pressure elevated: mission control maintains sampling checks.")
        supervisor_actions.append("Maintain hourly sampling of automated triage decisions.")
    elif pressure_status in {"steady", "cleared"}:
        _boost(2, "Analyst throughput supports longer autonomous windows.")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"mobilise", "critical"}:
        _penalise(6, "Frontline sustainment elevated: coordinate automation with brigade liaisons.")
        handoffs.append("Notify brigade liaison before executing frontline automation tasks.")
        operator_prompts.append("Попередьте офіцера зв'язку бригади про автоматизовані оновлення.")
    elif frontline_status in {"reinforce", "watch"}:
        _penalise(3, "Frontline sustainment sensitive: keep mission control synced with logistics cell.")

    governance_score = governance.get("governance_score")
    if isinstance(governance_score, (float, int)) and governance_score < 60:
        _penalise(5, "Governance cadence weak: mission control must document decisions.")
        actions.append("Log automation mission control decisions in governance tracker.")

    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)) and assurance_score < 60:
        _penalise(4, "Mission assurance strained: tighten automation approvals.")

    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)) and resilience_score < 60:
        _penalise(4, "Operational resilience vulnerable: keep human-in-the-loop supervision.")

    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)) and continuity_score < 60:
        _penalise(3, "Continuity constraints limit unattended automation windows.")

    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)) and recovery_score < 60:
        _penalise(3, "Recovery efforts ongoing: mission control monitors stabilisation tracks.")

    transform_score = transformation.get("transformation_score")
    if isinstance(transform_score, (float, int)) and transform_score >= 75:
        _boost(3, "Transformation tracks enable automation scaling.")
    elif isinstance(transform_score, (float, int)) and transform_score < 55:
        _penalise(2, "Transformation maturity low: mission control maintains tighter guardrails.")

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "accelerate"}:
        _penalise(4, "Sustainment surge: mission control coordinates automation handoffs with logistics.")

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "reinforce"}:
        _penalise(3, "Support priorities elevated: automation outputs require support confirmation.")

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status in {"misaligned", "drift", "at_risk"}:
        _penalise(6, "Command alignment gaps demand mission control oversight.")
        _collect(alignment.get("recommended_actions"), actions)

    directive_status = str(directives.get("status", "")).lower()
    if directive_status in {"escalate", "crisis"}:
        _penalise(6, "Directive posture escalated: mission control briefs leadership each run.")
        actions.append("Brief Ukrainian command on automation outputs during crisis posture.")

    communication_status = str(communication.get("status", "")).lower()
    if communication_status in {"crisis", "escalated"}:
        _penalise(4, "Communication cadence in crisis: mission control syncs with comms cell.")

    outlook_status = str(outlook.get("status", "")).lower()
    if outlook_status in {"heightened", "heightened_watch", "escalate"}:
        _penalise(4, "Operational outlook elevated: keep automation within mission control loop.")

    escalation_status = str(escalation.get("status", "")).lower()
    if escalation_status in {"escalate", "review", "heightened"}:
        _penalise(3, "Escalation pathways active: mission control reviews triggers each sync.")
    _register_window(
        escalation.get("next_review_hours")
        if isinstance(escalation.get("next_review_hours"), (float, int))
        else None
    )

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(6, "Telemetry confidence low: mission control enforces validation samples.")
        supervisor_actions.append("Enforce validation sampling on every automation batch.")
    elif confidence_level == "guarded":
        _penalise(3, "Telemetry confidence guarded: keep analysts in approval loop.")
    elif confidence_level in {"high", "strong"}:
        _boost(2, "Telemetry confidence strong: extend automation coverage cautiously.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        _penalise(4, "Detection confidence below 0.6: mission control reviews detection releases.")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.65:
        _penalise(4, "Feedback accuracy low: mission control cross-checks automation learning loops.")

    guardrail_status = str(guardrails.get("status", "")).lower()
    if guardrail_status in {"locked_down", "manual_override", "manual_guarded"}:
        _penalise(12, "Guardrails constrained: mission control required for every automation run.")
        handoffs.append("Record guardrail approvals in automation journal before execution.")
        operator_prompts.append("Занотуйте кожен оверрайд у журналі автоматизації до запуску.")
    elif guardrail_status in {"guided", "pilot"}:
        _penalise(5, "Guardrails guided: maintain mission control watch standers.")
    elif guardrail_status in {"autonomous", "steady"}:
        _boost(4, "Guardrails stable: mission control can expand automation windows.")

    autonomy_score = guardrails.get("autonomy_score")
    if isinstance(autonomy_score, (float, int)) and autonomy_score < 60:
        _penalise(5, "Autonomy score low: mission control must stay hands-on.")

    automation_status = str(automation.get("status", "")).lower()
    if automation_status in {"manual_override", "manual"}:
        _penalise(8, "Automation playbook in manual override.")
    elif automation_status in {"guided", "tune"}:
        _penalise(3, "Automation guided: mission control supervises calibrations.")
    elif automation_status in {"autonomous", "pilot"}:
        _boost(3, "Automation status autonomous: mission control focuses on audit cadence.")

    automation_window = automation.get("automation_window_hours")
    _register_window(automation_window if isinstance(automation_window, (float, int)) else None)

    guardrail_review = guardrails.get("next_review_hours")
    _register_window(guardrail_review if isinstance(guardrail_review, (float, int)) else None)

    _collect(automation.get("automation_tracks"), automation_tracks)
    _collect(automation.get("drivers"), control_focus)
    _collect(automation.get("triggers"), watch_items)
    _collect(automation.get("recommended_actions"), actions)
    _collect(automation.get("monitoring_channels"), mission_channels)
    _collect(guardrails.get("monitoring_channels"), mission_channels)
    _collect(guardrails.get("recommended_actions"), actions)
    _collect(guardrails.get("safety_checks"), supervisor_actions)
    _collect(guardrails.get("operator_overrides"), handoffs)
    _collect(guardrails.get("ukrainian_checklist"), operator_prompts)

    guardrail_list = guardrails.get("guardrails")
    if isinstance(guardrail_list, list):
        _collect(guardrail_list, critical_guardrails)

    mission_channels.extend([
        "Automation Ops Room",
        "Mission Control Net",
    ])
    actions.extend(
        [
            "Schedule Ukrainian automation mission control sync at shift turnover.",
            "Archive automation decision logs after each mission control review.",
        ]
    )
    operator_prompts.extend(
        [
            "Забезпечте резервний офіцерський нагляд під час автоматизованих запусків.",
            "Передайте наступній зміні короткий звіт про стан автоматизації.",
        ]
    )

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            if not value:
                continue
            text = str(value)
            if text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    control_focus = _dedupe(control_focus)
    mission_channels = _dedupe(mission_channels)
    handoffs = _dedupe(handoffs)
    actions = _dedupe(actions)
    watch_items = _dedupe(watch_items)
    operator_prompts = _dedupe(operator_prompts)
    automation_tracks = _dedupe(automation_tracks)
    supervisor_actions = _dedupe(supervisor_actions)
    critical_guardrails = _dedupe(critical_guardrails)

    next_sync: Optional[float] = None
    if windows:
        positive = [value for value in windows if value > 0]
        if positive:
            next_sync = round(min(positive), 2)

    status = "mission_ready"
    if severity >= 20 or score < 55:
        status = "manual_control"
    elif severity >= 14 or score < 68:
        status = "paired_supervision"
    elif severity >= 7 or score < 78:
        status = "supervised"

    supervision = "mission_ready"
    if status == "manual_control":
        supervision = "manual_control"
    elif status == "paired_supervision":
        supervision = "paired_supervision"
    elif status == "supervised":
        supervision = "supervised"

    payload: Dict[str, Any] = {
        "status": status,
        "mission_control_score": round(score, 1),
        "automation_mode": automation_status or "unknown",
        "supervision_level": supervision,
    }
    if severity > 0:
        payload["severity_index"] = severity
    if guardrail_status:
        payload["guardrail_status"] = guardrail_status
    if next_sync is not None:
        payload["next_sync_hours"] = next_sync
    if control_focus:
        payload["control_focus"] = control_focus
    if mission_channels:
        payload["mission_channels"] = mission_channels
    if automation_tracks:
        payload["automation_tracks"] = automation_tracks
    if supervisor_actions:
        payload["supervisor_actions"] = supervisor_actions
    if handoffs:
        payload["handoff_requirements"] = handoffs
    if watch_items:
        payload["watch_items"] = watch_items
    if actions:
        payload["recommended_actions"] = actions
    if operator_prompts:
        payload["ukrainian_operator_prompts"] = operator_prompts
    if critical_guardrails:
        payload["critical_guardrails"] = critical_guardrails

    return payload if payload else None


def _derive_automation_autonomy(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Score autonomous execution posture for Ukrainian automation teams."""

    automation = brief.get("automation_playbook") or {}
    guardrails = brief.get("automation_guardrails") or {}
    mission_control = brief.get("automation_mission_control") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    frontline = brief.get("frontline_support") or {}
    sustainment = brief.get("resource_sustainment") or {}
    support = brief.get("support_priorities") or {}
    governance = brief.get("operational_governance") or {}
    alignment = brief.get("command_alignment") or {}
    directives = brief.get("command_directives") or {}
    communication = brief.get("communication_plan") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    outlook = brief.get("operational_outlook") or {}
    escalation = brief.get("escalation_readiness") or {}
    confidence = brief.get("intelligence_confidence") or {}
    detection_quality = brief.get("detection_quality") or {}
    freshness = brief.get("data_freshness") or {}
    risks = brief.get("operational_risks") or {}
    gaps = brief.get("intelligence_gaps") or []
    meta = brief.get("meta") or {}

    if not any(
        [
            automation,
            guardrails,
            mission_control,
            readiness,
            pressure,
            frontline,
            sustainment,
            support,
            governance,
            alignment,
            directives,
            communication,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            outlook,
            escalation,
            confidence,
            detection_quality,
            freshness,
            risks,
            gaps,
            meta,
        ]
    ):
        return None

    score = 90.0
    severity = 0
    enablers: List[str] = []
    risk_factors: List[str] = []
    trusted_tasks: List[str] = []
    restricted_tasks: List[str] = []
    safeguards: List[str] = []
    monitoring: List[str] = []
    fallback: List[str] = []
    autonomy_tracks: List[str] = []
    watch_items: List[str] = []
    actions: List[str] = []
    windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            risk_factors.append(str(note))

    def _boost(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            enablers.append(str(note))

    def _collect(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if not value:
                continue
            target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    readiness_level = str(readiness.get("level", "")).lower()
    support_window = readiness.get("support_window_hours")
    _register_window(support_window if isinstance(support_window, (float, int)) else None)
    if readiness_level == "critical":
        _penalise(12, "Readiness critical – automation must remain manual only.")
        fallback.append("Duty officer validates every automation step before execution.")
        safeguards.append("Затверджуйте кожен запуск автоматизації разом із черговим офіцером.")
    elif readiness_level == "strained":
        _penalise(7, "Readiness strained – pair automation with human supervision.")
        fallback.append("Pair analysts with automation queues until readiness recovers.")
        safeguards.append("Призначте наставника до автоматизованої черги на зміні.")
    elif readiness_level in {"steady", "reinforced"}:
        _boost(3, "Readiness coverage supports extended automation windows.")

    pressure_status = str(pressure.get("status", "")).lower()
    _register_window(
        pressure.get("estimated_clearance_hours")
        if isinstance(pressure.get("estimated_clearance_hours"), (float, int))
        else None
    )
    if pressure_status == "critical_backlog":
        _penalise(10, "Critical backlog – automation autonomy paused until queues clear.")
        fallback.append("Hold automation outputs for manual review during backlog clearance.")
    elif pressure_status in {"backlog", "prediction_gap", "prediction_gap_watch"}:
        _penalise(5, "Queue pressure elevated – maintain tight supervision on automation.")
    elif pressure_status in {"steady", "cleared"}:
        _boost(2, "Prediction queues balanced – automation can extend coverage cautiously.")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"critical", "mobilise"}:
        _penalise(6, "Frontline mobilisation active – automation must sync with brigade liaisons.")
        fallback.append("Notify brigade liaison before executing autonomous frontline tasks.")
        safeguards.append("Повідомляйте офіцера зв'язку бригади про автономні дії.")
    elif frontline_status in {"reinforce", "watch"}:
        _penalise(3, "Frontline sustainment sensitive – maintain autonomy guardrails.")

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "accelerate"}:
        _penalise(4, "Sustainment surge – automation must protect logistics cadence.")

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "reinforce"}:
        _penalise(3, "Support priorities elevated – automation outputs require confirmation.")

    guardrail_status = str(guardrails.get("status", "")).lower()
    guardrail_score = guardrails.get("autonomy_score")
    if guardrail_status in {"locked_down", "manual_guarded"}:
        _penalise(12, "Guardrails locked down – autonomy cannot proceed unsupervised.")
        fallback.append("Log every guardrail override with mission control before execution.")
    elif guardrail_status in {"pilot", "supervised"}:
        _penalise(5, "Guardrails in pilot – maintain human confirmations.")
    elif guardrail_status == "autonomous":
        _boost(4, "Guardrails stable – autonomy expansion supported.")
    if isinstance(guardrail_score, (float, int)):
        if guardrail_score < 60:
            _penalise(8, "Guardrail score below 60 – automation limited to manual approval.")
        elif guardrail_score >= 85:
            _boost(4, "Guardrail score strong – autonomy windows can widen.")

    mission_status = str(mission_control.get("status", "")).lower()
    mission_score = mission_control.get("mission_control_score")
    if mission_status in {"manual_control"}:
        _penalise(10, "Mission control enforcing manual control over automation.")
    elif mission_status in {"paired_supervision", "supervised"}:
        _penalise(5, "Mission control supervision required – autonomy limited.")
    elif mission_status in {"mission_ready", "autonomous"}:
        _boost(3, "Mission control confident – autonomy uplift approved.")
    if isinstance(mission_score, (float, int)):
        if mission_score < 65:
            _penalise(4, "Mission control score trending low – increase oversight.")
        elif mission_score >= 80:
            _boost(3, "Mission control score strong – autonomy window expanding.")

    automation_status = str(automation.get("status", "")).lower()
    automation_score = automation.get("automation_score")
    if automation_status in {"manual_override", "manual"}:
        _penalise(9, "Automation playbook in manual override.")
    elif automation_status in {"guided", "tune"}:
        _penalise(4, "Automation guided – maintain supervision.")
    elif automation_status in {"autonomous", "pilot"}:
        _boost(4, "Automation playbook autonomous – scale trusted tasks.")
    if isinstance(automation_score, (float, int)):
        if automation_score < 60:
            _penalise(6, "Automation score degraded – autonomy blocked.")
        elif automation_score >= 82:
            _boost(4, "Automation score high – autonomy validated by telemetry.")

    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)):
        if resilience_score < 60:
            _penalise(4, "Operational resilience weak – keep humans in the loop.")
        elif resilience_score >= 75:
            _boost(2, "Resilience strong – automation can absorb shocks.")

    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)) and continuity_score < 60:
        _penalise(4, "Continuity constraints limit unattended automation windows.")

    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)) and recovery_score < 60:
        _penalise(3, "Recovery roadmap stabilising – autonomy staged gradually.")

    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)) and assurance_score < 60:
        _penalise(4, "Mission assurance strained – leadership demands manual checks.")

    transform_score = transformation.get("transformation_score")
    if isinstance(transform_score, (float, int)):
        if transform_score >= 78:
            _boost(3, "Transformation agenda supports automation scaling.")
        elif transform_score < 55:
            _penalise(3, "Transformation maturity low – autonomy adoption gated.")

    governance_status = str(governance.get("status", "")).lower()
    if governance_status in {"degraded", "at_risk"}:
        _penalise(4, "Governance cadence degraded – autonomy must log decisions.")

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status in {"misaligned", "drift", "at_risk"}:
        _penalise(5, "Command alignment gaps require manual sign-off.")

    directive_status = str(directives.get("status", "")).lower()
    if directive_status in {"escalate", "crisis"}:
        _penalise(6, "Command directives escalated – autonomy must brief leadership each run.")

    communication_status = str(communication.get("status", "")).lower()
    if communication_status in {"crisis", "escalated"}:
        _penalise(4, "Communication cadence in crisis – automation outputs broadcast manually.")

    outlook_status = str(outlook.get("status", "")).lower()
    if outlook_status in {"escalate", "heightened", "heightened_watch"}:
        _penalise(4, "Operational outlook elevated – autonomy restricted to supervised windows.")

    escalation_status = str(escalation.get("status", "")).lower()
    if escalation_status in {"escalate", "review", "heightened"}:
        _penalise(3, "Escalation pathways active – automation requires mission control pairing.")
    _register_window(
        escalation.get("next_review_hours")
        if isinstance(escalation.get("next_review_hours"), (float, int))
        else None
    )

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(6, "Telemetry confidence low – halt unattended automation.")
    elif confidence_level == "guarded":
        _penalise(3, "Telemetry confidence guarded – keep analysts approving outputs.")
    elif confidence_level in {"high", "strong"}:
        _boost(2, "Telemetry confidence strong – autonomy supported.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        _penalise(4, "Detection confidence below 0.6 – automation must be reviewed manually.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        minutes = feed_info.get("age_minutes")
        if isinstance(minutes, (float, int)):
            _register_window(minutes / 60 if minutes > 0 else None)
        if status == "stale":
            _penalise(6, f"{str(feed_name).title()} feed stale – autonomy paused on this stream.")
            watch_items.append(f"Refresh {str(feed_name).title()} feed for automation fidelity.")
        elif status == "warning":
            _penalise(3, f"{str(feed_name).title()} feed ageing – tighten automation sampling.")

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity_label = str(gap.get("severity", "")).lower()
        description = gap.get("description") or gap.get("name") or gap.get("detail")
        if severity_label == "critical":
            _penalise(6, f"Critical intelligence gap – automation blocked: {description or 'Gap'}")
            watch_items.append(f"Resolve critical gap: {description or 'Gap'}")
        elif severity_label in {"major", "high"}:
            _penalise(3, f"Major intelligence gap monitored: {description or 'Gap'}")

    severity_score = risks.get("severity_score")
    if isinstance(severity_score, (float, int)) and severity_score >= 80:
        _penalise(5, "Operational risk elevated – automation requires manual controls.")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.65:
        _penalise(4, "Feedback accuracy under 0.65 – validate automation learning loops.")

    automation_window = automation.get("automation_window_hours")
    _register_window(automation_window if isinstance(automation_window, (float, int)) else None)

    mission_sync = mission_control.get("next_sync_hours")
    _register_window(mission_sync if isinstance(mission_sync, (float, int)) else None)

    guardrail_review = guardrails.get("next_review_hours")
    _register_window(guardrail_review if isinstance(guardrail_review, (float, int)) else None)

    _collect(automation.get("automation_tracks"), autonomy_tracks)
    _collect(automation.get("drivers"), enablers)
    _collect(automation.get("triggers"), watch_items)
    _collect(automation.get("recommended_actions"), actions)
    _collect(automation.get("monitoring_channels"), monitoring)
    _collect(guardrails.get("monitoring_channels"), monitoring)
    _collect(guardrails.get("recommended_actions"), actions)
    _collect(guardrails.get("safety_checks"), fallback)
    _collect(guardrails.get("operator_overrides"), fallback)
    _collect(guardrails.get("ukrainian_checklist"), safeguards)
    _collect(mission_control.get("mission_channels"), monitoring)
    _collect(mission_control.get("handoff_requirements"), fallback)
    _collect(mission_control.get("supervisor_actions"), fallback)
    _collect(mission_control.get("recommended_actions"), actions)
    _collect(mission_control.get("control_focus"), autonomy_tracks)
    _collect(mission_control.get("watch_items"), watch_items)
    _collect(mission_control.get("ukrainian_operator_prompts"), safeguards)

    for task in automation.get("automation_tasks", []) or []:
        if not isinstance(task, dict):
            continue
        name = task.get("task") or task.get("name") or "Task"
        mode = str(task.get("mode") or "automated").lower()
        owner = task.get("owner") or task.get("team")
        window = task.get("window_hours") or task.get("support_window_hours")
        if isinstance(window, (float, int)):
            _register_window(float(window))
        descriptor = str(name)
        if owner:
            descriptor += f" [{owner}]"
        descriptor += f" ({mode})"
        if isinstance(window, (float, int)):
            descriptor += f" – {float(window):.1f}h"
        if mode in {"automated", "autonomous", "pilot"}:
            trusted_tasks.append(descriptor)
        else:
            restricted_tasks.append(descriptor)

    monitoring.extend([
        "Automation Ops Room",
        "Mission Control Net",
    ])

    safeguards.extend(
        [
            "Фіксуйте всі автономні рішення у журналі чергового штабу.",
            "Підтверджуйте запуск автономних скриптів за двофакторною процедурою.",
        ]
    )

    actions.extend(
        [
            "Publish automation autonomy status to the Ukrainian operations dashboard each shift.",
            "Schedule autonomy rehearsal drills with mission control before extending unattended windows.",
        ]
    )

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            if not value:
                continue
            text = str(value)
            if text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    enablers = _dedupe(enablers)
    risk_factors = _dedupe(risk_factors)
    trusted_tasks = _dedupe(trusted_tasks)
    restricted_tasks = _dedupe(restricted_tasks)
    safeguards = _dedupe(safeguards)
    monitoring = _dedupe(monitoring)
    fallback = _dedupe(fallback)
    autonomy_tracks = _dedupe(autonomy_tracks)
    watch_items = _dedupe(watch_items)
    actions = _dedupe(actions)

    autonomy_window: Optional[float] = None
    if windows:
        positive = [value for value in windows if value > 0]
        if positive:
            autonomy_window = round(min(positive), 2)

    status = "autonomous_ready"
    if severity >= 22 or score < 55:
        status = "manual_only"
    elif severity >= 16 or score < 65:
        status = "manual_guarded"
    elif severity >= 10 or score < 75:
        status = "supervised"
    elif severity >= 6 or score < 85:
        status = "mission_ready"

    supervision_requirements = {
        "manual_only": "Continuous Ukrainian oversight with dual approvals.",
        "manual_guarded": "Duty officer co-signs automation outputs each run.",
        "supervised": "Mission control samples automation hourly.",
        "mission_ready": "Mission control on-shift with rapid escalation triggers.",
        "autonomous_ready": "Mission control on-call; automation cell monitors telemetry board.",
    }.get(status, "Ukrainian oversight required.")

    payload: Dict[str, Any] = {
        "status": status,
        "autonomy_score": round(score, 1),
        "supervision_requirements": supervision_requirements,
    }
    if severity > 0:
        payload["severity_index"] = severity
    if autonomy_window is not None:
        payload["autonomy_window_hours"] = autonomy_window
    if automation_status:
        payload["operational_mode"] = automation_status
    if mission_status:
        payload["mission_control_status"] = mission_status
    if enablers:
        payload["autonomy_enablers"] = enablers
    if risk_factors:
        payload["risk_factors"] = risk_factors
    if trusted_tasks:
        payload["trusted_tasks"] = trusted_tasks
    if restricted_tasks:
        payload["restricted_tasks"] = restricted_tasks
    if autonomy_tracks:
        payload["automation_tracks"] = autonomy_tracks
    if monitoring:
        payload["monitoring_requirements"] = monitoring
    if fallback:
        payload["fallback_protocols"] = fallback
    if safeguards:
        payload["ukrainian_safeguards"] = safeguards
    if watch_items:
        payload["watch_items"] = watch_items
    if actions:
        payload["recommended_actions"] = actions

    return payload if payload else None


def _derive_automation_deployment(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Synthesise automation deployment posture for Ukrainian operators."""

    automation = brief.get("automation_playbook") or {}
    guardrails = brief.get("automation_guardrails") or {}
    mission_control = brief.get("automation_mission_control") or {}
    autonomy = brief.get("automation_autonomy") or {}
    failsafes = brief.get("automation_failsafes") or {}
    validation = brief.get("automation_validation") or {}
    frontline = brief.get("frontline_support") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    sustainment = brief.get("resource_sustainment") or {}
    support = brief.get("support_priorities") or {}
    governance = brief.get("operational_governance") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    directives = brief.get("command_directives") or {}
    alignment = brief.get("command_alignment") or {}
    communication = brief.get("communication_plan") or {}
    escalation = brief.get("escalation_readiness") or {}
    confidence = brief.get("intelligence_confidence") or {}
    detection_quality = brief.get("detection_quality") or {}
    freshness = brief.get("data_freshness") or {}
    meta = brief.get("meta") or {}
    gaps = brief.get("intelligence_gaps") or []
    activity = brief.get("activity_summary") or {}

    if not any(
        [
            automation,
            guardrails,
            mission_control,
            autonomy,
            failsafes,
            validation,
            frontline,
            readiness,
            pressure,
            sustainment,
            support,
            governance,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            directives,
            alignment,
            communication,
            escalation,
            confidence,
            detection_quality,
            freshness,
            meta,
            gaps,
            activity,
        ]
    ):
        return None

    score = 86.0
    severity = 0
    drivers: List[str] = []
    blockers: List[str] = []
    prerequisites: List[str] = []
    watch_items: List[str] = []
    actions: List[str] = []
    operator_prompts: List[str] = []
    deployment_tracks: List[Dict[str, Any]] = []
    windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(amount)
        score = max(0.0, score - float(amount) * 1.35)
        if note:
            blockers.append(str(note))

    def _boost(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            drivers.append(str(note))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 3))

    def _add_track(
        name: Optional[str],
        *,
        owner: Optional[str] = None,
        readiness: Optional[str] = None,
        window: Optional[float] = None,
    ) -> None:
        if not name:
            return
        entry: Dict[str, Any] = {"name": str(name)}
        if owner:
            entry["owner"] = str(owner)
        if readiness:
            entry["readiness"] = str(readiness)
        if isinstance(window, (float, int)) and window > 0:
            entry["window_hours"] = round(float(window), 2)
            windows.append(entry["window_hours"])
        deployment_tracks.append(entry)

    def _extend_actions(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                actions.append(str(value))

    automation_status = str(automation.get("status", "")).lower()
    automation_score = automation.get("automation_score")
    _register_window(
        automation.get("automation_window_hours")
        if isinstance(automation.get("automation_window_hours"), (float, int))
        else None
    )
    if automation_status in {"manual_override", "manual"}:
        _penalise(9, "Automation playbook locked to manual control.")
        prerequisites.append("Lift manual override with duty automation officer approval.")
        operator_prompts.append(
            "Отримайте підтвердження старшого офіцера перед запуском автоматизованих завдань."
        )
    elif automation_status in {"guided", "tune"}:
        _penalise(5, "Automation playbook still requires guided execution.")
        prerequisites.append("Pair guided automation tasks with analyst oversight.")
    elif automation_status in {"autonomous", "ready", "steady"}:
        _boost(4, "Automation playbook delivering stable runs for deployment.")

    if isinstance(automation_score, (float, int)):
        if automation_score >= 85:
            _boost(3, "Automation score above 85 supports deployment.")
        elif automation_score < 65:
            _penalise(4, "Automation score below 65 demands supervised launch.")

    for task in automation.get("automation_tasks", []) or []:
        if not isinstance(task, dict):
            continue
        mode = str(task.get("mode", "")).lower()
        readiness_mode = "manual" if mode in {"manual", "guided"} else "auto"
        _add_track(
            task.get("task"),
            owner=task.get("owner") or task.get("team"),
            readiness=readiness_mode,
            window=task.get("window_hours") or task.get("support_window_hours"),
        )
        if mode in {"manual", "guided"}:
            prerequisites.append("Confirm guided automation steps with analyst lead.")

    guardrail_status = str(guardrails.get("status", "")).lower()
    guardrail_score = guardrails.get("autonomy_score")
    _register_window(
        guardrails.get("next_review_hours")
        if isinstance(guardrails.get("next_review_hours"), (float, int))
        else None
    )
    if guardrail_status in {"locked_down", "manual_override", "manual_guarded"}:
        _penalise(8, "Guardrails locked down for automation deployment.")
        prerequisites.append("Review guardrail overrides with automation officer.")
        watch_items.append("Guardrail review pending before deployment.")
    elif guardrail_status in {"pilot", "guided"}:
        _penalise(4, "Guardrails in pilot mode; maintain supervision during rollout.")
    elif guardrail_status in {"autonomous", "steady"}:
        _boost(3, "Guardrails stable and support deployment windows.")
    if isinstance(guardrail_score, (float, int)) and guardrail_score < 60:
        _penalise(5, "Guardrail score under 60 requires manual confirmation.")

    mission_status = str(mission_control.get("status", "")).lower()
    mission_score = mission_control.get("mission_control_score")
    _register_window(
        mission_control.get("next_sync_hours")
        if isinstance(mission_control.get("next_sync_hours"), (float, int))
        else None
    )
    if mission_status in {"manual_control"}:
        _penalise(8, "Mission control enforcing manual control over automation deployment.")
        prerequisites.append("Mission control must green-light deployment batch.")
    elif mission_status in {"paired_supervision", "supervised"}:
        _penalise(5, "Mission control requires paired supervision for rollout.")
    elif mission_status in {"mission_ready", "autonomous"}:
        _boost(3, "Mission control confirms readiness for deployment.")
    if isinstance(mission_score, (float, int)) and mission_score < 65:
        _penalise(4, "Mission control score trending low; increase oversight.")

    autonomy_status = str(autonomy.get("status", "")).lower()
    _register_window(
        autonomy.get("autonomy_window_hours")
        if isinstance(autonomy.get("autonomy_window_hours"), (float, int))
        else None
    )
    if autonomy_status in {"manual_only", "manual_guarded"}:
        _penalise(8, "Automation autonomy restricted to manual oversight.")
        prerequisites.append("Resolve autonomy guardrails before deployment.")
    elif autonomy_status in {"supervised"}:
        _penalise(4, "Automation autonomy still supervised; limit rollout scope.")
    elif autonomy_status in {"mission_ready", "autonomous_ready"}:
        _boost(3, "Automation autonomy cleared for extended deployment.")

    failsafe_status = str(failsafes.get("status", "")).lower()
    _register_window(
        failsafes.get("failsafe_window_hours")
        if isinstance(failsafes.get("failsafe_window_hours"), (float, int))
        else None
    )
    if failsafe_status in {"degraded", "manual"}:
        _penalise(6, "Failsafe posture degraded; keep deployment guarded.")
        watch_items.append("Failsafe drills pending before automation push.")
    elif failsafe_status in {"mission_ready", "reinforced"}:
        _boost(2, "Failsafe posture supports automation deployment.")

    validation_status = str(validation.get("status", "")).lower()
    _register_window(
        validation.get("validation_window_hours")
        if isinstance(validation.get("validation_window_hours"), (float, int))
        else None
    )
    if validation_status in {"manual_review", "hold"}:
        _penalise(7, "Validation requires manual review before deployment.")
        prerequisites.append("Complete automation validation checklist.")
        operator_prompts.append(
            "Завершіть валідаційний чекліст автоматизації перед включенням автономних режимів."
        )
    elif validation_status in {"mission_ready", "validated"}:
        _boost(3, "Validation track confirms automation quality for rollout.")

    readiness_level = str(readiness.get("level", "")).lower()
    _register_window(
        readiness.get("support_window_hours")
        if isinstance(readiness.get("support_window_hours"), (float, int))
        else None
    )
    if readiness_level == "critical":
        _penalise(9, "Response readiness critical; delay automation deployment.")
        prerequisites.append("Stabilise readiness posture before automation launch.")
        operator_prompts.append(
            "Підтягніть резервні зміни, щоб покрити автоматизовані потоки.")
    elif readiness_level in {"strained", "watch"}:
        _penalise(5, "Readiness strained; deployment requires close supervision.")
    elif readiness_level in {"steady", "reinforced"}:
        _boost(2, "Readiness staffing supports deployment windows.")

    pressure_status = str(pressure.get("status", "")).lower()
    _register_window(
        pressure.get("estimated_clearance_hours")
        if isinstance(pressure.get("estimated_clearance_hours"), (float, int))
        else None
    )
    if pressure_status == "critical_backlog":
        _penalise(7, "Critical backlog limits safe automation deployment.")
        watch_items.append("Clear analyst backlog before automating additional tracks.")
    elif pressure_status in {"backlog", "prediction_gap"}:
        _penalise(5, "Backlog active; stage deployment in waves with analyst pairing.")
    elif pressure_status in {"steady", "cleared"}:
        _boost(2, "Pressure low; automation can extend coverage cautiously.")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"mobilise", "critical"}:
        _penalise(6, "Frontline support mobilising; coordinate deployment with brigades.")
        operator_prompts.append(
            "Попередьте офіцерів підтримки бригад про автоматизовані оновлення і запити."
        )
        watch_items.append("Brigade liaison confirmation required before automation publish.")
    elif frontline_status in {"reinforce", "watch"}:
        _penalise(3, "Frontline posture sensitive; maintain human confirmation for key flows.")

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "accelerate"}:
        _penalise(4, "Sustainment surge constrains automation logistics support.")

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "critical"}:
        _penalise(4, "Support priorities elevated; automation deployment requires coordination.")

    governance_score = governance.get("governance_score")
    if isinstance(governance_score, (float, int)) and governance_score < 60:
        _penalise(4, "Governance cadence weak; document deployment approvals.")
        prerequisites.append("Record deployment decision in governance tracker.")

    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)) and assurance_score < 60:
        _penalise(4, "Mission assurance strained; leadership review required.")

    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)) and resilience_score < 60:
        _penalise(3, "Operational resilience vulnerable; keep deployment narrow.")

    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)) and continuity_score < 60:
        _penalise(3, "Continuity constraints limit automation windows.")

    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)) and recovery_score < 60:
        _penalise(3, "Recovery roadmap stabilising; roll out automation gradually.")

    transform_score = transformation.get("transformation_score")
    if isinstance(transform_score, (float, int)):
        if transform_score >= 78:
            _boost(3, "Transformation agenda enables automation deployment scale.")
        elif transform_score < 55:
            _penalise(3, "Transformation maturity low; deployment demands phased adoption.")

    directive_status = str(directives.get("status", "")).lower()
    if directive_status in {"escalate", "crisis"}:
        _penalise(6, "Command directives escalated; coordinate deployment with leadership.")
        _extend_actions(directives.get("recommended_actions"))
    elif directive_status in {"synchronise", "stabilise"}:
        _boost(2, "Command directives aligned to automation rollout.")

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status in {"misaligned", "drift", "at_risk"}:
        _penalise(5, "Command alignment gaps require deployment pause.")
        watch_items.append("Resolve command alignment gaps before automation run.")

    communication_status = str(communication.get("status", "")).lower()
    if communication_status in {"crisis", "escalated"}:
        _penalise(4, "Communication cadence in crisis; brief stakeholders manually.")
    elif communication_status in {"focused", "steady"}:
        _boost(2, "Communication cadence ready to broadcast automation outputs.")

    escalation_status = str(escalation.get("status", "")).lower()
    _register_window(
        escalation.get("next_review_hours")
        if isinstance(escalation.get("next_review_hours"), (float, int))
        else None
    )
    if escalation_status in {"escalate", "heightened", "review"}:
        _penalise(3, "Escalation matrix active; embed manual review gates.")

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(6, "Telemetry confidence low; deployment must remain guarded.")
        prerequisites.append("Run confidence restoration plan before automation deployment.")
    elif confidence_level in {"guarded"}:
        _penalise(3, "Telemetry confidence guarded; keep sampling automation outputs.")
    elif confidence_level in {"strong", "high"}:
        _boost(2, "Telemetry confidence supports deployment checks.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.62:
        _penalise(4, "Detection confidence below 0.62; embed analyst review in rollout.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        minutes = feed_info.get("age_minutes")
        if isinstance(minutes, (float, int)) and minutes > 0:
            _register_window(minutes / 60)
        if status == "stale":
            _penalise(5, f"{str(feed_name).title()} feed stale; pause automation outputs.")
            watch_items.append(f"Refresh {str(feed_name).title()} feed before deployment.")
        elif status == "warning":
            _penalise(3, f"{str(feed_name).title()} feed ageing; tighten monitoring.")

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity_label = str(gap.get("severity", "")).lower()
        description = gap.get("description") or gap.get("name") or gap.get("detail")
        if severity_label == "critical":
            _penalise(6, f"Critical intelligence gap: {description or 'Gap'}")
        elif severity_label in {"major", "high"}:
            _penalise(4, f"Major intelligence gap: {description or 'Gap'}")

    tempo = str(activity.get("tempo", "")).lower()
    if tempo == "surge":
        _penalise(4, "Operational tempo surging; stagger automation rollout.")
    elif tempo == "elevated":
        _penalise(2, "Operational tempo elevated; keep deployment in phases.")
    elif tempo in {"steady"}:
        _boost(1.5, "Operational tempo steady for automation adoption.")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy >= 0.8:
        _boost(2, "Feedback accuracy strong; trust automation models with monitoring.")
    elif isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.65:
        _penalise(4, "Feedback accuracy below 0.65; hold broad deployment.")

    actions.extend(
        [
            "Coordinate an automation deployment briefing with the Ukrainian duty automation officer.",
            "Publish deployment readiness notes on the mission control channel.",
        ]
    )

    operator_prompts.append(
        "Після кожного автоматизованого релізу підтверджуйте стан каналів та журналюйте рішення."
    )

    def _dedupe_strings(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            if not value:
                continue
            text = str(value)
            if text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    def _dedupe_tracks(values: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[Tuple[Any, ...]] = set()
        ordered: List[Dict[str, Any]] = []
        for entry in values:
            if not isinstance(entry, dict):
                continue
            key = (
                entry.get("name"),
                entry.get("owner"),
                entry.get("readiness"),
                entry.get("window_hours"),
            )
            if key in seen:
                continue
            seen.add(key)
            ordered.append(entry)
        return ordered

    drivers = _dedupe_strings(drivers)
    blockers = _dedupe_strings(blockers)
    prerequisites = _dedupe_strings(prerequisites)
    watch_items = _dedupe_strings(watch_items)
    actions = _dedupe_strings(actions)
    operator_prompts = _dedupe_strings(operator_prompts)
    deployment_tracks = _dedupe_tracks(deployment_tracks)

    deployment_window: Optional[float] = None
    if windows:
        positive = [value for value in windows if value > 0]
        if positive:
            deployment_window = round(min(positive), 2)

    status = "staged"
    if severity >= 26 or score < 50:
        status = "manual_override"
    elif severity >= 18 or score < 60:
        status = "hold"
    elif severity >= 12 or score < 72:
        status = "guarded"
    elif score >= 90 and severity <= 8:
        status = "ready"

    payload: Dict[str, Any] = {
        "status": status,
        "deployment_score": round(score, 1),
    }
    if severity > 0:
        payload["severity_index"] = severity
    if deployment_window is not None:
        payload["deployment_window_hours"] = deployment_window
    if deployment_tracks:
        payload["deployment_tracks"] = deployment_tracks
    if drivers:
        payload["drivers"] = drivers
    if blockers:
        payload["blockers"] = blockers
    if prerequisites:
        payload["prerequisites"] = prerequisites
    if watch_items:
        payload["watch_items"] = watch_items
    if actions:
        payload["recommended_actions"] = actions
    if operator_prompts:
        payload["ukrainian_operator_prompts"] = operator_prompts

    return payload if payload else None


def _derive_automation_failsafes(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evaluate automation failsafe coverage for Ukrainian operators."""

    automation = brief.get("automation_playbook") or {}
    guardrails = brief.get("automation_guardrails") or {}
    mission_control = brief.get("automation_mission_control") or {}
    autonomy = brief.get("automation_autonomy") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    frontline = brief.get("frontline_support") or {}
    sustainment = brief.get("resource_sustainment") or {}
    support = brief.get("support_priorities") or {}
    governance = brief.get("operational_governance") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    communication = brief.get("communication_plan") or {}
    directives = brief.get("command_directives") or {}
    escalation = brief.get("escalation_readiness") or {}
    confidence = brief.get("intelligence_confidence") or {}
    detection_quality = brief.get("detection_quality") or {}
    freshness = brief.get("data_freshness") or {}
    risks = brief.get("operational_risks") or {}
    gaps = brief.get("intelligence_gaps") or []
    meta = brief.get("meta") or {}

    if not any(
        [
            automation,
            guardrails,
            mission_control,
            autonomy,
            readiness,
            pressure,
            frontline,
            sustainment,
            support,
            governance,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            communication,
            directives,
            escalation,
            confidence,
            detection_quality,
            freshness,
            risks,
            gaps,
            meta,
        ]
    ):
        return None

    score = 88.0
    severity = 0
    failsafe_measures: List[str] = []
    fallback_channels: List[str] = []
    recovery_steps: List[str] = []
    recommended_actions: List[str] = []
    ukrainian_prompts: List[str] = []
    failsafe_tests: List[str] = []
    watch_items: List[str] = []
    coverage_gaps: List[str] = []
    windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            watch_items.append(str(note))

    def _boost(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            failsafe_measures.append(str(note))

    def _collect(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if not value:
                continue
            target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    guardrail_status = str(guardrails.get("status", "")).lower()
    _register_window(
        guardrails.get("next_review_hours")
        if isinstance(guardrails.get("next_review_hours"), (float, int))
        else None
    )
    if guardrail_status in {"locked_down", "manual_override", "manual_guarded"}:
        _penalise(12, "Guardrails locked down: execute manual failsafe confirmations.")
        recommended_actions.append("Route automation overrides through duty officer failsafe log.")
        ukrainian_prompts.append("Фіксуйте кожен аварійний оверрайд у журналі чергового офіцера.")
    elif guardrail_status in {"guided", "pilot"}:
        _penalise(6, "Guardrails guided: confirm failsafe observers remain on shift.")
    elif guardrail_status in {"autonomous", "steady"}:
        _boost(4, "Guardrails steady with documented shutdown scripts.")

    _collect(guardrails.get("monitoring_channels"), fallback_channels)
    _collect(guardrails.get("critical_guardrails"), failsafe_measures)

    mission_status = str(mission_control.get("status", "")).lower()
    _register_window(
        mission_control.get("next_sync_hours")
        if isinstance(mission_control.get("next_sync_hours"), (float, int))
        else None
    )
    if mission_status in {"manual_control", "paired_supervision"}:
        _penalise(8, "Mission control supervising automation handoffs.")
        recovery_steps.append("Mission control must authorise failsafe activations each sync.")
    elif mission_status in {"supervised"}:
        _penalise(4, "Mission control supervising: maintain audit trail of failsafe drills.")
    elif mission_status in {"mission_ready"}:
        _boost(3, "Mission control ready to orchestrate failsafe playbook.")

    automation_status = str(automation.get("status", "")).lower()
    if automation_status in {"manual_override", "manual_guarded"}:
        _penalise(8, "Automation running in manual override mode.")
        recovery_steps.append("Keep automation in manual mode until failsafe checklist clears.")
    elif automation_status in {"autonomous", "steady"}:
        _boost(2, "Automation stable: verify failsafe cadence remains aligned.")

    autonomy_status = str((autonomy or {}).get("status", "")).lower()
    _register_window(
        autonomy.get("autonomy_window_hours")
        if isinstance(autonomy.get("autonomy_window_hours"), (float, int))
        else None
    )
    if autonomy_status in {"manual_control", "paired_supervision"}:
        _penalise(6, "Autonomy constrained; prepare manual fallback procedures.")
    elif autonomy_status in {"mission_ready"}:
        _boost(3, "Autonomy mission ready with trusted task roster.")

    readiness_level = str(readiness.get("level", "")).lower()
    _register_window(
        readiness.get("support_window_hours")
        if isinstance(readiness.get("support_window_hours"), (float, int))
        else None
    )
    if readiness_level == "critical":
        _penalise(10, "Readiness critical: failsafes require dual confirmation.")
        recommended_actions.append("Stage manual battle drills before launching automation batches.")
        ukrainian_prompts.append("Перед запуском автоматизації проведіть ручне тренування аварійного зупину.")
    elif readiness_level == "strained":
        _penalise(6, "Readiness strained: limit unattended automation windows.")
    elif readiness_level in {"steady", "reinforced"}:
        _boost(3, "Readiness steady: teams available for failsafe drills.")

    pressure_status = str(pressure.get("status", "")).lower()
    _register_window(
        pressure.get("estimated_clearance_hours")
        if isinstance(pressure.get("estimated_clearance_hours"), (float, int))
        else None
    )
    if pressure_status == "critical_backlog":
        _penalise(9, "Critical backlog: failsafe actions compete with analyst capacity.")
        recommended_actions.append("Assign dedicated failsafe sentinel during backlog surges.")
    elif pressure_status in {"backlog", "prediction_gap", "prediction_gap_watch"}:
        _penalise(5, "Backlog present: ensure automation failsafes do not add latency.")
    elif pressure_status in {"steady", "cleared"}:
        _boost(2, "Pressure steady: analysts can rehearse failsafe switchovers.")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"mobilise", "critical"}:
        _penalise(5, "Frontline mobilising: coordinate failsafes with brigade liaisons.")
        ukrainian_prompts.append("Повідомте офіцера зв'язку бригади про сценарії аварійної зупинки.")

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "accelerate"}:
        _penalise(4, "Sustainment surge: protect logistics automation with manual fallbacks.")

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "reinforce"}:
        _penalise(4, "Support priorities elevated: keep human confirmation on failsafe triggers.")

    gov_score = governance.get("governance_score")
    if isinstance(gov_score, (float, int)):
        if gov_score < 60:
            _penalise(6, "Governance cadence weak: document failsafe handoffs.")
            recommended_actions.append("Log failsafe reviews in governance tracker after each drill.")
        elif gov_score >= 75:
            _boost(3, "Governance councils validating failsafe posture.")

    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)):
        if assurance_score < 60:
            _penalise(4, "Mission assurance low: limit unattended automation.")
        elif assurance_score >= 75:
            _boost(2, "Mission assurance strengthening failsafe readiness.")

    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)):
        if resilience_score < 60:
            _penalise(4, "Operational resilience fragile: rehearse manual recovery paths.")
        elif resilience_score >= 75:
            _boost(3, "Resilience strong: redundancy supports automation failsafes.")

    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)):
        if continuity_score < 60:
            _penalise(4, "Continuity constraints: confirm fallback workstations and power.")
        elif continuity_score >= 75:
            _boost(2, "Continuity steady: redundant systems available for failover.")

    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)) and recovery_score < 60:
        _penalise(3, "Recovery roadmap stabilising: track failsafe dependencies closely.")

    transform_score = transformation.get("transformation_score")
    if isinstance(transform_score, (float, int)) and transform_score >= 75:
        _boost(2, "Transformation agenda maturing automation recovery drills.")

    directive_status = str(directives.get("status", "")).lower()
    if directive_status in {"escalate", "crisis"}:
        _penalise(6, "Command directives elevated: failsafe readiness brief required.")
        recommended_actions.append("Brief Ukrainian command on automation failsafe posture.")

    comm_status = str(communication.get("status", "")).lower()
    if comm_status in {"crisis", "escalated"}:
        _penalise(4, "Communications escalated: align failsafe messaging with comms cell.")

    escalation_status = str(escalation.get("status", "")).lower()
    _register_window(
        escalation.get("next_review_hours")
        if isinstance(escalation.get("next_review_hours"), (float, int))
        else None
    )
    if escalation_status in {"escalate", "review", "heightened"}:
        _penalise(4, "Escalation pathways active: confirm failsafe triggers and alerting.")

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(7, "Telemetry confidence low: enforce dual-channel verification.")
        failsafe_tests.append("Run dual-channel validation on automated outputs every 30 minutes.")
    elif confidence_level == "guarded":
        _penalise(4, "Telemetry confidence guarded: maintain manual sampling.")
    elif confidence_level in {"high", "strong"}:
        _boost(2, "Telemetry confidence high: expand automated health checks.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.55:
        _penalise(6, "Detection confidence below 0.55: lock failsafe sampling gates.")
        failsafe_tests.append("Hold analyst review of low-confidence detection batches before release.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        minutes = feed_info.get("age_minutes")
        if isinstance(minutes, (float, int)):
            _register_window(minutes / 60 if minutes > 0 else None)
        if status == "stale":
            _penalise(8, f"{str(feed_name).title()} feed stale: switch automation to manual mode.")
            coverage_gaps.append(f"{str(feed_name).title()} feed stale")
            recommended_actions.append(
                f"Pause unattended automation on {str(feed_name).title()} feed until refreshed."
            )
        elif status == "warning":
            _penalise(4, f"{str(feed_name).title()} feed ageing: rehearse failsafe fallback.")

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity_label = str(gap.get("severity", "")).lower()
        description = gap.get("name") or gap.get("description") or gap.get("detail")
        if severity_label == "critical":
            _penalise(7, f"Critical intelligence gap: {description or 'Gap'}")
            coverage_gaps.append(f"Critical gap: {description or 'Gap'}")
        elif severity_label in {"major", "high"}:
            _penalise(5, f"Major intelligence gap: {description or 'Gap'}")

    severity_score = risks.get("severity_score")
    if isinstance(severity_score, (float, int)) and severity_score >= 80:
        _penalise(5, "Operational risk register elevated: rehearse full automation shutdown.")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.65:
        _penalise(4, "Feedback accuracy under 0.65: tighten failsafe approvals.")

    _collect(automation.get("automation_tracks"), failsafe_measures)
    _collect(mission_control.get("automation_tracks"), failsafe_measures)
    _collect(mission_control.get("mission_channels"), fallback_channels)

    for allocation in sustainment.get("allocation_plan", []) or []:
        if not isinstance(allocation, dict):
            continue
        resource = allocation.get("resource") or allocation.get("name")
        focus = allocation.get("focus")
        window = allocation.get("window_hours")
        descriptor = resource or "Resupply package"
        if focus:
            descriptor = f"{descriptor} → {focus}"
        if isinstance(window, (float, int)) and window > 0:
            descriptor = f"{descriptor} ({float(window):.1f}h)"
        recovery_steps.append(f"Prepare manual resupply fallback for {descriptor}.")

    for priority in support.get("priorities", []) or []:
        if not isinstance(priority, dict):
            continue
        unit = priority.get("name") or priority.get("unit")
        focus = priority.get("focus")
        window = priority.get("support_window_hours")
        descriptor = unit or "Support priority"
        if focus:
            descriptor = f"{descriptor} → {focus}"
        if isinstance(window, (float, int)) and window > 0:
            descriptor = f"{descriptor} ({float(window):.1f}h)"
        recovery_steps.append(f"Coordinate support fallback cover for {descriptor}.")

    # Ensure default guidance for Ukrainian operators
    recommended_actions.append("Conduct a Ukrainian-language failsafe drill at start of shift.")
    ukrainian_prompts.append("Наготуйте резервні канали зв'язку на випадок відмови автоматизації.")

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    failsafe_measures = _dedupe(failsafe_measures)
    fallback_channels = _dedupe(fallback_channels)
    recovery_steps = _dedupe(recovery_steps)
    recommended_actions = _dedupe(recommended_actions)
    ukrainian_prompts = _dedupe(ukrainian_prompts)
    failsafe_tests = _dedupe(failsafe_tests)
    watch_items = _dedupe(watch_items)
    coverage_gaps = _dedupe(coverage_gaps)

    failsafe_window: Optional[float] = None
    if windows:
        positive = [value for value in windows if value > 0]
        if positive:
            failsafe_window = round(min(positive), 2)

    status = "secured"
    if severity >= 24 or score < 55:
        status = "manual_recovery"
    elif severity >= 16 or score < 65:
        status = "at_risk"
    elif severity >= 8 or score < 75:
        status = "watch"

    payload: Dict[str, Any] = {
        "status": status,
        "failsafe_score": round(score, 1),
    }
    if failsafe_window is not None:
        payload["failsafe_window_hours"] = failsafe_window
    if failsafe_measures:
        payload["failsafe_measures"] = failsafe_measures
    if fallback_channels:
        payload["fallback_channels"] = fallback_channels
    if recovery_steps:
        payload["recovery_steps"] = recovery_steps
    if recommended_actions:
        payload["recommended_actions"] = recommended_actions
    if ukrainian_prompts:
        payload["ukrainian_operator_prompts"] = ukrainian_prompts
    if failsafe_tests:
        payload["failsafe_tests"] = failsafe_tests
    if watch_items:
        payload["watch_items"] = watch_items
    if coverage_gaps:
        payload["coverage_gaps"] = coverage_gaps

    return payload if payload else None


def _derive_automation_validation(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate automation execution discipline for Ukrainian operators."""

    automation = brief.get("automation_playbook") or {}
    guardrails = brief.get("automation_guardrails") or {}
    mission_control = brief.get("automation_mission_control") or {}
    autonomy = brief.get("automation_autonomy") or {}
    failsafes = brief.get("automation_failsafes") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    frontline = brief.get("frontline_support") or {}
    sustainment = brief.get("resource_sustainment") or {}
    support = brief.get("support_priorities") or {}
    governance = brief.get("operational_governance") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    confidence = brief.get("intelligence_confidence") or {}
    detection_quality = brief.get("detection_quality") or {}
    freshness = brief.get("data_freshness") or {}
    gaps = brief.get("intelligence_gaps") or []
    meta = brief.get("meta") or {}

    if not any(
        [
            automation,
            guardrails,
            mission_control,
            autonomy,
            failsafes,
            readiness,
            pressure,
            frontline,
            sustainment,
            support,
            governance,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            confidence,
            detection_quality,
            freshness,
            gaps,
            meta,
        ]
    ):
        return None

    score = 90.0
    severity = 0
    validation_tracks: List[str] = []
    test_matrix: List[str] = []
    training_requirements: List[str] = []
    ukrainian_prompts: List[str] = []
    watch_items: List[str] = []
    recommended_actions: List[str] = []
    evidence: List[str] = []
    windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            watch_items.append(str(note))

    def _boost(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            validation_tracks.append(str(note))

    def _collect(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if not value:
                continue
            target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    automation_status = str(automation.get("status", "")).lower()
    if automation_status in {"manual_override", "manual"}:
        _penalise(12, "Automation playbook is in manual override; validation halted.")
        training_requirements.append("Rehearse automation scenarios with duty officer oversight.")
    elif automation_status in {"guided", "pilot"}:
        _penalise(6, "Automation playbook requires guided execution.")
        training_requirements.append("Assign mission control to supervise guided automation batches.")
    elif automation_status in {"autonomous", "steady"}:
        _boost(4, "Automation playbook approved for autonomous execution.")

    _collect(automation.get("automation_tracks"), validation_tracks)
    _collect(automation.get("recommended_actions"), recommended_actions)
    _collect(automation.get("monitoring_channels"), evidence)
    _register_window(
        automation.get("automation_window_hours")
        if isinstance(automation.get("automation_window_hours"), (float, int))
        else None
    )

    guardrail_status = str(guardrails.get("status", "")).lower()
    _register_window(
        guardrails.get("next_review_hours")
        if isinstance(guardrails.get("next_review_hours"), (float, int))
        else None
    )
    if guardrail_status in {"locked_down", "manual_override", "manual_guarded"}:
        _penalise(8, "Automation guardrails locked down; validation cannot sign off.")
        training_requirements.append("Complete guardrail reset drill before approving automation runs.")
    elif guardrail_status in {"guided", "pilot"}:
        _penalise(4, "Automation guardrails require guided checks.")
    elif guardrail_status in {"autonomous", "steady"}:
        _boost(3, "Automation guardrails stable with documented reviews.")

    _collect(guardrails.get("monitoring_channels"), evidence)
    _collect(guardrails.get("guardrails"), test_matrix)

    mission_status = str(mission_control.get("status", "")).lower()
    _register_window(
        mission_control.get("next_sync_hours")
        if isinstance(mission_control.get("next_sync_hours"), (float, int))
        else None
    )
    if mission_status in {"manual_control", "paired_supervision"}:
        _penalise(8, "Mission control supervising automation manually.")
        recommended_actions.append("Log manual supervision outcomes in the automation validation journal.")
    elif mission_status in {"mission_ready", "coordinated"}:
        _boost(3, "Mission control aligned for automation oversight.")

    _collect(mission_control.get("mission_channels"), evidence)
    _collect(mission_control.get("recommended_actions"), recommended_actions)

    autonomy_status = str(autonomy.get("status", "")).lower()
    _register_window(
        autonomy.get("autonomy_window_hours")
        if isinstance(autonomy.get("autonomy_window_hours"), (float, int))
        else None
    )
    if autonomy_status in {"manual_control", "manual_guarded"}:
        _penalise(7, "Automation autonomy requires manual control.")
        training_requirements.append("Deliver autonomy refresher briefing before expanding windows.")
    elif autonomy_status in {"mission_ready", "autonomous_ready"}:
        _boost(3, "Automation autonomy cleared for mission-ready tasks.")

    failsafe_status = str(failsafes.get("status", "")).lower()
    _register_window(
        failsafes.get("failsafe_window_hours")
        if isinstance(failsafes.get("failsafe_window_hours"), (float, int))
        else None
    )
    if failsafe_status in {"manual_recovery", "at_risk"}:
        _penalise(6, "Automation failsafes require manual intervention.")
        training_requirements.append("Run bilingual failsafe drill before approving automation shifts.")
    elif failsafe_status in {"secured"}:
        _boost(2, "Automation failsafes rehearsed and secured.")

    readiness_level = str(readiness.get("level", "")).lower()
    _register_window(
        readiness.get("support_window_hours")
        if isinstance(readiness.get("support_window_hours"), (float, int))
        else None
    )
    if readiness_level in {"critical", "degraded"}:
        _penalise(9, "Response readiness critical; automation validation paused.")
        training_requirements.append("Stabilise readiness roster before trusting automation runs.")
    elif readiness_level in {"strained", "guarded"}:
        _penalise(4, "Readiness strained; pair automation with supervisors.")
    elif readiness_level in {"reinforced", "stable"}:
        _boost(3, "Response readiness reinforced for automation validation.")

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "severe"}:
        _penalise(8, "Analyst backlog critical; automation validation must throttle releases.")
        recommended_actions.append("Throttle automation release cadence until backlog clears.")
    elif pressure_status in {"queue_forming", "elevated"}:
        _penalise(4, "Analyst backlog forming; tighten automation checks.")
    elif pressure_status in {"cleared", "balanced"}:
        _boost(2, "Analyst queues cleared; validation cadence can continue.")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"critical", "mobilising"}:
        _penalise(5, "Frontline support mobilising; validation requires brigade sign-off.")
        training_requirements.append("Coordinate frontline rehearsal for automation alerts.")
    elif frontline_status in {"supported", "stable"}:
        _boost(2, "Frontline support steady for automation deployment.")

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"strained", "critical"}:
        _penalise(4, "Sustainment strained; validate logistics automations manually.")
    elif sustainment_status in {"steady", "reinforced"}:
        _boost(2, "Sustainment steady; logistics automations cleared for validation.")

    support_priorities = support.get("priorities") if isinstance(support, dict) else None
    if isinstance(support_priorities, list):
        for priority in support_priorities:
            if not isinstance(priority, dict):
                continue
            focus = priority.get("focus") or priority.get("objective")
            unit = priority.get("name") or priority.get("unit")
            window = priority.get("support_window_hours")
            descriptor = unit or "Support priority"
            if focus:
                descriptor = f"{descriptor} → {focus}"
            if isinstance(window, (float, int)) and window > 0:
                descriptor = f"{descriptor} ({float(window):.1f}h)"
                _register_window(window)
            validation_tracks.append(f"Support coordination: {descriptor}")

    governance_status = str(governance.get("status", "")).lower()
    governance_score = governance.get("governance_score")
    if governance_status in {"strained", "delayed"}:
        _penalise(5, "Governance cadence delayed; document validation approvals.")
    if isinstance(governance_score, (float, int)):
        if governance_score < 60:
            _penalise(4, "Governance oversight below threshold for automation sign-off.")
        elif governance_score >= 80:
            _boost(2, "Governance cadence aligned with automation validation.")

    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)):
        if assurance_score < 60:
            _penalise(3, "Mission assurance strained; log automation validation decisions.")
        elif assurance_score >= 80:
            _boost(2, "Mission assurance backing automation validation results.")

    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)):
        if resilience_score < 60:
            _penalise(3, "Operational resilience fragile; expand manual validation sampling.")
        elif resilience_score >= 80:
            _boost(2, "Operational resilience supports automation testing.")

    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)):
        if continuity_score < 60:
            _penalise(3, "Continuity constraints limit unattended automation validation.")
        elif continuity_score >= 80:
            _boost(2, "Continuity protections cover automation validation drills.")

    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)) and recovery_score < 60:
        _penalise(2, "Recovery roadmap stabilising; add recovery checks to validation.")

    transform_score = transformation.get("transformation_score")
    if isinstance(transform_score, (float, int)):
        if transform_score >= 80:
            _boost(3, "Transformation tracks accelerating automation maturity.")
        elif transform_score < 60:
            _penalise(3, "Transformation maturity low; schedule automation upskilling.")

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(7, "Telemetry confidence low; validation must escalate sampling.")
        test_matrix.append("Double-sample automated outputs until telemetry stabilises.")
    elif confidence_level == "guarded":
        _penalise(4, "Telemetry confidence guarded; maintain validation pairing.")
    elif confidence_level in {"high", "strong"}:
        _boost(2, "Telemetry confidence high; validation cadence can widen.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        _penalise(5, "Detection confidence below 0.6; enforce manual validation.")
        test_matrix.append("Review low-confidence detection classes before automation publish.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        minutes = feed_info.get("age_minutes")
        if isinstance(minutes, (float, int)) and minutes > 0:
            _register_window(minutes / 60)
        if status == "stale":
            _penalise(6, f"{str(feed_name).title()} feed stale; validation requires manual checks.")
            test_matrix.append(f"Stale feed: {str(feed_name).title()} requires manual verification.")
        elif status == "warning":
            _penalise(3, f"{str(feed_name).title()} feed ageing; tighten validation sampling.")

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity_label = str(gap.get("severity", "")).lower()
        description = gap.get("name") or gap.get("description") or gap.get("detail")
        if severity_label == "critical":
            _penalise(6, f"Critical intelligence gap blocking automation validation: {description or 'Gap'}")
        elif severity_label in {"major", "high"}:
            _penalise(4, f"Major intelligence gap impacting automation validation: {description or 'Gap'}")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.65:
        _penalise(4, "Feedback accuracy under 0.65; require analyst sign-off on automation.")
    elif isinstance(feedback_accuracy, (float, int)) and feedback_accuracy >= 0.85:
        _boost(2, "Feedback accuracy high; automation validation has trusted samples.")

    for allocation in sustainment.get("allocation_plan", []) or []:
        if not isinstance(allocation, dict):
            continue
        resource = allocation.get("resource") or allocation.get("name")
        window = allocation.get("window_hours")
        if isinstance(window, (float, int)) and window > 0:
            _register_window(window)
        if resource:
            evidence.append(f"Sustainment prepared: {resource}")

    _collect(failsafes.get("failsafe_tests"), test_matrix)
    _collect(failsafes.get("recommended_actions"), recommended_actions)
    _collect(failsafes.get("fallback_channels"), evidence)

    ukrainian_prompts.append(
        "Переконайтеся, що автоматизовані сценарії мають актуальні тести та журнали українською мовою."
    )
    ukrainian_prompts.append("Погоджуйте випуски автоматизації з черговим офіцером штабу перед запуском.")
    recommended_actions.append("Publish automation validation summary to the Ukrainian operations board.")

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    validation_tracks = _dedupe(validation_tracks)
    test_matrix = _dedupe(test_matrix)
    training_requirements = _dedupe(training_requirements)
    ukrainian_prompts = _dedupe(ukrainian_prompts)
    watch_items = _dedupe(watch_items)
    recommended_actions = _dedupe(recommended_actions)
    evidence = _dedupe(evidence)

    validation_window: Optional[float] = None
    if windows:
        positive = [value for value in windows if value > 0]
        if positive:
            validation_window = round(min(positive), 2)

    status = "validated"
    if severity >= 26 or score < 55:
        status = "manual_validation"
    elif severity >= 18 or score < 65:
        status = "guarded"
    elif severity >= 10 or score < 75:
        status = "watch"
    elif score >= 88 and severity <= 6:
        status = "mission_ready"

    payload: Dict[str, Any] = {
        "status": status,
        "validation_score": round(score, 1),
    }
    if validation_window is not None:
        payload["validation_window_hours"] = validation_window
    if validation_tracks:
        payload["validation_tracks"] = validation_tracks
    if test_matrix:
        payload["test_matrix"] = test_matrix
    if training_requirements:
        payload["training_requirements"] = training_requirements
    if ukrainian_prompts:
        payload["ukrainian_operator_prompts"] = ukrainian_prompts
    if watch_items:
        payload["watch_items"] = watch_items
    if recommended_actions:
        payload["recommended_actions"] = recommended_actions
    if evidence:
        payload["validation_evidence"] = evidence

    return payload if payload else None


def _derive_automation_overwatch(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Assess automation overwatch coverage for Ukrainian ops centres."""

    automation = brief.get("automation_playbook") or {}
    guardrails = brief.get("automation_guardrails") or {}
    mission_control = brief.get("automation_mission_control") or {}
    autonomy = brief.get("automation_autonomy") or {}
    failsafes = brief.get("automation_failsafes") or {}
    validation = brief.get("automation_validation") or {}
    deployment = brief.get("automation_deployment") or {}
    frontline = brief.get("frontline_support") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    sustainment = brief.get("resource_sustainment") or {}
    support = brief.get("support_priorities") or {}
    governance = brief.get("operational_governance") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    directives = brief.get("command_directives") or {}
    alignment = brief.get("command_alignment") or {}
    communication = brief.get("communication_plan") or {}
    escalation = brief.get("escalation_readiness") or {}
    confidence = brief.get("intelligence_confidence") or {}
    detection_quality = brief.get("detection_quality") or {}
    freshness = brief.get("data_freshness") or {}
    gaps = brief.get("intelligence_gaps") or []
    risks = brief.get("operational_risks") or {}
    meta = brief.get("meta") or {}

    if not any(
        [
            automation,
            guardrails,
            mission_control,
            autonomy,
            failsafes,
            validation,
            deployment,
            frontline,
            readiness,
            pressure,
            sustainment,
            support,
            governance,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            directives,
            alignment,
            communication,
            escalation,
            confidence,
            detection_quality,
            freshness,
            gaps,
            risks,
            meta,
        ]
    ):
        return None

    score = 88.0
    severity = 0
    watch_teams: List[str] = []
    monitoring_channels: List[str] = []
    oversight_focus: List[str] = []
    watch_items: List[str] = []
    actions: List[str] = []
    prompts: List[str] = []
    fallback_channels: List[str] = []
    windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount) * 1.2)
        if note:
            watch_items.append(str(note))

    def _boost(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            oversight_focus.append(str(note))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    def _collect(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if value:
                target.append(str(value))

    mission_status = str(mission_control.get("status", "")).lower()
    mission_score = mission_control.get("mission_control_score")
    _register_window(
        mission_control.get("next_sync_hours")
        if isinstance(mission_control.get("next_sync_hours"), (float, int))
        else None
    )
    if mission_status in {"manual_control"}:
        _penalise(8, "Mission control enforcing manual oversight on automation outputs.")
        watch_teams.append("Automation Mission Control Cell")
    elif mission_status in {"paired_supervision", "supervised"}:
        _penalise(5, "Mission control requires paired supervision for automation runs.")
        watch_teams.append("Mission Control Supervisors")
    elif mission_status in {"mission_ready"}:
        _boost(3, "Mission control cadence supports proactive overwatch.")
    if isinstance(mission_score, (float, int)) and mission_score < 65:
        _penalise(3, "Mission control score trending low; increase overwatch staffing.")

    guardrail_status = str(guardrails.get("status", "")).lower()
    _register_window(
        guardrails.get("next_review_hours")
        if isinstance(guardrails.get("next_review_hours"), (float, int))
        else None
    )
    if guardrail_status in {"locked_down", "manual_override"}:
        _penalise(7, "Guardrails locked down; keep automation under manual watch.")
        watch_teams.append("Guardrail Safety Team")
        prompts.append("Зафіксуйте кожен оверрайд у журналі та повідомте чергового офіцера.")
    elif guardrail_status in {"guided", "pilot"}:
        _penalise(3, "Guardrails guided; maintain close overwatch on automation tasks.")
    elif guardrail_status in {"autonomous", "steady"}:
        _boost(2, "Guardrails steady; automation overwatch can focus on edge cases.")

    autonomy_status = str(autonomy.get("status", "")).lower()
    _register_window(
        autonomy.get("autonomy_window_hours")
        if isinstance(autonomy.get("autonomy_window_hours"), (float, int))
        else None
    )
    if autonomy_status in {"manual_only", "manual_guarded"}:
        _penalise(6, "Autonomy limited; human overwatch required for every release.")
        watch_teams.append("Automation Supervisors")
    elif autonomy_status in {"supervised"}:
        _penalise(3, "Autonomy supervised; maintain paired overwatch shifts.")
    elif autonomy_status in {"mission_ready", "autonomous_ready"}:
        _boost(3, "Autonomy cleared; focus overwatch on critical triggers.")

    failsafe_status = str(failsafes.get("status", "")).lower()
    _register_window(
        failsafes.get("failsafe_window_hours")
        if isinstance(failsafes.get("failsafe_window_hours"), (float, int))
        else None
    )
    if failsafe_status in {"degraded", "manual"}:
        _penalise(6, "Failsafe posture degraded; keep fallback channels manned.")
        fallback_channels.extend(failsafes.get("fallback_channels", []) or [])
        prompts.append("Перевірте резервні канали автоматизації кожні 30 хвилин.")
    elif failsafe_status in {"mission_ready", "reinforced"}:
        _boost(2, "Failsafe drills current; overwatch can widen automation windows.")

    validation_status = str(validation.get("status", "")).lower()
    _register_window(
        validation.get("validation_window_hours")
        if isinstance(validation.get("validation_window_hours"), (float, int))
        else None
    )
    if validation_status in {"manual_review", "hold"}:
        _penalise(6, "Validation pending manual review; slow down automation releases.")
        prompts.append("Переконайтесь, що валідаційні чеклісти підписані перед публікацією.")
    elif validation_status in {"mission_ready", "validated"}:
        _boost(3, "Validation cadence supports proactive overwatch.")

    deployment_status = str(deployment.get("status", "")).lower()
    _register_window(
        deployment.get("deployment_window_hours")
        if isinstance(deployment.get("deployment_window_hours"), (float, int))
        else None
    )
    if deployment_status in {"hold", "manual_override"}:
        _penalise(5, "Deployment on hold; maintain manual overwatch queues.")
    elif deployment_status in {"staged", "ready"}:
        _boost(2, "Deployment staged; coordinate overwatch with release windows.")

    readiness_level = str(readiness.get("level", "")).lower()
    _register_window(
        readiness.get("support_window_hours")
        if isinstance(readiness.get("support_window_hours"), (float, int))
        else None
    )
    if readiness_level == "critical":
        _penalise(8, "Readiness critical; automation overwatch must stay in manual mode.")
        watch_teams.append("Readiness Duty Cell")
        prompts.append("Залучіть резервного аналітика для спільного контролю автоматизації.")
    elif readiness_level in {"strained", "watch"}:
        _penalise(4, "Readiness strained; double-staff overwatch shifts.")
    elif readiness_level in {"steady", "reinforced"}:
        _boost(2, "Readiness stable; overwatch can widen monitoring intervals.")

    pressure_status = str(pressure.get("status", "")).lower()
    _register_window(
        pressure.get("estimated_clearance_hours")
        if isinstance(pressure.get("estimated_clearance_hours"), (float, int))
        else None
    )
    if pressure_status == "critical_backlog":
        _penalise(7, "Critical backlog; automation overwatch prioritises queue clearance.")
        watch_items.append("Clear analyst backlog before enabling autonomous runs.")
    elif pressure_status in {"backlog", "prediction_gap"}:
        _penalise(4, "Backlog active; keep overwatch paired with analysts.")
    elif pressure_status in {"steady", "cleared"}:
        _boost(2, "Pressure cleared; overwatch can focus on edge cases.")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"mobilise", "critical"}:
        _penalise(5, "Frontline mobilisation; sync automation overwatch with brigade liaisons.")
        watch_teams.append("Frontline Liaison Cell")
        prompts.append(
            "Сповістіть офіцерів фронтової підтримки про автоматизовані оновлення та сигнали."
        )

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "accelerate"}:
        _penalise(4, "Sustainment surge; track logistics dependencies inside overwatch logs.")

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "critical"}:
        _penalise(4, "Support priorities elevated; coordinate overwatch with support command.")

    governance_score = governance.get("governance_score")
    _register_window(
        governance.get("next_review_hours")
        if isinstance(governance.get("next_review_hours"), (float, int))
        else None
    )
    if isinstance(governance_score, (float, int)) and governance_score < 60:
        _penalise(4, "Governance cadence weak; log overwatch findings for council review.")

    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)) and assurance_score < 60:
        _penalise(4, "Mission assurance strained; leadership expects manual overwatch updates.")

    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)) and resilience_score < 60:
        _penalise(3, "Resilience vulnerable; prioritise continuity drills in overwatch.")

    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)) and continuity_score < 60:
        _penalise(3, "Continuity constraints limit unattended overwatch windows.")

    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)) and recovery_score < 60:
        _penalise(3, "Recovery tracks open; keep overwatch linked to stabilisation plans.")

    transform_score = transformation.get("transformation_score")
    if isinstance(transform_score, (float, int)):
        if transform_score >= 78:
            _boost(3, "Transformation tracks reinforce automation oversight maturity.")
        elif transform_score < 55:
            _penalise(2, "Transformation maturity low; document every overwatch decision.")

    directive_status = str(directives.get("status", "")).lower()
    if directive_status in {"escalate", "crisis"}:
        _penalise(5, "Command directives in crisis posture; provide overwatch briefs hourly.")
    _collect(directives.get("recommended_actions"), actions)

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status in {"misaligned", "drift", "at_risk"}:
        _penalise(4, "Command alignment drift; ensure overwatch sync with leadership intent.")
    _collect(alignment.get("recommended_actions"), actions)

    comm_status = str(communication.get("status", "")).lower()
    if comm_status in {"crisis", "escalated"}:
        _penalise(4, "Communication cadence escalated; mirror overwatch notes to comms cell.")
    _collect(communication.get("recommended_actions"), actions)

    escalation_status = str(escalation.get("status", "")).lower()
    if escalation_status in {"escalate", "review", "heightened"}:
        _penalise(3, "Escalation matrix active; keep overwatch triggers under review.")
    _register_window(
        escalation.get("next_review_hours")
        if isinstance(escalation.get("next_review_hours"), (float, int))
        else None
    )

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(6, "Telemetry confidence low; require analyst confirmation in overwatch.")
        prompts.append("Проводьте ручову перевірку кожного автоматизованого пакету даних.")
    elif confidence_level == "guarded":
        _penalise(3, "Telemetry confidence guarded; keep overwatch checks paired.")
    elif confidence_level in {"high", "strong"}:
        _boost(2, "Telemetry confidence high; focus overwatch on high-impact cues.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        _penalise(4, "Detection confidence under 0.6; cross-check automation outputs manually.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        age_minutes = feed_info.get("age_minutes")
        if isinstance(age_minutes, (float, int)) and age_minutes > 0:
            _register_window(age_minutes / 60.0)
        if status == "stale":
            _penalise(6, f"{str(feed_name).title()} feed stale; keep overwatch in manual mode.")
        elif status == "warning":
            _penalise(3, f"{str(feed_name).title()} feed ageing; shorten overwatch intervals.")

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity_label = str(gap.get("severity", "")).lower()
        description = gap.get("description") or gap.get("detail") or gap.get("name")
        if severity_label == "critical":
            _penalise(7, f"Critical intelligence gap: {description or 'Gap'}")
        elif severity_label in {"major", "high"}:
            _penalise(4, f"Major intelligence gap: {description or 'Gap'}")

    severity_score = risks.get("severity_score")
    if isinstance(severity_score, (float, int)) and severity_score >= 80:
        _penalise(4, "Operational risk register elevated; log overwatch escalations.")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.65:
        _penalise(4, "Feedback accuracy weak; require manual confirmation in overwatch.")

    _collect(mission_control.get("mission_channels"), monitoring_channels)
    _collect(mission_control.get("control_focus"), oversight_focus)
    _collect(mission_control.get("watch_items"), watch_items)
    _collect(mission_control.get("recommended_actions"), actions)
    _collect(guardrails.get("monitoring_channels"), monitoring_channels)
    _collect(guardrails.get("safety_checks"), actions)
    _collect(automation.get("monitoring_channels"), monitoring_channels)
    _collect(automation.get("triggers"), watch_items)
    _collect(automation.get("drivers"), oversight_focus)
    _collect(automation.get("recommended_actions"), actions)
    _collect(automation.get("automation_tracks"), oversight_focus)
    _collect(failsafes.get("recommended_actions"), actions)
    _collect(validation.get("recommended_actions"), actions)
    _collect(deployment.get("recommended_actions"), actions)

    fallback_channels.extend(guardrails.get("fallback_channels", []) or [])
    fallback_channels.extend(failsafes.get("fallback_channels", []) or [])

    if not watch_teams and (monitoring_channels or oversight_focus):
        watch_teams.append("Automation Overwatch Team")

    next_sync: Optional[float] = None
    if windows:
        positive = [value for value in windows if value > 0]
        if positive:
            next_sync = round(min(positive), 2)

    status = "mission_ready"
    if severity >= 20 or score < 60:
        status = "manual_watch"
    elif severity >= 14 or score < 70:
        status = "paired_watch"
    elif severity >= 8 or score < 80:
        status = "focused_watch"

    payload: Dict[str, Any] = {
        "status": status,
        "overwatch_score": round(score, 1),
    }
    if severity > 0:
        payload["severity_index"] = severity
    if next_sync is not None:
        payload["next_sync_hours"] = next_sync
    if watch_teams:
        payload["watch_teams"] = watch_teams
    if monitoring_channels:
        payload["monitoring_channels"] = sorted({channel for channel in monitoring_channels})
    if oversight_focus:
        payload["watch_focus"] = oversight_focus
    if watch_items:
        payload["watch_items"] = watch_items
    if fallback_channels:
        payload["fallback_channels"] = sorted({channel for channel in fallback_channels})
    if actions:
        payload["recommended_actions"] = actions
    if prompts:
        payload["ukrainian_watch_prompts"] = prompts

    return payload if payload else None


def _derive_automation_battle_management(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Coordinate automation battle management posture for Ukrainian operators."""

    automation = brief.get("automation_playbook") or {}
    guardrails = brief.get("automation_guardrails") or {}
    mission_control = brief.get("automation_mission_control") or {}
    overwatch = brief.get("automation_overwatch") or {}
    autonomy = brief.get("automation_autonomy") or {}
    failsafes = brief.get("automation_failsafes") or {}
    validation = brief.get("automation_validation") or {}
    deployment = brief.get("automation_deployment") or {}
    frontline = brief.get("frontline_support") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    sustainment = brief.get("resource_sustainment") or {}
    support = brief.get("support_priorities") or {}
    directives = brief.get("command_directives") or {}
    alignment = brief.get("command_alignment") or {}
    communication = brief.get("communication_plan") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    governance = brief.get("operational_governance") or {}
    escalation = brief.get("escalation_readiness") or {}
    confidence = brief.get("intelligence_confidence") or {}
    detection_quality = brief.get("detection_quality") or {}
    freshness = brief.get("data_freshness") or {}
    risks = brief.get("operational_risks") or {}
    outlook = brief.get("operational_outlook") or {}
    meta = brief.get("meta") or {}

    if not any(
        [
            automation,
            guardrails,
            mission_control,
            overwatch,
            autonomy,
            failsafes,
            validation,
            deployment,
            frontline,
            readiness,
            pressure,
            sustainment,
            support,
            directives,
            alignment,
            communication,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            governance,
            escalation,
            confidence,
            detection_quality,
            freshness,
            risks,
            outlook,
            meta,
        ]
    ):
        return None

    score = 87.0
    severity = 0
    drivers: List[str] = []
    focus_areas: List[str] = []
    watch_items: List[str] = []
    recommended_actions: List[str] = []
    prompts: List[str] = []
    battle_channels: List[str] = []
    integration_targets: List[str] = []
    priority_feeds: List[str] = []
    handoff_requirements: List[str] = []
    coordination_tracks: List[Dict[str, Any]] = []
    windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None, *, focus: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            watch_items.append(str(note))
        if focus:
            focus_areas.append(str(focus))

    def _boost(amount: float, note: Optional[str] = None, *, focus: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            drivers.append(str(note))
        if focus:
            focus_areas.append(str(focus))

    def _collect(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if value:
                target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    def _add_track(
        name: Optional[str],
        *,
        lead: Optional[str] = None,
        readiness_tag: Optional[str] = None,
        window: Optional[float] = None,
        status: Optional[str] = None,
    ) -> None:
        if not name:
            return
        track: Dict[str, Any] = {"name": str(name)}
        if lead:
            track["lead"] = str(lead)
        if readiness_tag:
            track["readiness"] = str(readiness_tag)
        if isinstance(window, (float, int)) and window > 0:
            track["window_hours"] = round(float(window), 2)
            _register_window(float(window))
        if status:
            track["status"] = str(status)
        coordination_tracks.append(track)

    mission_status = str(mission_control.get("status", "")).lower()
    mission_score = mission_control.get("mission_control_score")
    _register_window(
        mission_control.get("next_sync_hours")
        if isinstance(mission_control.get("next_sync_hours"), (float, int))
        else None
    )
    if mission_status in {"manual_control", "manual_bridge"}:
        _penalise(
            9,
            "Mission control is enforcing a manual bridge for automation battle management.",
            focus="Manual bridge",
        )
        handoff_requirements.append(
            "Mission control must sign off each automation battle package before release."
        )
        prompts.append(
            "Узгоджуйте кожне автоматизоване рішення з черговим офіцером місії."
        )
    elif mission_status in {"paired_supervision", "supervised", "paired_watch"}:
        _penalise(
            6,
            "Mission control requires paired supervision for automation battle tracks.",
            focus="Mission supervision",
        )
        handoff_requirements.append(
            "Pair duty analysts with mission control during automation battle runs."
        )
        prompts.append(
            "Призначте напарника для контролю автоматизованих бойових треків."
        )
    elif mission_status == "mission_ready":
        _boost(
            3,
            "Mission control cadence supports automation battle coordination windows.",
            focus="Mission coordination",
        )
    if isinstance(mission_score, (float, int)) and mission_score < 65:
        _penalise(4, "Mission control score trending low; log automation battle decisions.")
    _collect(mission_control.get("mission_channels"), battle_channels)
    _collect(mission_control.get("control_focus"), focus_areas)
    _collect(mission_control.get("watch_items"), watch_items)
    _collect(mission_control.get("recommended_actions"), recommended_actions)
    _collect(mission_control.get("handoff_requirements"), handoff_requirements)
    _add_track(
        "Mission control sync",
        lead="Mission control",
        readiness_tag=mission_status or "unknown",
        window=mission_control.get("next_sync_hours")
        if isinstance(mission_control.get("next_sync_hours"), (float, int))
        else None,
        status=mission_status or None,
    )

    overwatch_status = str(overwatch.get("status", "")).lower()
    _register_window(
        overwatch.get("next_sync_hours")
        if isinstance(overwatch.get("next_sync_hours"), (float, int))
        else None
    )
    if overwatch_status in {"manual_watch", "paired_watch"}:
        _penalise(
            7,
            "Overwatch posture demands manual supervision before automation release.",
            focus="Overwatch staffing",
        )
        prompts.append("Утримуйте чергову пару операторів на автоматизованих каналах.")
    elif overwatch_status == "mission_ready":
        _boost(3, "Overwatch teams are mission-ready for automation battle tempo.")
    _collect(overwatch.get("monitoring_channels"), battle_channels)
    _collect(overwatch.get("watch_focus"), focus_areas)
    _collect(overwatch.get("watch_items"), watch_items)
    _collect(overwatch.get("recommended_actions"), recommended_actions)
    _collect(overwatch.get("fallback_channels"), battle_channels)
    prompts.extend(overwatch.get("ukrainian_watch_prompts", []) or [])
    _add_track(
        "Automation overwatch",
        lead="Overwatch cell",
        readiness_tag=overwatch_status or "unknown",
        window=overwatch.get("next_sync_hours")
        if isinstance(overwatch.get("next_sync_hours"), (float, int))
        else None,
        status=overwatch_status or None,
    )

    autonomy_status = str(autonomy.get("status", "")).lower()
    _register_window(
        autonomy.get("autonomy_window_hours")
        if isinstance(autonomy.get("autonomy_window_hours"), (float, int))
        else None
    )
    if autonomy_status in {"manual_only", "manual_guarded"}:
        _penalise(
            8,
            "Automation autonomy limited; require manual battle management approvals.",
            focus="Autonomy safeguards",
        )
        handoff_requirements.append("Record autonomy overrides in the Ukrainian automation log.")
        prompts.append("Занотовуйте всі автономні рішення у журналі автоматизації штабу.")
    elif autonomy_status in {"mission_ready", "autonomous_ready"}:
        _boost(3, "Autonomy posture supports coordinated battle execution.")
    _collect(autonomy.get("trusted_tasks"), integration_targets)
    _collect(autonomy.get("restricted_tasks"), watch_items)
    _collect(autonomy.get("ukrainian_safeguards"), prompts)
    _collect(autonomy.get("recommended_actions"), recommended_actions)

    failsafe_status = str(failsafes.get("status", "")).lower()
    _register_window(
        failsafes.get("failsafe_window_hours")
        if isinstance(failsafes.get("failsafe_window_hours"), (float, int))
        else None
    )
    if failsafe_status in {"manual", "degraded"}:
        _penalise(
            6,
            "Failsafe posture degraded; automate battle releases only with fallback drills ready.",
            focus="Failsafe drills",
        )
        _collect(failsafes.get("fallback_channels"), battle_channels)
        prompts.append("Перевіряйте резервні канали автоматизації перед кожним запуском.")
    elif failsafe_status in {"mission_ready", "reinforced"}:
        _boost(2, "Failsafe drills current; automation battle windows can extend cautiously.")
    _collect(failsafes.get("recommended_actions"), recommended_actions)

    validation_status = str(validation.get("status", "")).lower()
    _register_window(
        validation.get("validation_window_hours")
        if isinstance(validation.get("validation_window_hours"), (float, int))
        else None
    )
    if validation_status in {"manual_review", "hold"}:
        _penalise(
            6,
            "Validation cadence requires manual review before automation battle deployment.",
            focus="Validation checks",
        )
        prompts.append("Переконайтесь, що валідаційні чеклісти підписані перед бойовим запуском.")
    elif validation_status in {"mission_ready", "validated"}:
        _boost(3, "Validation discipline supports automation battle management.")
    _collect(validation.get("recommended_actions"), recommended_actions)

    deployment_status = str(deployment.get("status", "")).lower()
    _register_window(
        deployment.get("deployment_window_hours")
        if isinstance(deployment.get("deployment_window_hours"), (float, int))
        else None
    )
    if deployment_status in {"hold", "manual_override"}:
        _penalise(
            6,
            "Automation deployment on hold; coordinate manual battle release sequencing.",
            focus="Deployment staging",
        )
    elif deployment_status in {"ready", "staged"}:
        _boost(2, "Automation deployment staged with clear release windows.")
    _collect(deployment.get("recommended_actions"), recommended_actions)
    for track in deployment.get("deployment_tracks", []) or []:
        if not isinstance(track, dict):
            continue
        _add_track(
            track.get("name") or track.get("track") or "Deployment track",
            lead=track.get("owner") or track.get("lead"),
            readiness_tag=track.get("readiness") or track.get("status"),
            window=track.get("window_hours"),
            status=track.get("status"),
        )

    readiness_level = str(readiness.get("level", "")).lower()
    _register_window(
        readiness.get("support_window_hours")
        if isinstance(readiness.get("support_window_hours"), (float, int))
        else None
    )
    if readiness_level == "critical":
        _penalise(
            10,
            "Readiness critical; maintain manual bridge for automation battle tasks.",
            focus="Staffing reinforcement",
        )
        handoff_requirements.append("Mobilise reserve analysts to cover automation battle queues.")
        prompts.append("Залучіть резерв чергових для підтримки автоматизованих напрямків.")
    elif readiness_level in {"strained", "watch"}:
        _penalise(5, "Readiness strained; battle management requires close staffing.")
    elif readiness_level in {"steady", "reinforced"}:
        _boost(3, "Readiness coverage enables automation battle tempo.")

    pressure_status = str(pressure.get("status", "")).lower()
    _register_window(
        pressure.get("estimated_clearance_hours")
        if isinstance(pressure.get("estimated_clearance_hours"), (float, int))
        else None
    )
    if pressure_status == "critical_backlog":
        _penalise(
            9,
            "Critical backlog; automation battle outputs require manual confirmation.",
            focus="Analyst throughput",
        )
        recommended_actions.append(
            "Stand up surge analysts to clear automation backlogs before widening windows."
        )
    elif pressure_status in {"backlog", "prediction_gap", "prediction_gap_watch"}:
        _penalise(6, "Automation queues elevated; pair analysts with automation outputs.")
    elif pressure_status in {"steady", "cleared"}:
        _boost(2, "Queue pressure stable; automation battle cadence can expand.")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"critical", "mobilise"}:
        _penalise(
            7,
            "Frontline mobilisation active; sync automation battle plans with brigades.",
            focus="Frontline integration",
        )
        prompts.append(
            "Попередьте офіцерів фронтової підтримки про автоматизовані бойові рішення."
        )
    elif frontline_status in {"reinforce", "watch"}:
        _penalise(3, "Frontline sustainment sensitive; monitor automation battle effects.")
    _collect(frontline.get("drivers"), drivers)
    _collect(frontline.get("signals"), focus_areas)
    _collect(frontline.get("recommended_actions"), recommended_actions)
    for support_entry in frontline.get("brigade_support", []) or []:
        if not isinstance(support_entry, dict):
            continue
        unit = support_entry.get("unit") or support_entry.get("brigade")
        if unit:
            integration_targets.append(str(unit))
        _add_track(
            unit or "Brigade support",
            lead=support_entry.get("resource") or support_entry.get("support"),
            readiness_tag=support_entry.get("priority"),
            window=support_entry.get("window_hours"),
            status=frontline_status or None,
        )

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "accelerate"}:
        _penalise(
            5,
            "Sustainment surge requires careful automation battle staging.",
            focus="Logistics coordination",
        )
    _collect(sustainment.get("recommended_actions"), recommended_actions)

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "critical"}:
        _penalise(
            5,
            "Support priorities elevated; confirm automation battle effects with support cell.",
            focus="Support confirmation",
        )
    _collect(support.get("recommended_actions"), recommended_actions)

    guardrail_status = str(guardrails.get("status", "")).lower()
    guardrail_score = guardrails.get("autonomy_score") or guardrails.get("guardrail_score")
    _register_window(
        guardrails.get("next_review_hours")
        if isinstance(guardrails.get("next_review_hours"), (float, int))
        else None
    )
    if guardrail_status in {"locked_down", "manual_override", "manual_guarded"}:
        _penalise(
            8,
            "Guardrails locked down; automation battle runs must stay under manual control.",
            focus="Guardrail oversight",
        )
        handoff_requirements.append("Document guardrail overrides before automation release.")
        prompts.append("Фіксуйте всі оверрайди захисту перед запуском скриптів.")
    elif guardrail_status in {"guided", "pilot"}:
        _penalise(4, "Guardrails in pilot mode; limit unattended battle automation windows.")
    elif guardrail_status in {"autonomous", "steady"}:
        _boost(3, "Guardrails stable; automation battle posture benefits from automation.")
    if isinstance(guardrail_score, (float, int)):
        if guardrail_score < 60:
            _penalise(5, "Guardrail score below 60; keep battle automation under supervision.")
        elif guardrail_score >= 85:
            _boost(3, "Guardrail score strong; automation battle tracks validated.")
    _collect(guardrails.get("monitoring_channels"), battle_channels)
    _collect(guardrails.get("fallback_channels"), battle_channels)
    _collect(guardrails.get("recommended_actions"), recommended_actions)

    automation_status = str(automation.get("status", "")).lower()
    automation_score = automation.get("automation_score")
    if automation_status in {"manual_override", "manual"}:
        _penalise(7, "Automation playbook in manual override; plan battle actions carefully.")
    elif automation_status in {"guided", "tune"}:
        _penalise(4, "Automation playbook guided; battle management requires supervision.")
    elif automation_status in {"autonomous", "pilot"}:
        _boost(3, "Automation playbook confident for coordinated battle automation.")
    if isinstance(automation_score, (float, int)):
        if automation_score < 60:
            _penalise(5, "Automation score degraded; leadership expects manual confirmation.")
        elif automation_score >= 82:
            _boost(3, "Automation score strong; battle automation gains trust.")
    _collect(automation.get("monitoring_channels"), battle_channels)
    _collect(automation.get("triggers"), watch_items)
    _collect(automation.get("recommended_actions"), recommended_actions)
    for task in automation.get("automation_tasks", []) or []:
        if not isinstance(task, dict):
            continue
        integration_targets.append(str(task.get("task") or task.get("name") or "Automation task"))

    directive_status = str(directives.get("status", "")).lower()
    if directive_status in {"escalate", "crisis"}:
        _penalise(
            7,
            "Command directives escalated; automate battle plans only with leadership sync.",
            focus="Command briefs",
        )
        recommended_actions.append("Brief Ukrainian command on automation battle posture each shift.")
    _collect(directives.get("recommended_actions"), recommended_actions)

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status in {"misaligned", "drift", "at_risk"}:
        _penalise(6, "Command alignment gaps; automation battle cells require manual sync.")
    _collect(alignment.get("recommended_actions"), recommended_actions)

    comm_status = str(communication.get("status", "")).lower()
    if comm_status in {"crisis", "escalated"}:
        _penalise(4, "Communication cadence escalated; share automation battle cues manually.")
    _collect(communication.get("recommended_actions"), recommended_actions)
    _collect(communication.get("channels"), battle_channels)

    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)) and assurance_score < 60:
        _penalise(4, "Mission assurance strained; automation battle posture must remain guarded.")

    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)) and resilience_score < 60:
        _penalise(4, "Operational resilience weak; battle automation requires contingency pairs.")

    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)) and continuity_score < 60:
        _penalise(3, "Continuity constraints limit unattended automation battle windows.")

    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)) and recovery_score < 60:
        _penalise(3, "Recovery roadmap still stabilising; stage automation battle uplift carefully.")

    transformation_score = transformation.get("transformation_score")
    if isinstance(transformation_score, (float, int)):
        if transformation_score < 55:
            _penalise(3, "Transformation maturity low; automation battle scaling gated.")
        elif transformation_score >= 78:
            _boost(3, "Transformation agenda supports automation battle innovation.")

    governance_score = governance.get("governance_score")
    _register_window(
        governance.get("next_review_hours")
        if isinstance(governance.get("next_review_hours"), (float, int))
        else None
    )
    if isinstance(governance_score, (float, int)) and governance_score < 60:
        _penalise(4, "Governance cadence weak; document automation battle escalations.")
    _collect(governance.get("recommended_actions"), recommended_actions)

    escalation_status = str(escalation.get("status", "")).lower()
    if escalation_status in {"escalate", "review", "heightened"}:
        _penalise(4, "Escalation pathways active; automate battle triggers with caution.")
    _register_window(
        escalation.get("next_review_hours")
        if isinstance(escalation.get("next_review_hours"), (float, int))
        else None
    )

    outlook_status = str(outlook.get("status", "")).lower()
    if outlook_status in {"heightened", "heightened_watch", "escalate"}:
        _penalise(3, "Operational outlook elevated; battle automation requires close tracking.")
    _collect(outlook.get("focus_areas"), focus_areas)

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(6, "Telemetry confidence low; enforce manual sampling on automation battles.")
    elif confidence_level == "guarded":
        _penalise(3, "Telemetry confidence guarded; keep supervisors in the loop.")
    elif confidence_level in {"high", "strong"}:
        _boost(2, "Telemetry confidence high; automation battle integration gains trust.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        _penalise(4, "Detection confidence below 0.6; confirm automation battle outputs manually.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        age_minutes = feed_info.get("age_minutes")
        if isinstance(age_minutes, (float, int)) and age_minutes > 0:
            _register_window(age_minutes / 60.0)
        if status == "stale":
            _penalise(
                6,
                f"{str(feed_name).title()} feed stale; battle automation requires manual confirmation.",
                focus="Telemetry recovery",
            )
            priority_feeds.append(f"{feed_name} (stale)")
        elif status == "warning":
            _penalise(
                3,
                f"{str(feed_name).title()} feed warning; shorten automation battle sync intervals.",
                focus="Telemetry monitoring",
            )
            priority_feeds.append(f"{feed_name} (warning)")

    severity_score = risks.get("severity_score")
    if isinstance(severity_score, (float, int)) and severity_score >= 80:
        _penalise(4, "Operational risk register elevated; leadership wants manual updates.")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.65:
        _penalise(4, "Feedback accuracy weak; pair analysts with automation battle outputs.")

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    drivers = _dedupe(drivers)
    focus_areas = _dedupe(focus_areas)
    watch_items = _dedupe(watch_items)
    recommended_actions = _dedupe(recommended_actions)
    prompts = _dedupe(prompts)
    integration_targets = _dedupe(integration_targets)
    priority_feeds = _dedupe(priority_feeds)
    handoff_requirements = _dedupe(handoff_requirements)
    battle_channels = sorted({channel for channel in battle_channels if channel})

    unique_tracks: List[Dict[str, Any]] = []
    seen_tracks = set()
    for track in coordination_tracks:
        key = (
            track.get("name"),
            track.get("lead"),
            track.get("readiness"),
            track.get("window_hours"),
            track.get("status"),
        )
        if key in seen_tracks:
            continue
        seen_tracks.add(key)
        unique_tracks.append(track)
    coordination_tracks = unique_tracks

    next_window: Optional[float] = None
    positive = [value for value in windows if value > 0]
    if positive:
        next_window = round(min(positive), 2)

    status = "coordinated"
    if severity >= 34 or score < 55:
        status = "manual_bridge"
    elif severity >= 24 or score < 65:
        status = "paired_ops"
    elif severity >= 16 or score < 75:
        status = "watch"
    elif score >= 90 and severity <= 10:
        status = "mission_ready"

    payload: Dict[str, Any] = {
        "status": status,
        "battle_management_score": round(score, 1),
    }
    if severity > 0:
        payload["severity_index"] = severity
    if next_window is not None:
        payload["battle_management_window_hours"] = next_window
    if drivers:
        payload["drivers"] = drivers
    if focus_areas:
        payload["focus_areas"] = focus_areas
    if watch_items:
        payload["watch_items"] = watch_items
    if recommended_actions:
        payload["recommended_actions"] = recommended_actions
    if prompts:
        payload["ukrainian_operator_prompts"] = prompts
    if battle_channels:
        payload["battle_channels"] = battle_channels
    if integration_targets:
        payload["integration_targets"] = integration_targets
    if priority_feeds:
        payload["priority_feeds"] = priority_feeds
    if handoff_requirements:
        payload["handoff_requirements"] = handoff_requirements
    if coordination_tracks:
        payload["coordination_tracks"] = coordination_tracks

    return payload if payload else None


def _derive_automation_campaign_orchestration(
    brief: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Fuse automation pillars into a campaign orchestration posture."""

    automation = brief.get("automation_playbook") or {}
    guardrails = brief.get("automation_guardrails") or {}
    mission_control = brief.get("automation_mission_control") or {}
    battle = brief.get("automation_battle_management") or {}
    overwatch = brief.get("automation_overwatch") or {}
    autonomy = brief.get("automation_autonomy") or {}
    failsafes = brief.get("automation_failsafes") or {}
    validation = brief.get("automation_validation") or {}
    deployment = brief.get("automation_deployment") or {}
    frontline = brief.get("frontline_support") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    sustainment = brief.get("resource_sustainment") or {}
    support = brief.get("support_priorities") or {}
    directives = brief.get("command_directives") or {}
    alignment = brief.get("command_alignment") or {}
    communication = brief.get("communication_plan") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    governance = brief.get("operational_governance") or {}
    outlook = brief.get("operational_outlook") or {}
    posture = brief.get("operational_posture") or {}
    risks = brief.get("operational_risks") or {}
    confidence = brief.get("intelligence_confidence") or {}
    detection_quality = brief.get("detection_quality") or {}
    freshness = brief.get("data_freshness") or {}
    gaps = brief.get("intelligence_gaps") or []
    meta = brief.get("meta") or {}

    if not any(
        [
            automation,
            guardrails,
            mission_control,
            battle,
            overwatch,
            autonomy,
            failsafes,
            validation,
            deployment,
            frontline,
            readiness,
            pressure,
            sustainment,
            support,
            directives,
            alignment,
            communication,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            governance,
            outlook,
            posture,
            risks,
            confidence,
            detection_quality,
            freshness,
            gaps,
        ]
    ):
        return None

    score = 90.0
    severity = 0
    drivers: List[str] = []
    focus_areas: List[str] = []
    watch_items: List[str] = []
    recommended_actions: List[str] = []
    prompts: List[str] = []
    campaign_channels: List[str] = []
    integration_partners: List[str] = []
    orchestration_tracks: List[Dict[str, Any]] = []
    dependencies: List[str] = []
    windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None, *, focus: Optional[str] = None) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            watch_items.append(str(note))
        if focus:
            focus_areas.append(str(focus))

    def _boost(amount: float, note: Optional[str] = None, *, focus: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            drivers.append(str(note))
        if focus:
            focus_areas.append(str(focus))

    def _collect(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if not value:
                continue
            target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    def _add_track(
        name: Optional[str],
        *,
        lead: Optional[str] = None,
        mode: Optional[str] = None,
        readiness_tag: Optional[str] = None,
        window: Optional[float] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        if not name:
            return
        track: Dict[str, Any] = {"name": str(name)}
        if lead:
            track["lead"] = str(lead)
        if mode:
            track["mode"] = str(mode)
        if readiness_tag:
            track["readiness"] = str(readiness_tag)
        if isinstance(window, (float, int)) and window > 0:
            track["window_hours"] = round(float(window), 2)
            _register_window(float(window))
        if status:
            track["status"] = str(status)
        if source:
            track["source"] = str(source)
        orchestration_tracks.append(track)

    for payload, key in [
        (automation, "automation_window_hours"),
        (mission_control, "next_sync_hours"),
        (battle, "battle_management_window_hours"),
        (overwatch, "next_sync_hours"),
        (autonomy, "autonomy_window_hours"),
        (failsafes, "failsafe_window_hours"),
        (validation, "validation_window_hours"),
        (deployment, "deployment_window_hours"),
        (readiness, "support_window_hours"),
        (pressure, "estimated_clearance_hours"),
        (frontline, "coordination_window_hours"),
        (support, "support_window_hours"),
        (sustainment, "resupply_window_hours"),
        (governance, "next_review_hours"),
        (outlook, "review_window_hours"),
    ]:
        window_value = payload.get(key) if isinstance(payload, dict) else None
        _register_window(window_value if isinstance(window_value, (float, int)) else None)

    mission_status = str(mission_control.get("status", "")).lower()
    battle_status = str(battle.get("status", "")).lower()
    overwatch_status = str(overwatch.get("status", "")).lower()
    automation_status = str(automation.get("status", "")).lower()
    guardrail_status = str(guardrails.get("status", "")).lower()
    autonomy_status = str(autonomy.get("status", "")).lower()
    failsafe_status = str(failsafes.get("status", "")).lower()
    validation_status = str(validation.get("status", "")).lower()
    deployment_status = str(deployment.get("status", "")).lower()
    readiness_level = str(readiness.get("level", "")).lower()
    pressure_status = str(pressure.get("status", "")).lower()
    frontline_status = str(frontline.get("status", "")).lower()
    sustainment_status = str(sustainment.get("status", "")).lower()
    support_status = str(support.get("status", "")).lower()
    directive_status = str(directives.get("status", "")).lower()
    alignment_status = str(alignment.get("status", "")).lower()
    communication_status = str(communication.get("status", "")).lower()
    resilience_status = str(resilience.get("status", "")).lower()
    continuity_status = str(continuity.get("status", "")).lower()
    recovery_status = str(recovery.get("status", "")).lower()
    transformation_status = str(transformation.get("status", "")).lower()
    posture_status = str(posture.get("status", "")).lower()
    outlook_status = str(outlook.get("status", "")).lower()

    if mission_status in {"manual_control", "manual_bridge"}:
        _penalise(
            12,
            "Mission control enforcing manual bridge; coordinate campaign decisions manually.",
            focus="Manual bridge",
        )
        prompts.append("Узгоджуйте кожну автоматизовану кампанію з черговим офіцером.")
        recommended_actions.append(
            "Record mission control approvals for every automation campaign release."
        )
    elif mission_status in {"paired_supervision", "paired_watch"}:
        _penalise(7, "Mission control requires paired supervision for automation campaigns.")
        prompts.append("Призначте напарника для координації автоматизованих кампаній.")
    elif mission_status in {"supervised", "mission_ready"}:
        _boost(3, "Mission control supporting campaign automation windows.")

    if battle_status in {"manual_bridge", "manual"}:
        _penalise(
            10,
            "Battle management on manual bridge; consolidate tracks before automation.",
            focus="Battle integration",
        )
        prompts.append("Підтверджуйте узгодження бойових треків вручну перед запуском.")
    elif battle_status in {"paired_ops", "watch"}:
        _penalise(6, "Battle management requires paired operations oversight.")
    elif battle_status == "mission_ready":
        _boost(3, "Battle management ready for automated orchestration.")

    if overwatch_status in {"manual_watch", "manual"}:
        _penalise(5, "Overwatch on manual watch; keep automation cadence short.")
    elif overwatch_status in {"paired_watch", "focused_watch"}:
        _penalise(3, "Overwatch enforcing paired review on automation outputs.")
    elif overwatch_status == "mission_ready":
        _boost(2, "Overwatch cadence supports automated orchestration.")

    if automation_status in {"manual", "manual_override"}:
        _penalise(6, "Automation playbook in manual override mode.")
    elif automation_status in {"guided", "tune"}:
        _penalise(3, "Automation guided; campaign release cadence reduced.")
    elif automation_status in {"autonomous", "pilot"}:
        _boost(4, "Automation playbook trusted for campaign execution.")

    if guardrail_status in {"locked_down", "manual_guarded", "manual_override"}:
        _penalise(7, "Guardrails constrained; leadership requires manual orchestration checks.")
        dependencies.append("Guardrail review cadence")
    elif guardrail_status in {"guided", "pilot"}:
        _penalise(3, "Guardrails guided; maintain supervision on campaign releases.")
    elif guardrail_status in {"autonomous", "steady"}:
        _boost(2, "Guardrails steady; automation campaign approvals faster.")

    if autonomy_status in {"manual_only", "manual"}:
        _penalise(5, "Automation autonomy manual; limit unattended orchestration.")
    elif autonomy_status in {"paired", "supervised"}:
        _penalise(3, "Automation autonomy paired; ensure supervision on key tracks.")
    elif autonomy_status in {"mission_ready", "autonomous"}:
        _boost(2, "Autonomy posture supports campaign automation.")

    if failsafe_status in {"manual", "degraded"}:
        _penalise(4, "Failsafes require manual triggers; keep contingency plans active.")
        dependencies.append("Failsafe drill schedule")
    elif failsafe_status in {"mission_ready", "ready"}:
        _boost(2, "Failsafes tested for campaign automation.")

    if validation_status in {"manual_review", "manual"}:
        _penalise(5, "Validation in manual review; share campaign updates with QA cell.")
        dependencies.append("Validation checklist")
    elif validation_status in {"mission_ready", "ready"}:
        _boost(3, "Validation cadence supports automation campaigns.")

    if deployment_status in {"hold", "blocked"}:
        _penalise(6, "Automation deployment on hold; coordinate manual synchronisation.")
    elif deployment_status in {"ready", "mission_ready"}:
        _boost(3, "Deployment track ready; expand automated campaign release windows.")

    if readiness_level == "critical":
        _penalise(8, "Readiness critical; automation campaigns must stay narrow.", focus="Readiness")
        prompts.append("Залучіть резервні зміни для покриття автоматизації.")
    elif readiness_level in {"strained", "degraded"}:
        _penalise(5, "Readiness strained; pair automation releases with manual crews.")
    elif readiness_level in {"steady", "reinforced"}:
        _boost(3, "Readiness teams can sustain automation campaigns.")

    if pressure_status in {"critical_backlog", "surge"}:
        _penalise(7, "Analyst backlog elevated; stagger automation campaign output.", focus="Queue relief")
        dependencies.append("Backlog clearance")
    elif pressure_status in {"backlog", "prediction_gap", "prediction_gap_watch"}:
        _penalise(4, "Queue pressure rising; maintain manual sampling on campaigns.")
    elif pressure_status in {"steady", "cleared"}:
        _boost(2, "Analyst throughput supports automation orchestration.")

    if frontline_status in {"critical", "surge"}:
        _penalise(6, "Frontline support strained; stage automation deployments carefully.")
        dependencies.append("Frontline support windows")
    elif frontline_status in {"steady", "reinforced"}:
        _boost(2, "Frontline sustainment ready for automated taskings.")

    if sustainment_status in {"surge", "critical"}:
        _penalise(4, "Sustainment under surge; confirm logistics for automation outputs.")
    elif sustainment_status in {"steady", "recovering"}:
        _boost(2, "Sustainment cadence supports campaign orchestration.")

    if support_status in {"mobilise", "escalate"}:
        _penalise(4, "Support cells mobilising; align automation campaigns with teams.")
    elif support_status in {"steady", "stabilise"}:
        _boost(2, "Support queue aligned to automation campaigns.")

    if directive_status in {"crisis", "escalate"}:
        _penalise(5, "Command directives critical; ensure leadership review of automation campaigns.")
    elif directive_status in {"stabilise", "align"}:
        _boost(2, "Directives support structured automation campaigns.")

    if alignment_status in {"misaligned", "at_risk"}:
        _penalise(5, "Command alignment at risk; hold automation campaigns for sync.")
    elif alignment_status in {"aligned", "synchronised"}:
        _boost(3, "Command alignment strong; automation campaigns can scale.")

    if communication_status in {"crisis", "escalated"}:
        _penalise(3, "Communications in crisis mode; schedule rapid automation updates.")
    elif communication_status in {"steady", "reinforced"}:
        _boost(2, "Communication plan ready to amplify automation campaigns.")

    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)):
        if assurance_score < 60:
            _penalise(4, "Mission assurance weak; stage automation campaigns cautiously.")
        elif assurance_score >= 80:
            _boost(3, "Mission assurance strong; campaign automation trusted.")

    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)):
        if resilience_score < 60:
            _penalise(4, "Operational resilience low; maintain manual fallback routes.")
        elif resilience_score >= 80:
            _boost(2, "Resilience high; automation campaigns can endure disruption.")

    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)):
        if continuity_score < 60:
            _penalise(4, "Continuity constraints limit unattended automation.")
        elif continuity_score >= 80:
            _boost(2, "Continuity posture steady; automation orchestration more resilient.")

    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)):
        if recovery_score < 60:
            _penalise(3, "Recovery roadmap still stabilising; stage automation carefully.")
        elif recovery_score >= 78:
            _boost(2, "Recovery roadmap supports campaign orchestration uplifts.")

    transformation_score = transformation.get("transformation_score")
    if isinstance(transformation_score, (float, int)):
        if transformation_score < 60:
            _penalise(3, "Transformation maturity low; ensure automation change control.")
        elif transformation_score >= 80:
            _boost(3, "Transformation agenda prepared for automation campaigns.")

    governance_score = governance.get("governance_score")
    if isinstance(governance_score, (float, int)) and governance_score < 60:
        _penalise(3, "Governance cadence weak; document campaign escalations.")

    posture_focus = posture.get("focus") or posture.get("focus_areas")
    if isinstance(posture_focus, list):
        _collect(posture_focus, focus_areas)

    if posture_status in {"recover", "stabilise"}:
        _penalise(2, "Operational posture recovering; pace automation releases.")
    elif posture_status in {"steady", "advance"}:
        _boost(2, "Operational posture steady; automation campaigns can expand.")

    if outlook_status in {"heightened", "escalate", "escalation_imminent"}:
        _penalise(3, "Operational outlook heightened; confirm campaign triggers.")
    elif outlook_status in {"stabilise", "steady"}:
        _boost(1, "Operational outlook steady; automation orchestration stable.")

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(5, "Telemetry confidence low; enforce manual verification on campaigns.")
        dependencies.append("Telemetry confidence rebuild")
    elif confidence_level in {"guarded", "moderate"}:
        _penalise(3, "Telemetry confidence guarded; maintain sampling.")
    elif confidence_level in {"high", "strong"}:
        _boost(2, "Telemetry confidence high; automation orchestration trusted.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        _penalise(4, "Detection confidence below 0.6; flag automation outputs for review.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        age_minutes = feed_info.get("age_minutes")
        if isinstance(age_minutes, (float, int)) and age_minutes > 0:
            _register_window(age_minutes / 60.0)
        if status == "stale":
            _penalise(
                5,
                f"{str(feed_name).title()} feed stale; align automation orchestration with recovery.",
                focus="Telemetry recovery",
            )
            dependencies.append(f"Restore {feed_name} feed")
        elif status == "warning":
            _penalise(
                3,
                f"{str(feed_name).title()} feed aging; shorten automation orchestration windows.",
                focus="Telemetry monitoring",
            )

    severity_score = risks.get("severity_score")
    if isinstance(severity_score, (float, int)) and severity_score >= 80:
        _penalise(4, "Operational risk register elevated; escalate campaign governance.")

    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        severity_label = str(gap.get("severity", "")).lower()
        description = gap.get("description") or gap.get("detail") or gap.get("name")
        if severity_label == "critical":
            _penalise(6, f"Critical gap: {description or 'gap'} affecting automation campaigns.")
            dependencies.append(f"Resolve critical gap: {description or 'gap'}")
        elif severity_label in {"major", "high"}:
            _penalise(3, f"Major gap: {description or 'gap'} requires supervision.")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.65:
        _penalise(3, "Feedback accuracy weak; increase manual sampling of automation campaigns.")

    for track in battle.get("coordination_tracks") or []:
        if not isinstance(track, dict):
            continue
        _add_track(
            track.get("name"),
            lead=track.get("lead"),
            readiness_tag=track.get("readiness"),
            window=track.get("window_hours"),
            status=track.get("status"),
            source="battle",
        )

    for task in automation.get("automation_tasks") or []:
        if not isinstance(task, dict):
            continue
        _add_track(
            task.get("task") or task.get("name"),
            lead=task.get("owner"),
            mode=task.get("mode"),
            readiness_tag=task.get("readiness"),
            window=task.get("window_hours"),
            status=task.get("status"),
            source="automation",
        )

    support_queue = support.get("coordination_queue") if isinstance(support, dict) else None
    if isinstance(support_queue, list):
        for entry in support_queue:
            if not isinstance(entry, dict):
                continue
            _add_track(
                entry.get("task") or entry.get("name"),
                lead=entry.get("owner") or entry.get("team"),
                readiness_tag=entry.get("priority"),
                window=entry.get("window_hours"),
                status=entry.get("status"),
                source="support",
            )

    deployment_tracks = deployment.get("deployment_tracks") if isinstance(deployment, dict) else None
    if isinstance(deployment_tracks, list):
        for entry in deployment_tracks:
            if not isinstance(entry, dict):
                continue
            _add_track(
                entry.get("name"),
                lead=entry.get("owner"),
                readiness_tag=entry.get("readiness"),
                window=entry.get("window_hours"),
                status=entry.get("status"),
                source="deployment",
            )

    frontline_units = frontline.get("brigade_support") if isinstance(frontline, dict) else None
    if isinstance(frontline_units, list):
        for unit in frontline_units:
            if not isinstance(unit, dict):
                continue
            integration_partners.append(str(unit.get("unit", "Frontline")))
            _add_track(
                unit.get("unit"),
                lead=unit.get("liaison") or unit.get("owner"),
                readiness_tag=unit.get("priority"),
                window=unit.get("window_hours"),
                status=unit.get("status"),
                source="frontline",
            )

    sustainment_needs = sustainment.get("resource_needs") if isinstance(sustainment, dict) else None
    if isinstance(sustainment_needs, list):
        for need in sustainment_needs:
            if not isinstance(need, dict):
                continue
            dependencies.append(str(need.get("resource", need.get("need", "Resource"))))

    _collect(mission_control.get("mission_channels"), campaign_channels)
    _collect(battle.get("battle_channels"), campaign_channels)
    _collect(automation.get("monitoring_channels"), campaign_channels)
    _collect(overwatch.get("monitoring_channels"), campaign_channels)
    _collect(guardrails.get("monitoring_channels"), campaign_channels)
    _collect(communication.get("channels") if isinstance(communication, dict) else [], campaign_channels)
    _collect(communication.get("primary_channels") if isinstance(communication, dict) else [], campaign_channels)

    _collect(automation.get("drivers"), drivers)
    _collect(battle.get("drivers"), drivers)
    _collect(frontline.get("drivers"), drivers)
    _collect(support.get("drivers"), drivers)
    _collect(transformation.get("drivers"), drivers)

    _collect(automation.get("focus_areas"), focus_areas)
    _collect(battle.get("focus_areas"), focus_areas)
    _collect(support.get("focus_areas"), focus_areas)
    _collect(outlook.get("focus_areas"), focus_areas)

    _collect(automation.get("recommended_actions"), recommended_actions)
    _collect(guardrails.get("recommended_actions"), recommended_actions)
    _collect(mission_control.get("recommended_actions"), recommended_actions)
    _collect(battle.get("recommended_actions"), recommended_actions)
    _collect(overwatch.get("recommended_actions"), recommended_actions)
    _collect(validation.get("recommended_actions"), recommended_actions)
    _collect(deployment.get("recommended_actions"), recommended_actions)
    _collect(support.get("recommended_actions"), recommended_actions)
    _collect(frontline.get("recommended_actions"), recommended_actions)
    _collect(sustainment.get("recommended_actions"), recommended_actions)
    _collect(directives.get("recommended_actions"), recommended_actions)
    _collect(alignment.get("recommended_actions"), recommended_actions)
    _collect(communication.get("recommended_actions"), recommended_actions)

    prompts.extend(
        [
            "Переконайтеся, що автоматизовані кампанії узгоджені з бойовими пріоритетами.",
            "Повідомляйте ланку забезпечення про кожне автоматизоване відвантаження.",
        ]
    )

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    def _dedupe_tracks(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[Tuple[Any, ...]] = set()
        ordered: List[Dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = (
                entry.get("name"),
                entry.get("lead"),
                entry.get("mode"),
                entry.get("readiness"),
                entry.get("window_hours"),
                entry.get("status"),
                entry.get("source"),
            )
            if key in seen:
                continue
            seen.add(key)
            ordered.append(entry)
        return ordered

    drivers = _dedupe(drivers)
    focus_areas = _dedupe(focus_areas)
    watch_items = _dedupe(watch_items)
    recommended_actions = _dedupe(recommended_actions)
    prompts = _dedupe(prompts)
    campaign_channels = sorted({channel for channel in campaign_channels if channel})
    integration_partners = _dedupe(integration_partners)
    dependencies = _dedupe(dependencies)
    orchestration_tracks = _dedupe_tracks(orchestration_tracks)

    next_window: Optional[float] = None
    positive = [value for value in windows if value > 0]
    if positive:
        next_window = round(min(positive), 2)

    status = "coordinated"
    if severity >= 32 or score < 55:
        status = "manual_bridge"
    elif severity >= 22 or score < 65:
        status = "paired_ops"
    elif severity >= 12 or score < 75:
        status = "watch"
    elif score >= 90 and severity <= 10:
        status = "mission_ready"

    payload: Dict[str, Any] = {
        "status": status,
        "campaign_orchestration_score": round(score, 1),
    }
    if severity > 0:
        payload["severity_index"] = severity
    if next_window is not None:
        payload["campaign_window_hours"] = next_window
    if drivers:
        payload["drivers"] = drivers
    if focus_areas:
        payload["focus_areas"] = focus_areas
    if watch_items:
        payload["watch_items"] = watch_items
    if recommended_actions:
        payload["recommended_actions"] = recommended_actions
    if prompts:
        payload["ukrainian_operator_prompts"] = prompts
    if campaign_channels:
        payload["campaign_channels"] = campaign_channels
    if integration_partners:
        payload["integration_partners"] = integration_partners
    if dependencies:
        payload["operational_dependencies"] = dependencies
    if orchestration_tracks:
        payload["orchestration_tracks"] = orchestration_tracks

    return payload if payload else None

def _derive_automation_joint_operations(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Coordinate coalition automation operations across Ukrainian and partner teams."""

    campaign = brief.get("automation_campaign_orchestration") or {}
    battle = brief.get("automation_battle_management") or {}
    mission_control = brief.get("automation_mission_control") or {}
    overwatch = brief.get("automation_overwatch") or {}
    guardrails = brief.get("automation_guardrails") or {}
    playbook = brief.get("automation_playbook") or {}
    autonomy = brief.get("automation_autonomy") or {}
    failsafes = brief.get("automation_failsafes") or {}
    validation = brief.get("automation_validation") or {}
    deployment = brief.get("automation_deployment") or {}
    frontline = brief.get("frontline_support") or {}
    sustainment = brief.get("resource_sustainment") or {}
    support = brief.get("support_priorities") or {}
    directives = brief.get("command_directives") or {}
    alignment = brief.get("command_alignment") or {}
    communication = brief.get("communication_plan") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    governance = brief.get("operational_governance") or {}

    if not any(
        [
            campaign,
            battle,
            mission_control,
            overwatch,
            guardrails,
            playbook,
            autonomy,
            failsafes,
            validation,
            deployment,
            frontline,
            sustainment,
            support,
            directives,
            alignment,
            communication,
            readiness,
            pressure,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            governance,
        ]
    ):
        return None

    score = 94.0
    severity = 0
    drivers: List[str] = []
    focus_areas: List[str] = []
    watch_items: List[str] = []
    recommended_actions: List[str] = []
    prompts: List[str] = []
    integration_channels: List[str] = []
    coalition_partners: List[str] = []
    joint_tracks: List[Dict[str, Any]] = []
    dependencies: List[str] = []
    handoff_requirements: List[str] = []
    support_cells: List[str] = []
    windows: List[float] = []

    def _penalise(
        amount: float,
        note: Optional[str] = None,
        *,
        focus: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            watch_items.append(str(note))
        if focus:
            focus_areas.append(str(focus))
        if prompt:
            prompts.append(str(prompt))

    def _boost(amount: float, note: Optional[str] = None, *, focus: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            drivers.append(str(note))
        if focus:
            focus_areas.append(str(focus))

    def _collect(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if not value:
                continue
            target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    def _add_track(
        name: Optional[str],
        *,
        lead: Optional[str] = None,
        mode: Optional[str] = None,
        readiness_tag: Optional[str] = None,
        window: Optional[float] = None,
        status: Optional[str] = None,
        source: Optional[str] = None,
    ) -> None:
        if not name:
            return
        track: Dict[str, Any] = {"name": str(name)}
        if lead:
            track["lead"] = str(lead)
        if mode:
            track["mode"] = str(mode)
        if readiness_tag:
            track["readiness"] = str(readiness_tag)
        if isinstance(window, (float, int)) and window > 0:
            track["window_hours"] = round(float(window), 2)
            _register_window(float(window))
        if status:
            track["status"] = str(status)
        if source:
            track["source"] = str(source)
        joint_tracks.append(track)

    mission_status = str(mission_control.get("status", "")).lower()
    if mission_status in {"manual_control", "manual_bridge"}:
        _penalise(
            14,
            "Mission control operating in manual bridge; coalition releases require duty approval.",
            focus="Mission control bridge",
            prompt="Погоджуйте кожне автоматизоване завдання з черговими офіцерами та союзними представниками.",
        )
        handoff_requirements.append(
            "Duty officer retains release authority for coalition automations."
        )
    elif mission_status in {"paired_supervision", "supervised"}:
        _penalise(
            7,
            "Mission control is under supervised mode; keep coalition liaisons paired to releases.",
            focus="Supervised mission control",
            prompt="Залучіть партнерських зв’язкових до контрольних запусків автоматизації.",
        )
        handoff_requirements.append(
            "Pair mission control with coalition liaison for supervised releases."
        )
    elif mission_status == "mission_ready":
        _boost(
            4,
            "Mission control ready to steer coalition automation runs.",
            focus="Mission-ready coordination",
        )

    battle_status = str(battle.get("status", "")).lower()
    if battle_status in {"manual_bridge", "manual_control"}:
        _penalise(
            11,
            "Automation battle management running manual bridge; synchronise fires approvals manually.",
            focus="Manual battle bridge",
            prompt="Повідомте артилерійські та БПЛА-розрахунки про ручне підтвердження завдань.",
        )
        handoff_requirements.append(
            "Coordinate fires release manually with coalition battle captains."
        )
    elif battle_status in {"paired_ops", "watch"}:
        _penalise(
            6,
            "Battle automation requires paired operations; align coalition fires liaisons.",
            focus="Paired battle ops",
        )
    elif battle_status == "mission_ready":
        _boost(3, "Battle automation aligned across partners.", focus="Coalition battle rhythm")

    campaign_status = str(campaign.get("status", "")).lower()
    if campaign_status in {"manual_bridge", "manual_joint"}:
        _penalise(
            8,
            "Campaign orchestration degraded; coalition planning windows need manual steering.",
            focus="Campaign oversight",
        )
    elif campaign_status in {"paired_ops", "watch"}:
        _penalise(5, "Campaign orchestration requires close partner pairing.", focus="Campaign synchronisation")
    elif campaign_status in {"coordinated", "mission_ready"}:
        _boost(4, "Campaign orchestration flowing across partners.", focus="Campaign synchronisation")

    guardrail_status = str(guardrails.get("status", "")).lower()
    if guardrail_status in {"locked_down", "manual_override"}:
        _penalise(
            6,
            "Automation guardrails locked down; share manual override notes with coalition partners.",
            focus="Guardrail synchronisation",
            prompt="Зафіксуйте обмеження та поширте їх серед союзних змін.",
        )

    autonomy_status = str(autonomy.get("status", "")).lower()
    if autonomy_status in {"manual_only", "manual_guarded", "restricted"}:
        _penalise(
            6,
            "Automation autonomy restricted; assign coalition monitors before releases.",
            focus="Autonomy safeguards",
            prompt="Призначте представника союзників для контролю обмеженого режиму автономії.",
        )

    failsafe_status = str(failsafes.get("status", "")).lower()
    if failsafe_status in {"manual", "degraded"}:
        _penalise(
            5,
            "Failsafe posture manual; rehearse fallback steps with coalition operators.",
            focus="Failsafe drills",
        )

    validation_status = str(validation.get("status", "")).lower()
    if validation_status in {"manual_review", "degraded"}:
        _penalise(
            5,
            "Automation validation requires manual review; coordinate evidence exchange with partners.",
            focus="Validation backlog",
        )

    deployment_status = str(deployment.get("status", "")).lower()
    if deployment_status in {"hold", "manual_override", "guarded"}:
        _penalise(
            5,
            "Automation deployment on hold; inform coalition release managers.",
            focus="Deployment coordination",
        )
    elif deployment_status in {"ready", "mission_ready"}:
        _boost(2, "Deployment pipeline ready for coalition execution.")

    overwatch_status = str(overwatch.get("status", "")).lower()
    if overwatch_status in {"manual_watch", "manual_bridge"}:
        _penalise(
            6,
            "Automation overwatch in manual watch; schedule coalition monitoring rotations.",
            focus="Overwatch pairing",
        )

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level == "critical":
        _penalise(
            10,
            "Response readiness critical; coalition automation stays in manual loop.",
            focus="Readiness recovery",
            prompt="Попередьте партнерські штаби про критичну готовність та ручний режим.",
        )
        support_cells.append("Command Liaison")
    elif readiness_level == "strained":
        _penalise(
            6,
            "Readiness strained; ensure coalition relief teams cover automation outputs.",
            focus="Readiness reinforcement",
        )
        support_cells.append("Operations Planning")
    elif readiness_level in {"steady", "reinforced"}:
        _boost(2, "Readiness steady for coalition automation supervision.")

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status == "critical_backlog":
        _penalise(
            8,
            "Critical analyst backlog; coalition automation results require manual triage.",
            focus="Queue clearance",
        )
        support_cells.append("Intelligence Cell")
    elif pressure_status in {"backlog", "prediction_gap", "prediction_gap_watch"}:
        _penalise(5, "Analyst workload elevated; keep coalition validation paired.")

    sustain_status = str(sustainment.get("status", "")).lower()
    if sustain_status in {"surge", "mobilise"}:
        _penalise(
            6,
            "Sustainment plan surging; align coalition logistics commitments.",
            focus="Sustainment surge",
        )
        support_cells.append("Logistics")
    elif sustain_status in {"accelerate", "reinforce"}:
        _penalise(4, "Sustainment acceleration needed; confirm coalition resupply routes.")

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "critical"}:
        _penalise(
            6,
            "Support priorities mobilising; confirm coalition support rotations.",
            focus="Support mobilisation",
        )
    elif support_status in {"reinforce", "accelerate"}:
        _penalise(4, "Support queue elevated; share coalition staffing adjustments.")

    directive_severity = directives.get("severity")
    if isinstance(directive_severity, (float, int)):
        if directive_severity >= 18:
            _penalise(8, "Command directives in crisis band; coalition approvals must be synchronised.")
        elif directive_severity >= 12:
            _penalise(5, "Command directives accelerated; keep coalition liaison informed.")
        elif directive_severity >= 6:
            _penalise(3, "Command directives focused; align automation agenda with partners.")

    directive_status = str(directives.get("status", "")).lower()
    if directive_status in {"crisis", "escalate"}:
        _penalise(7, "Command directives escalated; run coalition sync briefs.", focus="Command synchronisation")
    elif directive_status in {"accelerate", "focus"}:
        _penalise(3, "Command directives emphasise rapid coalition action.")

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status == "misaligned":
        _penalise(
            10,
            "Command alignment misaligned; coalition automation requires manual arbitration.",
            focus="Command alignment",
            prompt="Синхронізуйтеся з командуванням союзників для вирівнювання рішень.",
        )
        support_cells.append("Command Liaison")
    elif alignment_status == "at_risk":
        _penalise(6, "Command alignment at risk; escalate coalition sync cadence.")
    elif alignment_status == "aligned":
        _boost(3, "Command alignment steady across coalition teams.")

    comm_status = str(communication.get("status", "")).lower()
    if comm_status == "escalated":
        _penalise(6, "Communication cadence escalated; coordinate coalition messaging loops.", focus="Communications cadence")
    elif comm_status == "heightened":
        _penalise(3, "Communication cadence heightened; ensure partner liaisons are briefed.")
    elif comm_status == "focused":
        _boost(2, "Communication plan focused on coalition priorities.")

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status in {"critical", "at_risk"}:
        _penalise(6, "Mission assurance degraded; coalition automation requires contingency cover.")
    elif assurance_status == "assured":
        _boost(2, "Mission assurance steady across partners.")

    resilience_status = str(resilience.get("status", "")).lower()
    if resilience_status in {"critical", "vulnerable"}:
        _penalise(6, "Operational resilience weak; keep coalition reserves primed.")
    elif resilience_status in {"steady", "resilient"}:
        _boost(2, "Operational resilience reinforcing automation trust.")

    continuity_status = str(continuity.get("status", "")).lower()
    if continuity_status in {"critical", "strained", "constrained", "degraded"}:
        _penalise(6, "Operational continuity stressed; joint automation requires fallback planning.")

    recovery_status = str(recovery.get("status", "")).lower()
    if recovery_status in {"manual_recovery", "rebuild", "stabilise", "stabilize"}:
        _penalise(4, "Operational recovery active; prioritise coalition rebuild tracks.")

    transformation_status = str(transformation.get("status", "")).lower()
    if transformation_status in {"mobilise", "accelerate"}:
        _penalise(3, "Transformation agenda accelerating; align coalition change owners.")

    governance_score = governance.get("governance_score")
    if isinstance(governance_score, (float, int)) and governance_score < 60:
        _penalise(3, "Governance score below 60; document coalition oversight actions.")

    for payload, key in [
        (campaign, "campaign_window_hours"),
        (mission_control, "next_sync_hours"),
        (battle, "battle_management_window_hours"),
        (overwatch, "next_sync_hours"),
        (autonomy, "autonomy_window_hours"),
        (failsafes, "failsafe_window_hours"),
        (validation, "validation_window_hours"),
        (deployment, "deployment_window_hours"),
        (frontline, "coordination_window_hours"),
        (sustainment, "resupply_window_hours"),
        (support, "support_window_hours"),
        (alignment, "next_sync_hours"),
        (directives, "planning_window_hours"),
    ]:
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, (float, int)):
            _register_window(float(value))

    cadence_minutes = communication.get("update_cadence_minutes") if isinstance(communication, dict) else None
    if isinstance(cadence_minutes, (float, int)) and cadence_minutes > 0:
        _register_window(float(cadence_minutes) / 60.0)

    for track in campaign.get("orchestration_tracks", []) if isinstance(campaign, dict) else []:
        if not isinstance(track, dict):
            continue
        _add_track(
            track.get("name"),
            lead=track.get("lead"),
            mode=track.get("mode"),
            readiness_tag=track.get("readiness"),
            window=track.get("window_hours"),
            status=track.get("status"),
            source=track.get("source") or "campaign",
        )

    for track in battle.get("coordination_tracks", []) if isinstance(battle, dict) else []:
        if not isinstance(track, dict):
            continue
        _add_track(
            track.get("name"),
            lead=track.get("lead"),
            readiness_tag=track.get("readiness"),
            window=track.get("window_hours"),
            status=track.get("status"),
            source="battle",
        )

    for task in playbook.get("automation_tasks", []) if isinstance(playbook, dict) else []:
        if not isinstance(task, dict):
            continue
        _add_track(
            task.get("task"),
            lead=task.get("owner"),
            mode=task.get("mode"),
            readiness_tag=task.get("mode"),
            window=task.get("window_hours"),
            status=task.get("status"),
            source="automation",
        )

    for entry in deployment.get("deployment_tracks", []) if isinstance(deployment, dict) else []:
        if not isinstance(entry, dict):
            continue
        _add_track(
            entry.get("name"),
            lead=entry.get("owner"),
            readiness_tag=entry.get("readiness"),
            window=entry.get("window_hours"),
            status=entry.get("status"),
            source="deployment",
        )

    for entry in support.get("coordination_queue", []) if isinstance(support, dict) else []:
        if not isinstance(entry, dict):
            continue
        _add_track(
            entry.get("task") or entry.get("team"),
            lead=entry.get("team"),
            mode=entry.get("priority"),
            readiness_tag=entry.get("priority"),
            window=entry.get("window_hours"),
            status=entry.get("status"),
            source="support",
        )
        team = entry.get("team")
        if team:
            support_cells.append(str(team))

    for entry in frontline.get("brigade_support", []) if isinstance(frontline, dict) else []:
        if not isinstance(entry, dict):
            continue
        _add_track(
            entry.get("unit"),
            lead=entry.get("lead") or entry.get("unit"),
            mode=entry.get("priority"),
            readiness_tag=entry.get("priority"),
            window=entry.get("window_hours"),
            status=entry.get("status"),
            source="frontline",
        )
        unit = entry.get("unit")
        if unit:
            coalition_partners.append(str(unit))

    _collect(campaign.get("operational_dependencies"), dependencies)
    _collect(battle.get("priority_feeds"), dependencies)
    _collect(sustainment.get("resource_needs"), dependencies)
    _collect(frontline.get("support_corridors"), dependencies)
    _collect(guardrails.get("critical_guardrails"), dependencies)
    _collect(autonomy.get("ukrainian_safeguards"), dependencies)

    _collect(playbook.get("recommended_actions"), recommended_actions)
    _collect(guardrails.get("recommended_actions"), recommended_actions)
    _collect(mission_control.get("recommended_actions"), recommended_actions)
    _collect(battle.get("recommended_actions"), recommended_actions)
    _collect(overwatch.get("recommended_actions"), recommended_actions)
    _collect(campaign.get("recommended_actions"), recommended_actions)
    _collect(frontline.get("recommended_actions"), recommended_actions)
    _collect(sustainment.get("recommended_actions"), recommended_actions)
    _collect(support.get("recommended_actions"), recommended_actions)
    _collect(directives.get("recommended_actions"), recommended_actions)
    _collect(alignment.get("recommended_actions"), recommended_actions)
    _collect(communication.get("recommended_actions"), recommended_actions)
    _collect(deployment.get("recommended_actions"), recommended_actions)
    _collect(validation.get("recommended_actions"), recommended_actions)
    _collect(failsafes.get("recommended_actions"), recommended_actions)
    _collect(autonomy.get("recommended_actions"), recommended_actions)

    _collect(campaign.get("drivers"), drivers)
    _collect(battle.get("drivers"), drivers)
    _collect(mission_control.get("control_focus"), drivers)
    _collect(frontline.get("drivers"), drivers)
    _collect(support.get("drivers"), drivers)
    _collect(alignment.get("drivers"), drivers)
    _collect(directives.get("drivers"), drivers)
    _collect(communication.get("drivers"), drivers)
    _collect(resilience.get("drivers"), drivers)

    _collect(campaign.get("focus_areas"), focus_areas)
    _collect(battle.get("focus_areas"), focus_areas)
    _collect(mission_control.get("control_focus"), focus_areas)
    _collect(frontline.get("signals"), focus_areas)
    _collect(alignment.get("focus_areas"), focus_areas)
    _collect(directives.get("focus_areas"), focus_areas)

    _collect(campaign.get("watch_items"), watch_items)
    _collect(battle.get("watch_items"), watch_items)
    _collect(mission_control.get("watch_items"), watch_items)
    _collect(overwatch.get("watch_items"), watch_items)
    _collect(alignment.get("coordination_gaps"), watch_items)

    _collect(mission_control.get("mission_channels"), integration_channels)
    _collect(battle.get("battle_channels"), integration_channels)
    _collect(overwatch.get("monitoring_channels"), integration_channels)
    _collect(playbook.get("monitoring_channels"), integration_channels)
    _collect(guardrails.get("monitoring_channels"), integration_channels)
    _collect(communication.get("channels"), integration_channels)

    _collect(campaign.get("integration_partners"), coalition_partners)
    _collect(support.get("teams"), coalition_partners)
    _collect(frontline.get("priority_units"), coalition_partners)

    for audience in communication.get("audiences", []) if isinstance(communication, dict) else []:
        if isinstance(audience, dict) and audience.get("audience"):
            coalition_partners.append(str(audience.get("audience")))

    _collect(campaign.get("ukrainian_operator_prompts"), prompts)
    _collect(battle.get("ukrainian_operator_prompts"), prompts)
    _collect(mission_control.get("ukrainian_operator_prompts"), prompts)
    _collect(frontline.get("ukrainian_operator_notes"), prompts)
    _collect(autonomy.get("ukrainian_safeguards"), prompts)

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    drivers = _dedupe(drivers)
    focus_areas = _dedupe(focus_areas)
    watch_items = _dedupe(watch_items)
    recommended_actions = _dedupe(recommended_actions)
    prompts = _dedupe(prompts)
    dependencies = _dedupe(dependencies)
    handoff_requirements = _dedupe(handoff_requirements)
    support_cells = _dedupe(support_cells)
    coalition_partners = _dedupe(coalition_partners)
    integration_channels = sorted({channel for channel in integration_channels if channel})

    unique_tracks: List[Dict[str, Any]] = []
    seen_tracks = set()
    for track in joint_tracks:
        key = (
            track.get("name"),
            track.get("lead"),
            track.get("mode"),
            track.get("readiness"),
            track.get("window_hours"),
            track.get("status"),
            track.get("source"),
        )
        if key in seen_tracks:
            continue
        seen_tracks.add(key)
        unique_tracks.append(track)
    joint_tracks = unique_tracks

    next_window: Optional[float] = None
    positive = [value for value in windows if value and value > 0]
    if positive:
        next_window = round(min(positive), 2)

    status = "synchronising"
    if severity >= 40 or score < 55:
        status = "manual_bridge"
    elif severity >= 28 or score < 65:
        status = "manual_joint"
    elif severity >= 18 or score < 75:
        status = "paired_ops"
    elif score >= 90 and severity <= 12:
        status = "coalition_ready"

    payload: Dict[str, Any] = {
        "status": status,
        "joint_operations_score": round(score, 1),
    }
    if severity > 0:
        payload["severity_index"] = severity
    if next_window is not None:
        payload["joint_window_hours"] = next_window
    if drivers:
        payload["drivers"] = drivers
    if focus_areas:
        payload["focus_areas"] = focus_areas
    if watch_items:
        payload["watch_items"] = watch_items
    if recommended_actions:
        payload["recommended_actions"] = recommended_actions
    if prompts:
        payload["ukrainian_operator_prompts"] = prompts
    if integration_channels:
        payload["integration_channels"] = integration_channels
    if coalition_partners:
        payload["coalition_partners"] = coalition_partners
    if joint_tracks:
        payload["joint_operation_tracks"] = joint_tracks
    if dependencies:
        payload["operational_dependencies"] = dependencies
    if handoff_requirements:
        payload["handoff_requirements"] = handoff_requirements
    if support_cells:
        payload["support_cells"] = support_cells

    return payload if payload else None


def _derive_automation_theater_command(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Unify multi-theatre automation command and partner coordination."""

    joint_ops = brief.get("automation_joint_operations") or {}
    campaign = brief.get("automation_campaign_orchestration") or {}
    battle = brief.get("automation_battle_management") or {}
    mission_control = brief.get("automation_mission_control") or {}
    overwatch = brief.get("automation_overwatch") or {}
    guardrails = brief.get("automation_guardrails") or {}
    playbook = brief.get("automation_playbook") or {}
    mission_control_channels = mission_control.get("mission_channels") or []
    autonomy = brief.get("automation_autonomy") or {}
    failsafes = brief.get("automation_failsafes") or {}
    validation = brief.get("automation_validation") or {}
    deployment = brief.get("automation_deployment") or {}
    battle_tracks = battle.get("coordination_tracks") or []
    campaign_tracks = campaign.get("orchestration_tracks") or []
    joint_tracks = joint_ops.get("joint_operation_tracks") or []
    directives = brief.get("command_directives") or {}
    alignment = brief.get("command_alignment") or {}
    communication = brief.get("communication_plan") or {}
    governance = brief.get("operational_governance") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    sustainment = brief.get("resource_sustainment") or {}
    frontline = brief.get("frontline_support") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}

    if not any(
        [
            joint_ops,
            campaign,
            battle,
            mission_control,
            overwatch,
            guardrails,
            playbook,
            autonomy,
            failsafes,
            validation,
            deployment,
            directives,
            alignment,
            communication,
            governance,
            assurance,
            resilience,
            continuity,
            recovery,
            sustainment,
            frontline,
            readiness,
            pressure,
        ]
    ):
        return None

    score = 93.0
    severity = 0
    drivers: List[str] = []
    focus_areas: List[str] = []
    watch_items: List[str] = []
    recommended_actions: List[str] = []
    prompts: List[str] = []
    coordinating_theaters: List[str] = []
    command_channels: List[str] = []
    coalition_commanders: List[str] = []
    support_requirements: List[str] = []
    windows: List[float] = []
    command_tracks: List[Dict[str, Any]] = []

    def _penalise(
        amount: float,
        note: Optional[str] = None,
        *,
        focus: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            watch_items.append(str(note))
        if focus:
            focus_areas.append(str(focus))
        if prompt:
            prompts.append(str(prompt))

    def _boost(amount: float, note: Optional[str] = None, *, focus: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            drivers.append(str(note))
        if focus:
            focus_areas.append(str(focus))

    def _collect_text(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if not value:
                continue
            target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    def _track_from(source: str, track: MutableMapping[str, Any]) -> None:
        name = track.get("name") or track.get("task") or track.get("track")
        if not name:
            return
        entry: Dict[str, Any] = {"name": str(name)}
        lead = track.get("lead") or track.get("owner") or track.get("team")
        if lead:
            entry["lead"] = str(lead)
            coalition_commanders.append(str(lead))
        mode = track.get("mode") or track.get("priority")
        if mode:
            entry["mode"] = str(mode)
        readiness_tag = track.get("readiness") or track.get("status")
        if readiness_tag:
            entry["readiness"] = str(readiness_tag)
        window_value = track.get("window_hours") or track.get("window")
        if isinstance(window_value, (float, int)) and window_value > 0:
            entry["window_hours"] = round(float(window_value), 2)
            _register_window(float(window_value))
        status = track.get("status")
        if status:
            entry["status"] = str(status)
        entry["source"] = source
        command_tracks.append(entry)

    joint_status = str(joint_ops.get("status", "")).lower()
    if joint_status in {"manual_bridge", "manual_joint"}:
        _penalise(
            12,
            "Coalition automation running manual bridge; theatre command must retain release authority.",
            focus="Manual coalition bridge",
            prompt="Погодьте кожне автоматизоване завдання з міжтеатральним штабом перед запуском.",
        )
        support_requirements.append(
            "Duty officer retains veto on coalition automation releases in all theatres."
        )
    elif joint_status in {"paired_ops", "watch", "synchronising"}:
        _penalise(
            6,
            "Coalition automation requires paired command oversight across theatres.",
            focus="Paired coalition command",
        )
    elif joint_status in {"coalition_ready", "mission_ready"}:
        _boost(4, "Coalition automation ready to support multi-theatre operations.")

    battle_status = str(battle.get("status", "")).lower()
    if battle_status in {"manual_bridge", "manual_control"}:
        _penalise(
            8,
            "Battle management operating in manual bridge; theatre fires approval needed.",
            focus="Manual battle bridge",
            prompt="Синхронізуйте підтвердження вогневих місій у кожному театрі вручну.",
        )
        support_requirements.append("Fires duty officers pair with automation releases.")
    elif battle_status in {"paired_ops", "watch"}:
        _penalise(4, "Battle automation requires paired operations.", focus="Battle pairing")
    elif battle_status == "mission_ready":
        _boost(3, "Battle management automation supporting coalition theatres.")

    mission_status = str(mission_control.get("status", "")).lower()
    if mission_status in {"manual_control", "manual_bridge"}:
        _penalise(
            8,
            "Mission control in manual state; theatre command must approve releases.",
            focus="Mission control approvals",
            prompt="Підтвердьте з черговим штабу автоматизовані дії до виконання.",
        )
    elif mission_status in {"paired_supervision", "supervised"}:
        _penalise(4, "Mission control supervised; keep theatre commanders informed.")
    elif mission_status == "mission_ready":
        _boost(2, "Mission control automation ready for theatre coordination.")

    guardrail_status = str(guardrails.get("status", "")).lower()
    if guardrail_status in {"locked_down", "manual_override"}:
        _penalise(
            6,
            "Automation guardrails locked down; theatre command needs manual briefs.",
            focus="Guardrail oversight",
            prompt="Доставте нотатки про обмеження до штабів театрів.",
        )

    autonomy_status = str(autonomy.get("status", "")).lower()
    if autonomy_status in {"manual_only", "manual_guarded", "restricted"}:
        _penalise(
            6,
            "Automation autonomy restricted; assign theatre monitors before releases.",
            focus="Autonomy safeguards",
        )

    failsafe_status = str(failsafes.get("status", "")).lower()
    if failsafe_status in {"manual", "degraded"}:
        _penalise(5, "Failsafes degraded; rehearse fallback plans per theatre.")

    validation_status = str(validation.get("status", "")).lower()
    if validation_status in {"manual_review", "degraded"}:
        _penalise(5, "Validation backlog requires theatre QA review.")

    deployment_status = str(deployment.get("status", "")).lower()
    if deployment_status in {"hold", "manual_override", "guarded"}:
        _penalise(
            5,
            "Deployment pipeline guarded; theatre release windows constrained.",
            focus="Deployment windows",
        )
    elif deployment_status in {"ready", "mission_ready"}:
        _boost(2, "Deployment pipeline supports multi-theatre releases.")

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level == "critical":
        _penalise(
            10,
            "Response readiness critical; automation releases need theatre commander approval.",
            focus="Readiness recovery",
            prompt="Повідомте командирів театрів про критичний стан готовності.",
        )
        support_requirements.append("Mobilise reserve analysts for theatre automation supervision.")
    elif readiness_level == "strained":
        _penalise(6, "Readiness strained; prioritise theatre handovers.")
    elif readiness_level in {"steady", "reinforced"}:
        _boost(2, "Readiness supports theatre automation.")

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status == "critical_backlog":
        _penalise(
            8,
            "Critical backlog impacting theatre automation reviews.",
            focus="Backlog clearance",
        )
        support_requirements.append("Assign coalition QA to clear automation backlog queues.")
    elif pressure_status in {"backlog", "prediction_gap", "prediction_gap_watch"}:
        _penalise(5, "Backlog elevated; theatre QA pairing advised.")

    sustain_status = str(sustainment.get("status", "")).lower()
    if sustain_status in {"surge", "mobilise"}:
        _penalise(5, "Sustainment surge; coordinate theatre logistics for automation support.")
    elif sustain_status in {"steady", "reinforced"}:
        _boost(2, "Sustainment steady for theatre automation support.")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"critical", "mobilise"}:
        _penalise(
            6,
            "Frontline support critical; ensure theatre automation prioritises urgent brigades.",
            focus="Frontline prioritisation",
        )
    elif frontline_status in {"reinforced", "steady"}:
        _boost(2, "Frontline support steady for automation delivery.")

    governance_score = governance.get("governance_score")
    if isinstance(governance_score, (int, float)):
        if governance_score < 55:
            _penalise(6, "Governance score low; theatre oversight councils need updates.")
        elif governance_score >= 80:
            _boost(3, "Governance councils reinforcing theatre automation controls.")

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status in {"at_risk", "degraded"}:
        _penalise(6, "Mission assurance degraded; brief theatre command on blockers.")
    elif assurance_status in {"assured", "reinforced"}:
        _boost(2, "Mission assurance supporting theatre execution.")

    resilience_status = str(resilience.get("status", "")).lower()
    if resilience_status in {"fragile", "stressed"}:
        _penalise(5, "Resilience stressed; protect theatre contingencies.")
    elif resilience_status in {"resilient", "reinforced"}:
        _boost(2, "Resilience posture supports theatre automation.")

    continuity_status = str(continuity.get("status", "")).lower()
    if continuity_status in {"degraded", "at_risk"}:
        _penalise(5, "Continuity degraded; align theatre continuity cells.")
    elif continuity_status in {"sustained", "stabilised"}:
        _boost(2, "Continuity supporting theatre ops.")

    recovery_status = str(recovery.get("status", "")).lower()
    if recovery_status in {"recover", "stabilise", "manual"}:
        _penalise(4, "Recovery underway; theatre automation needs stabilisation checks.")

    directives_status = str(directives.get("status", "")).lower()
    if directives_status in {"critical", "urgent"}:
        _penalise(5, "Command directives urgent; align theatre automation priorities.")
    elif directives_status in {"steady", "coordinated"}:
        _boost(2, "Command directives reinforcing theatre automation plan.")

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status in {"misaligned", "manual_bridge"}:
        _penalise(6, "Command alignment gap; theatre liaisons required.")
    elif alignment_status in {"aligned", "synchronised"}:
        _boost(3, "Command alignment supporting theatre coordination.")

    communication_status = str(communication.get("status", "")).lower()
    if communication_status in {"disrupted", "manual"}:
        _penalise(5, "Communication plan disrupted; escalate theatre messaging.")
    elif communication_status in {"focused", "steady"}:
        _boost(2, "Communications plan supporting theatre automation.")

    _collect_text(joint_ops.get("integration_channels"), command_channels)
    _collect_text(joint_ops.get("coalition_partners"), coalition_commanders)
    _collect_text(mission_control_channels, command_channels)
    _collect_text(overwatch.get("monitoring_channels"), command_channels)
    _collect_text(playbook.get("automation_channels"), command_channels)

    for track in joint_tracks:
        if isinstance(track, MutableMapping):
            _track_from("joint", track)
            _collect_text([track.get("theatre") or track.get("mode")], coordinating_theaters)

    for track in battle_tracks:
        if isinstance(track, MutableMapping):
            _track_from("battle", track)
            _collect_text([track.get("focus") or track.get("mode")], coordinating_theaters)

    for track in campaign_tracks:
        if isinstance(track, MutableMapping):
            _track_from("campaign", track)
            _collect_text([track.get("focus") or track.get("mode")], coordinating_theaters)

    _collect_text(frontline.get("priority_units"), coordinating_theaters)
    _collect_text(frontline.get("brigade_support"), watch_items)
    _collect_text(sustainment.get("support_corridors") or sustainment.get("resupply_windows"), support_requirements)

    _collect_text(joint_ops.get("recommended_actions"), recommended_actions)
    _collect_text(campaign.get("recommended_actions"), recommended_actions)
    _collect_text(battle.get("recommended_actions"), recommended_actions)
    _collect_text(mission_control.get("recommended_actions"), recommended_actions)
    _collect_text(guardrails.get("recommended_actions"), recommended_actions)
    _collect_text(overwatch.get("recommended_actions"), recommended_actions)
    _collect_text(playbook.get("recommended_actions"), recommended_actions)
    _collect_text(frontline.get("recommended_actions"), recommended_actions)
    _collect_text(sustainment.get("recommended_actions"), recommended_actions)
    _collect_text(directives.get("recommended_actions"), recommended_actions)
    _collect_text(alignment.get("recommended_actions"), recommended_actions)
    _collect_text(communication.get("recommended_actions"), recommended_actions)

    prompts.extend(
        [
            "Узгодьте театральні вікна запуску з оперативним штабом та союзними офіцерами.",
            "Поширте обмеження автоматизації серед чергових командирів театрів.",
        ]
    )

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    def _dedupe_tracks(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[Tuple[Any, ...]] = set()
        ordered: List[Dict[str, Any]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            key = (
                entry.get("name"),
                entry.get("lead"),
                entry.get("mode"),
                entry.get("readiness"),
                entry.get("window_hours"),
                entry.get("status"),
                entry.get("source"),
            )
            if key in seen:
                continue
            seen.add(key)
            ordered.append(entry)
        return ordered

    drivers = _dedupe(drivers)
    focus_areas = _dedupe(focus_areas)
    watch_items = _dedupe(watch_items)
    recommended_actions = _dedupe(recommended_actions)
    prompts = _dedupe(prompts)
    coordinating_theaters = _dedupe(coordinating_theaters)
    command_channels = sorted({channel for channel in command_channels if channel})
    coalition_commanders = _dedupe(coalition_commanders)
    support_requirements = _dedupe(support_requirements)
    command_tracks = _dedupe_tracks(command_tracks)

    next_window: Optional[float] = None
    positive_windows = [value for value in windows if value > 0]
    if positive_windows:
        next_window = round(min(positive_windows), 2)

    status = "synchronised_command"
    if severity >= 34 or score < 55:
        status = "manual_bridge"
    elif severity >= 22 or score < 65:
        status = "paired_command"
    elif severity >= 12 or score < 75:
        status = "command_watch"
    elif score >= 92 and severity <= 10:
        status = "mission_ready"

    payload: Dict[str, Any] = {
        "status": status,
        "theater_command_score": round(score, 1),
    }
    if severity > 0:
        payload["severity_index"] = severity
    if next_window is not None:
        payload["command_window_hours"] = next_window
    if drivers:
        payload["drivers"] = drivers
    if focus_areas:
        payload["focus_areas"] = focus_areas
    if watch_items:
        payload["watch_items"] = watch_items
    if recommended_actions:
        payload["recommended_actions"] = recommended_actions
    if prompts:
        payload["ukrainian_operator_prompts"] = prompts
    if coordinating_theaters:
        payload["coordinating_theaters"] = coordinating_theaters
    if command_channels:
        payload["command_channels"] = command_channels
    if coalition_commanders:
        payload["coalition_commanders"] = coalition_commanders
    if support_requirements:
        payload["support_requirements"] = support_requirements
    if command_tracks:
        payload["command_tracks"] = command_tracks

    return payload if payload else None



def _derive_automation_supreme_command(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fuse theatre automation telemetry into a supreme automation command view."""

    theater = brief.get("automation_theater_command") or {}
    joint_ops = brief.get("automation_joint_operations") or {}
    campaign = brief.get("automation_campaign_orchestration") or {}
    battle = brief.get("automation_battle_management") or {}
    mission_control = brief.get("automation_mission_control") or {}
    overwatch = brief.get("automation_overwatch") or {}
    guardrails = brief.get("automation_guardrails") or {}
    playbook = brief.get("automation_playbook") or {}
    autonomy = brief.get("automation_autonomy") or {}
    failsafes = brief.get("automation_failsafes") or {}
    validation = brief.get("automation_validation") or {}
    deployment = brief.get("automation_deployment") or {}
    battle_tracks = battle.get("coordination_tracks") or []
    campaign_tracks = campaign.get("orchestration_tracks") or []
    joint_tracks = joint_ops.get("joint_operation_tracks") or []
    mission_tracks = mission_control.get("mission_tracks") or []
    overwatch_tracks = overwatch.get("oversight_tracks") or []

    directives = brief.get("command_directives") or {}
    alignment = brief.get("command_alignment") or {}
    communication = brief.get("communication_plan") or {}
    governance = brief.get("operational_governance") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    sustainment = brief.get("resource_sustainment") or {}
    frontline = brief.get("frontline_support") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}

    if not any(
        [
            theater,
            joint_ops,
            campaign,
            battle,
            mission_control,
            overwatch,
            guardrails,
            playbook,
            autonomy,
            failsafes,
            validation,
            deployment,
            directives,
            alignment,
            communication,
            governance,
            assurance,
            resilience,
            continuity,
            recovery,
            sustainment,
            frontline,
            readiness,
            pressure,
        ]
    ):
        return None

    score = 94.0
    severity = 0
    drivers: List[str] = []
    focus_areas: List[str] = []
    watch_items: List[str] = []
    recommended_actions: List[str] = []
    prompts: List[str] = []
    command_nodes: List[str] = []
    integration_channels: List[str] = []
    coalition_liaisons: List[str] = []
    dependencies: List[str] = []
    windows: List[float] = []
    global_tracks: List[Dict[str, Any]] = []

    def _penalise(
        amount: float,
        note: Optional[str] = None,
        *,
        focus: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            watch_items.append(str(note))
        if focus:
            focus_areas.append(str(focus))
        if prompt:
            prompts.append(str(prompt))

    def _boost(amount: float, note: Optional[str] = None, *, focus: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            drivers.append(str(note))
        if focus:
            focus_areas.append(str(focus))

    def _collect_text(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if not value:
                continue
            target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for value in values:
            key = value.strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(key)
        return result

    def _dedupe_tracks(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[Tuple[str, str, str]] = set()
        result: List[Dict[str, Any]] = []
        for entry in entries:
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            lead = str(entry.get("lead", "")).strip()
            source = str(entry.get("source", "")).strip()
            key = (name, lead, source)
            if key in seen:
                continue
            seen.add(key)
            result.append(entry)
        return result

    def _track_from(source: str, track: MutableMapping[str, Any]) -> None:
        name = track.get("name") or track.get("track") or track.get("task")
        if not name:
            return
        entry: Dict[str, Any] = {"name": str(name)}
        lead = track.get("lead") or track.get("owner") or track.get("team")
        if lead:
            entry["lead"] = str(lead)
            coalition_liaisons.append(str(lead))
        readiness_tag = track.get("readiness") or track.get("status")
        if readiness_tag:
            entry["readiness"] = str(readiness_tag)
        mode = track.get("mode") or track.get("priority")
        if mode:
            entry["mode"] = str(mode)
        window_value = track.get("window_hours") or track.get("window")
        if isinstance(window_value, (float, int)):
            entry["window_hours"] = float(window_value)
            _register_window(float(window_value))
        source_tag = track.get("source") or source
        if source_tag:
            entry["source"] = str(source_tag)
        status_tag = track.get("status")
        if status_tag:
            entry["status"] = str(status_tag)
        global_tracks.append(entry)

    def _collect_actions(values: Optional[Iterable[Any]], *, prompt: Optional[str] = None) -> None:
        for value in values or []:
            if not value:
                continue
            recommended_actions.append(str(value))
            if prompt:
                prompts.append(str(prompt).format(action=value))

    theater_status = str(theater.get("status", "")).lower()
    if not theater:
        _penalise(
            18,
            note="No theatre automation command telemetry available.",
            focus="Establish automation theatre command coverage",
            prompt="Відсутній контроль автоматизації театрів — зведіть дані вручну.",
        )
    elif theater_status in {"manual_bridge", "manual_override", "manual"}:
        _penalise(
            20,
            note="Theatre command automation is in manual bridge.",
            focus="Stabilise theatre automation command",
            prompt="Театральні автоматизовані рішення на ручному мосту — виділіть офіцера для координації.",
        )
    elif theater_status in {"paired_command", "command_watch"}:
        _penalise(12, note="Theatre command requires paired automation oversight.")
    elif theater_status == "mission_ready":
        _boost(4, note="Theatre automation command is mission ready.")

    joint_status = str(joint_ops.get("status", "")).lower()
    if joint_status in {"manual_bridge", "manual"}:
        _penalise(12, note="Joint automation requires manual coalition bridge.")
    elif joint_status in {"coalition_ready", "mission_ready"}:
        _boost(3, note="Coalition automation is synchronised.")

    campaign_status = str(campaign.get("status", "")).lower()
    if campaign_status in {"manual_bridge", "manual"}:
        _penalise(10, note="Campaign orchestration is manual.")
    elif campaign_status in {"coordinated", "mission_ready"}:
        _boost(2, note="Campaign orchestration is coordinated.")

    mission_status = str(mission_control.get("status", "")).lower()
    if mission_status in {"manual_control", "manual"}:
        _penalise(10, note="Mission control automation held manually.")
    elif mission_status in {"mission_ready", "guided"}:
        _boost(2, note="Mission control automation online.")

    overwatch_status = str(overwatch.get("status", "")).lower()
    if overwatch_status in {"manual_overwatch", "manual"}:
        _penalise(6, note="Automation overwatch needs manual staffing.")
    elif overwatch_status in {"mission_ready", "active_watch"}:
        _boost(2, note="Automation overwatch synchronised.")

    autonomy_status = str(autonomy.get("status", "")).lower()
    if autonomy_status in {"manual_only", "manual"}:
        _penalise(8, note="Automation autonomy restricted to manual mode.")
    elif autonomy_status in {"mission_ready", "trusted"}:
        _boost(2, note="Automation autonomy trusted in priority lanes.")

    guardrail_status = str(guardrails.get("status", "")).lower()
    if guardrail_status in {"locked_down", "manual"}:
        _penalise(6, note="Automation guardrails locked down.")

    failsafe_status = str(failsafes.get("status", "")).lower()
    if failsafe_status in {"manual", "degraded"}:
        _penalise(5, note="Automation failsafes degraded; confirm fallback teams.")

    validation_status = str(validation.get("status", "")).lower()
    if validation_status in {"manual_review", "manual"}:
        _penalise(4, note="Automation validation requires manual review.")

    deployment_status = str(deployment.get("status", "")).lower()
    if deployment_status in {"hold", "manual"}:
        _penalise(5, note="Automation deployment is on hold.")
    elif deployment_status in {"mission_ready", "ready"}:
        _boost(2, note="Deployment green across theatres.")

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level in {"critical", "degraded"}:
        _penalise(12, note="Response readiness degraded across commands.")
    elif readiness_level in {"ready", "steady"}:
        _boost(3, note="Response readiness supports automation command.")

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "surge"}:
        _penalise(8, note="Analyst backlog threatens automation command speed.")

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"critical", "surge"}:
        _penalise(6, note="Sustainment surge required for automation command support.")

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"critical", "degraded"}:
        _penalise(6, note="Frontline automation support degraded.")

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status in {"at_risk", "critical"}:
        _penalise(6, note="Mission assurance is at risk; confirm command priorities.")
    elif assurance_status in {"steady", "protected"}:
        _boost(2, note="Mission assurance supporting automation command.")

    resilience_status = str(resilience.get("status", "")).lower()
    if resilience_status in {"fragile", "at_risk"}:
        _penalise(6, note="Operational resilience fragile for supreme automation command.")
    elif resilience_status in {"resilient", "reinforced"}:
        _boost(2, note="Operational resilience reinforces automation command.")

    continuity_status = str(continuity.get("status", "")).lower()
    if continuity_status in {"degraded", "at_risk"}:
        _penalise(4, note="Operational continuity degraded; plan contingencies.")

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status in {"misaligned", "at_risk"}:
        _penalise(6, note="Command alignment gaps detected across theatres.")

    directives_status = str(directives.get("status", "")).lower()
    if directives_status in {"critical", "at_risk"}:
        _penalise(6, note="Command directives indicate elevated automation risk.")

    governance_score = governance.get("governance_score")
    if isinstance(governance_score, (int, float)):
        if governance_score >= 80:
            _boost(2, note="Governance cadence reinforces automation oversight.")
        elif governance_score < 55:
            _penalise(5, note="Governance cadence insufficient for supreme automation command.")

    for tracks, source in [
        (theater.get("command_tracks"), "theater"),
        (joint_tracks, "joint"),
        (campaign_tracks, "campaign"),
        (battle_tracks, "battle"),
        (mission_tracks, "mission"),
        (overwatch_tracks, "overwatch"),
    ]:
        if not isinstance(tracks, Iterable):
            continue
        for track in tracks:
            if isinstance(track, MutableMapping):
                _track_from(source, track)

    for section in [
        theater,
        joint_ops,
        campaign,
        battle,
        mission_control,
        overwatch,
        guardrails,
        playbook,
        autonomy,
        failsafes,
        validation,
        deployment,
        directives,
        alignment,
        communication,
        governance,
        assurance,
        resilience,
        continuity,
        recovery,
        sustainment,
        frontline,
    ]:
        _collect_text(section.get("recommended_actions"), recommended_actions)

    _collect_text(theater.get("command_channels"), integration_channels)
    _collect_text(joint_ops.get("integration_channels"), integration_channels)
    _collect_text(campaign.get("integration_channels"), integration_channels)
    _collect_text(mission_control.get("mission_channels"), integration_channels)
    _collect_text(overwatch.get("monitoring_channels"), integration_channels)
    _collect_text(guardrails.get("monitoring_channels"), integration_channels)
    _collect_text(playbook.get("automation_channels"), integration_channels)

    _collect_text(theater.get("support_requirements"), dependencies)
    _collect_text(joint_ops.get("support_requirements"), dependencies)
    _collect_text(sustainment.get("resource_needs"), dependencies)
    _collect_text(frontline.get("priority_units"), dependencies)
    _collect_text(frontline.get("support_gaps"), dependencies)

    _collect_text(theater.get("coordinating_theaters"), command_nodes)
    _collect_text(joint_ops.get("coalition_partners"), command_nodes)
    _collect_text(campaign.get("campaign_nodes"), command_nodes)
    _collect_text(battle.get("coordination_cells"), command_nodes)

    _collect_text(theater.get("coalition_commanders"), coalition_liaisons)
    _collect_text(joint_ops.get("coalition_liaisons"), coalition_liaisons)
    _collect_text(campaign.get("campaign_leads"), coalition_liaisons)
    _collect_text(mission_control.get("mission_leads"), coalition_liaisons)

    _collect_text(playbook.get("ukrainian_operator_prompts"), prompts)
    _collect_text(guardrails.get("ukrainian_operator_prompts"), prompts)
    _collect_text(mission_control.get("ukrainian_operator_prompts"), prompts)
    _collect_text(overwatch.get("ukrainian_operator_prompts"), prompts)
    _collect_text(theater.get("ukrainian_operator_prompts"), prompts)

    if severity >= 40 or score < 52:
        status = "manual_override"
    elif severity >= 28 or score < 62:
        status = "coalition_bridge"
    elif severity >= 18 or score < 72:
        status = "paired_command"
    elif severity >= 10 or score < 82:
        status = "command_watch"
    elif score >= 95 and severity <= 8:
        status = "mission_ready"
    else:
        status = "strategic_sync"

    next_window: Optional[float] = None
    if windows:
        next_window = min(windows)

    payload: Dict[str, Any] = {
        "status": status,
        "supreme_command_score": round(score, 1),
    }

    if severity > 0:
        payload["severity_index"] = severity
    if next_window is not None:
        payload["command_window_hours"] = next_window

    if drivers:
        payload["drivers"] = _dedupe(drivers)
    if focus_areas:
        payload["focus_areas"] = _dedupe(focus_areas)
    if watch_items:
        payload["watch_items"] = _dedupe(watch_items)
    if recommended_actions:
        payload["recommended_actions"] = _dedupe(recommended_actions)
    if prompts:
        payload["ukrainian_operator_prompts"] = _dedupe(prompts)
    if command_nodes:
        payload["command_nodes"] = _dedupe(command_nodes)
    if integration_channels:
        payload["integration_channels"] = _dedupe(integration_channels)
    if coalition_liaisons:
        payload["coalition_liaisons"] = _dedupe(coalition_liaisons)
    if dependencies:
        payload["support_dependencies"] = _dedupe(dependencies)

    deduped_tracks = _dedupe_tracks(global_tracks)
    if deduped_tracks:
        payload["command_tracks"] = deduped_tracks

    return payload if payload else None



def _derive_automation_strategic_convergence(
    brief: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Blend national automation telemetry into a strategic convergence view."""

    supreme = brief.get("automation_supreme_command") or {}
    theater = brief.get("automation_theater_command") or {}
    joint_ops = brief.get("automation_joint_operations") or {}
    campaign = brief.get("automation_campaign_orchestration") or {}
    battle = brief.get("automation_battle_management") or {}
    mission_control = brief.get("automation_mission_control") or {}
    overwatch = brief.get("automation_overwatch") or {}
    guardrails = brief.get("automation_guardrails") or {}
    playbook = brief.get("automation_playbook") or {}
    autonomy = brief.get("automation_autonomy") or {}
    failsafes = brief.get("automation_failsafes") or {}
    validation = brief.get("automation_validation") or {}
    deployment = brief.get("automation_deployment") or {}

    frontline = brief.get("frontline_support") or {}
    sustainment = brief.get("resource_sustainment") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    directives = brief.get("command_directives") or {}
    alignment = brief.get("command_alignment") or {}
    communication = brief.get("communication_plan") or {}
    governance = brief.get("operational_governance") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    risk_register = brief.get("operational_risks") or {}

    if not any(
        [
            supreme,
            theater,
            joint_ops,
            campaign,
            battle,
            mission_control,
            overwatch,
            guardrails,
            playbook,
            autonomy,
            failsafes,
            validation,
            deployment,
            frontline,
            sustainment,
            readiness,
            pressure,
            directives,
            alignment,
            communication,
            governance,
            assurance,
            resilience,
            continuity,
            recovery,
            risk_register,
        ]
    ):
        return None

    score = 93.0
    severity = 0
    drivers: List[str] = []
    focus_areas: List[str] = []
    watch_items: List[str] = []
    recommended_actions: List[str] = []
    prompts: List[str] = []
    national_nodes: List[str] = []
    coalition_partners: List[str] = []
    strategic_channels: List[str] = []
    dependencies: List[str] = []
    support_requirements: List[str] = []
    windows: List[float] = []
    cross_domain_tracks: List[Dict[str, Any]] = []

    def _penalise(
        amount: float,
        note: Optional[str] = None,
        *,
        focus: Optional[str] = None,
        prompt: Optional[str] = None,
        action: Optional[str] = None,
    ) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            watch_items.append(str(note))
        if focus:
            focus_areas.append(str(focus))
        if prompt:
            prompts.append(str(prompt))
        if action:
            recommended_actions.append(str(action))

    def _boost(amount: float, note: Optional[str] = None, *, focus: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if note:
            drivers.append(str(note))
        if focus:
            focus_areas.append(str(focus))

    def _collect_text(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if not value:
                continue
            target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    def _collect_tracks(
        entries: Optional[Iterable[MutableMapping[str, Any]]],
        *,
        source: str,
    ) -> None:
        for entry in entries or []:
            if not isinstance(entry, MutableMapping):
                continue
            name = entry.get("name") or entry.get("track") or entry.get("task")
            if not name:
                continue
            track: Dict[str, Any] = {"name": str(name)}
            lead = entry.get("lead") or entry.get("owner") or entry.get("team")
            if lead:
                track["lead"] = str(lead)
                coalition_partners.append(str(lead))
            readiness_tag = entry.get("readiness") or entry.get("status")
            if readiness_tag:
                track["readiness"] = str(readiness_tag)
            mode = entry.get("mode") or entry.get("phase")
            if mode:
                track["mode"] = str(mode)
            window_value = entry.get("window_hours") or entry.get("window")
            if isinstance(window_value, (float, int)):
                track["window_hours"] = float(window_value)
                _register_window(float(window_value))
            source_tag = entry.get("source") or source
            if source_tag:
                track["source"] = str(source_tag)
            status_tag = entry.get("status")
            if status_tag:
                track["status"] = str(status_tag)
            cross_domain_tracks.append(track)

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        result: List[str] = []
        for value in values:
            key = str(value).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(key)
        return result

    def _dedupe_tracks(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[Tuple[str, str, str]] = set()
        result: List[Dict[str, Any]] = []
        for entry in entries:
            name = str(entry.get("name", "")).strip()
            if not name:
                continue
            lead = str(entry.get("lead", "")).strip()
            source = str(entry.get("source", "")).strip()
            key = (name, lead, source)
            if key in seen:
                continue
            seen.add(key)
            result.append(entry)
        return result

    def _import_payload(payload: Dict[str, Any], *, source: str) -> None:
        _collect_text(payload.get("drivers"), drivers)
        _collect_text(payload.get("focus_areas"), focus_areas)
        _collect_text(payload.get("watch_items"), watch_items)
        _collect_text(payload.get("recommended_actions"), recommended_actions)
        _collect_text(payload.get("ukrainian_operator_prompts"), prompts)
        _collect_text(payload.get("support_dependencies"), dependencies)
        _collect_text(payload.get("support_requirements"), support_requirements)
        _collect_tracks(payload.get("command_tracks"), source=source)
        _collect_tracks(payload.get("coordination_tracks"), source=source)
        _collect_tracks(payload.get("cross_domain_tracks"), source=source)
        _collect_tracks(payload.get("orchestration_tracks"), source=source)

    _import_payload(supreme, source="supreme")
    _import_payload(theater, source="theater")
    _import_payload(joint_ops, source="joint")
    _import_payload(campaign, source="campaign")
    _import_payload(battle, source="battle")
    _import_payload(mission_control, source="mission_control")
    _import_payload(overwatch, source="overwatch")
    _import_payload(playbook, source="playbook")
    _import_payload(guardrails, source="guardrails")
    _import_payload(autonomy, source="autonomy")
    _import_payload(failsafes, source="failsafes")
    _import_payload(validation, source="validation")
    _import_payload(deployment, source="deployment")

    _collect_text(supreme.get("command_nodes"), national_nodes)
    _collect_text(theater.get("command_nodes"), national_nodes)
    _collect_text(theater.get("coordinating_theaters"), national_nodes)
    _collect_text(joint_ops.get("coalition_partners"), coalition_partners)
    _collect_text(campaign.get("coalition_partners"), coalition_partners)
    _collect_text(battle.get("coalition_partners"), coalition_partners)
    _collect_text(frontline.get("priority_units"), coalition_partners)

    _collect_text(supreme.get("integration_channels"), strategic_channels)
    _collect_text(theater.get("command_channels"), strategic_channels)
    _collect_text(joint_ops.get("integration_channels"), strategic_channels)
    _collect_text(campaign.get("integration_channels"), strategic_channels)
    _collect_text(mission_control.get("mission_channels"), strategic_channels)
    _collect_text(overwatch.get("monitoring_channels"), strategic_channels)
    _collect_text(playbook.get("automation_channels"), strategic_channels)
    _collect_text(guardrails.get("monitoring_channels"), strategic_channels)

    _collect_text(sustainment.get("resource_needs"), dependencies)
    _collect_text(sustainment.get("allocation_plan"), dependencies)
    _collect_text(frontline.get("support_gaps"), dependencies)
    _collect_text(frontline.get("support_requirements"), support_requirements)
    _collect_text(recovery.get("dependencies"), dependencies)
    _collect_text(continuity.get("constraints"), dependencies)
    _collect_text(resilience.get("weak_spots"), dependencies)
    _collect_text(risk_register.get("risks"), watch_items)

    for payload in [
        supreme,
        theater,
        joint_ops,
        campaign,
        battle,
        mission_control,
        overwatch,
        guardrails,
        playbook,
        autonomy,
        failsafes,
        validation,
        deployment,
    ]:
        _register_window(payload.get("command_window_hours"))
        _register_window(payload.get("next_review_hours"))
        _register_window(payload.get("mission_window_hours"))
        _register_window(payload.get("monitoring_window_hours"))
        _register_window(payload.get("recovery_window_hours"))

    supreme_status = str(supreme.get("status", "")).lower()
    if supreme_status in {"manual_override", "manual_bridge"}:
        _penalise(
            24,
            "National automation is under manual override.",
            focus="Restore supreme automation synchronisation",
            prompt="Організуйте ручне управління до відновлення національної автоматизації.",
            action="Coordinate rapid recovery of supreme automation command.",
        )
    elif supreme_status in {"coalition_bridge", "paired_command", "command_watch"}:
        _penalise(
            10,
            "Supreme automation command requires close supervision.",
            focus="Stabilise national automation governance",
        )
    elif supreme_status in {"mission_ready", "strategic_sync"}:
        _boost(4, "Supreme automation posture is supporting convergence.")

    theater_status = str(theater.get("status", "")).lower()
    if theater_status in {"manual_bridge", "command_watch", "paired_command"}:
        _penalise(
            8,
            "Theatre command automation is constrained.",
            focus="Reinforce theatre automation",
            prompt="Підтягніть театри до стратегічного темпу автоматизації.",
        )
    elif theater_status in {"mission_ready", "synchronised_command"}:
        _boost(3, "Theatre command is aligned with strategic automation.")

    joint_status = str(joint_ops.get("status", "")).lower()
    if joint_status in {"manual_bridge", "manual_override"}:
        _penalise(
            10,
            "Coalition automation bridge is active.",
            focus="Secure coalition interfaces",
            prompt="Узгодьте канали з союзниками та підтвердьте готовність до автоматизації.",
        )
    elif joint_status in {"coalition_ready", "mission_ready"}:
        _boost(2, "Coalition automation posture is supporting convergence.")

    guardrail_status = str(guardrails.get("status", "")).lower()
    if guardrail_status in {"manual", "pilot", "degraded"}:
        _penalise(
            12,
            "Automation guardrails are degraded.",
            focus="Restore guardrail coverage",
            prompt="Перевірте журнали guardrails та поверніть автоматичний контроль.",
            action="Initiate guardrail recovery workflow.",
        )

    autonomy_status = str(autonomy.get("status", "")).lower()
    if autonomy_status in {"manual", "manual_bridge"}:
        _penalise(
            10,
            "Automation autonomy requires manual oversight.",
            focus="Balance supervision tiers",
        )
    elif autonomy_status in {"mission_ready", "trusted"}:
        _boost(3, "Automation autonomy cleared for trusted execution.")

    failsafe_status = str(failsafes.get("status", "")).lower()
    if failsafe_status in {"manual", "critical"}:
        _penalise(
            9,
            "Automation failsafes are under manual posture.",
            focus="Verify fallback readiness",
            prompt="Проведіть відпрацювання failsafe з українськими командами.",
        )

    validation_status = str(validation.get("status", "")).lower()
    if validation_status in {"manual_review", "degraded"}:
        _penalise(
            6,
            "Automation validation backlog detected.",
            focus="Accelerate validation tracks",
        )

    deployment_status = str(deployment.get("status", "")).lower()
    if deployment_status in {"hold", "guarded"}:
        _penalise(
            5,
            "Automation deployment is paused.",
            focus="Clear deployment prerequisites",
        )
    elif deployment_status in {"ready", "mission_ready"}:
        _boost(2, "Deployment posture ready to scale automation releases.")

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level in {"critical", "degraded"}:
        _penalise(
            10,
            "Response readiness is constraining automation scale.",
            focus="Reinforce response cells",
            prompt="Перекиньте чергові групи підтримки до автоматизованих напрямків.",
        )
    elif readiness_level in {"reinforced", "elevated"}:
        _boost(3, "Response teams ready to supervise automation surge.")

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "severe_backlog"}:
        _penalise(
            9,
            "Analyst backlog is building.",
            focus="Reduce automation tasking load",
        )

    frontline_status = str(frontline.get("status", "")).lower()
    if frontline_status in {"critical", "strained"}:
        _penalise(
            8,
            "Frontline support posture is strained.",
            focus="Stabilise brigade automation links",
            prompt="Передайте бригадам чіткі інструкції щодо автоматизованих каналів.",
        )

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "critical"}:
        _penalise(
            6,
            "Resupply tempo is impacting automation runs.",
            focus="Secure logistics for automation tasks",
        )

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status in {"at_risk", "critical"}:
        _penalise(
            6,
            "Mission assurance signals elevated automation risk.",
        )

    resilience_status = str(resilience.get("status", "")).lower()
    if resilience_status in {"fragile", "strained"}:
        _penalise(
            5,
            "Operational resilience is weak.",
            focus="Fortify redundant automation pathways",
        )

    continuity_status = str(continuity.get("status", "")).lower()
    if continuity_status in {"disrupted", "at_risk"}:
        _penalise(
            5,
            "Continuity constraints detected.",
            focus="Protect critical automation services",
        )

    recovery_status = str(recovery.get("status", "")).lower()
    if recovery_status in {"stabilise", "recover"}:
        _boost(2, "Recovery roadmap reinforcing strategic automation.")

    governance_score = governance.get("governance_score")
    if isinstance(governance_score, (int, float)) and governance_score < 60:
        _penalise(6, "Governance cadence is below target.")

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status in {"misaligned", "fragmented"}:
        _penalise(
            6,
            "Command alignment gaps reduce automation convergence.",
            focus="Close command alignment loops",
        )

    directives_status = str(directives.get("status", "")).lower()
    if directives_status in {"critical", "surge"}:
        _penalise(4, "Directive load indicates elevated automation demand.")

    communication_status = str(communication.get("status", "")).lower()
    if communication_status in {"disrupted", "manual"}:
        _penalise(
            5,
            "Communication cadence is limiting automation reach.",
            focus="Reestablish automation comms",
        )

    risk_severity = risk_register.get("severity_score")
    if isinstance(risk_severity, (int, float)) and risk_severity > 70:
        _penalise(
            8,
            "Operational risk register flags automation blockers.",
            focus="Mitigate top automation risks",
        )

    for note in supreme.get("recommended_actions", []) or []:
        recommended_actions.append(str(note))
    for note in theater.get("recommended_actions", []) or []:
        recommended_actions.append(str(note))
    for note in joint_ops.get("recommended_actions", []) or []:
        recommended_actions.append(str(note))
    for note in campaign.get("recommended_actions", []) or []:
        recommended_actions.append(str(note))

    next_window: Optional[float] = None
    positive_windows = [value for value in windows if value > 0]
    if positive_windows:
        next_window = min(positive_windows)

    status = "strategic_alignment"
    if severity >= 36 or score < 50:
        status = "manual_bridge"
    elif severity >= 24 or score < 60:
        status = "stabilisation_watch"
    elif severity >= 14 or score < 72:
        status = "coordinated_recovery"
    elif score >= 95 and severity <= 8:
        status = "mission_ready"

    payload: Dict[str, Any] = {
        "status": status,
        "strategic_convergence_score": round(score, 1),
    }

    if severity > 0:
        payload["severity_index"] = severity
    if next_window is not None:
        payload["next_convergence_window_hours"] = round(float(next_window), 2)

    if drivers:
        payload["drivers"] = _dedupe(drivers)
    if focus_areas:
        payload["focus_areas"] = _dedupe(focus_areas)
    if watch_items:
        payload["watch_items"] = _dedupe(watch_items)
    if recommended_actions:
        payload["recommended_actions"] = _dedupe(recommended_actions)
    if prompts:
        payload["ukrainian_operator_prompts"] = _dedupe(prompts)
    if national_nodes:
        payload["national_command_nodes"] = _dedupe(national_nodes)
    if coalition_partners:
        payload["coalition_partners"] = _dedupe(coalition_partners)
    if strategic_channels:
        payload["strategic_channels"] = _dedupe(strategic_channels)
    if dependencies:
        payload["strategic_dependencies"] = _dedupe(dependencies)
    if support_requirements:
        payload["support_requirements"] = _dedupe(support_requirements)

    deduped_tracks = _dedupe_tracks(cross_domain_tracks)
    if deduped_tracks:
        payload["cross_domain_tracks"] = deduped_tracks

    return payload if payload else None



def _derive_operational_governance(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Summarise the governance cadence required to steer the operation."""

    transformation = brief.get("operational_transformation") or {}
    recovery = brief.get("operational_recovery") or {}
    continuity = brief.get("operational_continuity") or {}
    resilience = brief.get("operational_resilience") or {}
    assurance = brief.get("mission_assurance") or {}
    sustainment = brief.get("resource_sustainment") or {}
    alignment = brief.get("command_alignment") or {}
    directives = brief.get("command_directives") or {}
    communication = brief.get("communication_plan") or {}
    risks = brief.get("operational_risks") or {}
    support = brief.get("support_priorities") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    contingency = brief.get("contingency_plans") or {}
    outlook = brief.get("operational_outlook") or {}
    escalation = brief.get("escalation_readiness") or {}

    if not any(
        [
            transformation,
            recovery,
            continuity,
            resilience,
            assurance,
            sustainment,
            alignment,
            directives,
            communication,
            risks,
            support,
            readiness,
            pressure,
            contingency,
            outlook,
            escalation,
        ]
    ):
        return None

    score = 100.0
    compliance_gaps: List[str] = []
    oversight_focus: List[str] = []
    oversight_drivers: List[str] = []
    watch_items: List[str] = []
    metrics: List[str] = []
    actions: List[str] = []
    councils: List[Dict[str, Any]] = []
    review_windows: List[float] = []

    def _penalise(amount: float, note: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = max(0.0, score - float(amount))
        if note:
            compliance_gaps.append(str(note))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            review_windows.append(round(float(value), 2))

    def _collect_actions(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                text = str(value)
                actions.append(text)

    def _collect_focus(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                oversight_focus.append(str(value))

    def _collect_drivers(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                oversight_drivers.append(str(value))

    def _collect_watch(values: Optional[Iterable[Any]], *, prefix: Optional[str] = None) -> None:
        for value in values or []:
            if not value:
                continue
            text = str(value)
            if prefix:
                text = f"{prefix}: {text}"
            watch_items.append(text)

    def _add_metric(label: str, value: Any) -> None:
        if value is None:
            return
        metrics.append(f"{label}: {value}")

    def _add_council(
        name: Optional[str],
        *,
        status: Optional[str] = None,
        focus: Optional[str] = None,
        window: Optional[float] = None,
        actions_bucket: Optional[Iterable[Any]] = None,
        drivers_bucket: Optional[Iterable[Any]] = None,
    ) -> None:
        if not name:
            return
        entry: Dict[str, Any] = {"name": str(name)}
        if status:
            entry["status"] = str(status)
        if focus:
            entry["focus"] = str(focus)
        if isinstance(window, (float, int)) and window > 0:
            entry["next_review_hours"] = round(float(window), 2)
            _register_window(window)
        collected_actions: List[str] = []
        for value in actions_bucket or []:
            if value:
                text = str(value)
                collected_actions.append(text)
                actions.append(text)
        if collected_actions:
            entry["actions"] = collected_actions
        collected_drivers: List[str] = []
        for value in drivers_bucket or []:
            if value:
                text = str(value)
                collected_drivers.append(text)
                oversight_drivers.append(text)
        if collected_drivers:
            entry["drivers"] = collected_drivers
        councils.append(entry)

    risk_score = risks.get("severity_score")
    if isinstance(risk_score, (float, int)):
        _add_metric("Risk severity", int(round(float(risk_score))))
        if risk_score >= 90:
            _penalise(35, "Critical risks need governance intervention")
        elif risk_score >= 75:
            _penalise(25, "High-severity risks awaiting review")
        elif risk_score >= 60:
            _penalise(15, "Elevated risks to monitor")
    if isinstance(risks.get("risk_count"), int) and risks["risk_count"] > 0:
        _add_metric("Open risks", risks["risk_count"])
    for risk in risks.get("risks", []) or []:
        if not isinstance(risk, dict):
            continue
        name = risk.get("name")
        severity = risk.get("severity")
        status = risk.get("status")
        if isinstance(severity, (int, float)) and severity >= 4:
            _collect_watch([name], prefix="Risk")
            if status:
                _collect_drivers([f"{name}: {status}"])
        if risk.get("review_window_hours"):
            _register_window(risk.get("review_window_hours"))

    alignment_score = alignment.get("alignment_score")
    if isinstance(alignment_score, (float, int)):
        _add_metric("Alignment score", int(round(float(alignment_score))))
        if alignment_score < 55:
            _penalise(25, "Command alignment is fragmented")
        elif alignment_score < 70:
            _penalise(15, "Command alignment drifting")
    alignment_status = str(alignment.get("status", ""))
    if alignment_status:
        _collect_focus(alignment.get("focus_areas"))
        _collect_drivers(alignment.get("drivers", []))
        _collect_watch(alignment.get("coordination_gaps", []), prefix="Gap")
        _collect_actions(alignment.get("recommended_actions"))
    _register_window(alignment.get("next_sync_hours"))

    directive_status = str(directives.get("status", ""))
    if directive_status:
        _collect_focus(directives.get("focus_areas"))
        _collect_drivers(directives.get("drivers", []))
        _collect_actions(directives.get("recommended_actions"))
        window = directives.get("planning_window_hours")
        if isinstance(window, (float, int)):
            _register_window(window)

    comm_status = str(communication.get("status", ""))
    if comm_status.lower() in {"escalated", "heightened"}:
        _penalise(10, "Communications cadence is under pressure")
    _collect_focus(communication.get("key_messages"))
    _collect_actions(communication.get("recommended_actions"))
    for audience in communication.get("audiences", []) or []:
        if not isinstance(audience, dict):
            continue
        cadence = audience.get("cadence_hours")
        if isinstance(cadence, (float, int)):
            _register_window(cadence)

    assurance_score = assurance.get("assurance_score")
    if isinstance(assurance_score, (float, int)):
        _add_metric("Assurance score", int(round(float(assurance_score))))
        if assurance_score < 55:
            _penalise(25, "Mission assurance critically low")
        elif assurance_score < 70:
            _penalise(15, "Mission assurance slipping")
    _collect_watch(assurance.get("blockers"), prefix="Blocker")
    _collect_drivers(assurance.get("drivers", []))
    _collect_actions(assurance.get("recommended_actions"))
    _register_window(assurance.get("next_checkpoint_hours"))

    resilience_score = resilience.get("resilience_score")
    if isinstance(resilience_score, (float, int)):
        _add_metric("Resilience score", int(round(float(resilience_score))))
        if resilience_score < 55:
            _penalise(20, "Operational resilience is fragile")
    _collect_watch(resilience.get("weak_spots"), prefix="Weak spot")
    _collect_drivers(resilience.get("drivers", []))
    _collect_actions(resilience.get("recommended_actions"))
    _register_window(resilience.get("stability_window_hours"))

    continuity_score = continuity.get("continuity_score")
    if isinstance(continuity_score, (float, int)):
        _add_metric("Continuity score", int(round(float(continuity_score))))
        if continuity_score < 60:
            _penalise(20, "Continuity constraints unresolved")
    _collect_watch(continuity.get("primary_constraints"), prefix="Constraint")
    _collect_watch(continuity.get("continuity_risks"), prefix="Continuity risk")
    _collect_actions(continuity.get("recommended_actions"))
    _register_window(continuity.get("continuity_horizon_hours"))

    recovery_score = recovery.get("recovery_score")
    if isinstance(recovery_score, (float, int)):
        _add_metric("Recovery score", int(round(float(recovery_score))))
    _collect_focus(recovery.get("insight_drivers"))
    _collect_actions(recovery.get("recommended_actions"))
    _collect_watch(recovery.get("critical_dependencies"), prefix="Dependency")
    _collect_watch(recovery.get("watch_items"), prefix="Recovery watch")
    _register_window(recovery.get("recovery_window_hours"))

    transformation_score = transformation.get("transformation_score")
    if isinstance(transformation_score, (float, int)):
        _add_metric("Transformation score", int(round(float(transformation_score))))
        if transformation_score < 60:
            _penalise(10, "Transformation momentum lagging")
    _collect_focus(transformation.get("transformation_focus"))
    _collect_actions(transformation.get("recommended_actions"))
    _collect_watch(transformation.get("constraints"), prefix="Transformation constraint")
    _register_window(transformation.get("next_review_hours"))

    support_status = str(support.get("status", ""))
    if support_status.lower() in {"mobilise", "reinforce"}:
        _penalise(10, "Support mobilisation required")
    _collect_drivers(support.get("drivers", []))
    _collect_actions(support.get("recommended_actions"))
    for entry in support.get("priorities", []) or []:
        if not isinstance(entry, dict):
            continue
        _collect_watch([entry.get("name")], prefix="Support priority")
        _register_window(entry.get("support_window_hours"))

    sustain_status = str(sustainment.get("status", ""))
    if sustain_status.lower() in {"surge", "accelerate"}:
        _penalise(10, "Sustainment posture elevated")
    _collect_drivers(sustainment.get("drivers", []))
    _collect_actions(sustainment.get("recommended_actions"))
    for entry in sustainment.get("resource_needs", []) or []:
        if not isinstance(entry, dict):
            continue
        _collect_watch([entry.get("name")], prefix="Resource need")
        _register_window(entry.get("support_window_hours"))

    readiness_level = str(readiness.get("level", ""))
    if readiness_level.lower() in {"critical", "high"}:
        _penalise(15, "Readiness level degraded")
    _collect_drivers(readiness.get("drivers", []))
    _collect_actions(readiness.get("priority_actions"))
    _register_window(readiness.get("support_window_hours"))

    pressure_status = str(pressure.get("status", ""))
    if pressure_status.lower() in {"critical_backlog", "backlog"}:
        _penalise(15, "Analyst backlog impacting governance")
    _collect_drivers(pressure.get("drivers", []))
    _collect_actions(pressure.get("recommended_actions"))
    _register_window(pressure.get("estimated_clearance_hours"))

    contingency_status = str(contingency.get("status", ""))
    if contingency_status:
        _collect_drivers(contingency.get("drivers", []))
        _collect_actions(contingency.get("recommended_actions"))
    for scenario in contingency.get("scenarios", []) or []:
        if not isinstance(scenario, dict):
            continue
        _collect_watch([scenario.get("name")], prefix="Scenario")
        _register_window(scenario.get("review_window_hours"))

    outlook_severity = outlook.get("severity") or outlook.get("severity_score")
    if isinstance(outlook_severity, (float, int)) and outlook_severity >= 75:
        _penalise(10, "Operational outlook indicates escalation")
    _collect_focus(outlook.get("focus_areas"))
    _collect_drivers(outlook.get("drivers", []))
    _collect_actions(outlook.get("recommended_actions"))
    _register_window(outlook.get("planning_horizon_hours"))

    escalation_status = str(escalation.get("status", ""))
    if escalation_status.lower() in {"escalate", "accelerate", "activate"}:
        _penalise(10, "Escalation matrix recommends activation")
    _collect_focus(escalation.get("focus_areas"))
    _collect_drivers(escalation.get("drivers", []))
    _collect_actions(escalation.get("recommended_actions"))
    _register_window(escalation.get("next_review_hours"))

    _add_council(
        "Command council",
        status=alignment_status or directive_status or comm_status,
        focus=(alignment.get("focus_areas") or directives.get("focus_areas") or [None])[0],
        window=directives.get("planning_window_hours") or alignment.get("next_sync_hours"),
        actions_bucket=(directives.get("recommended_actions") or [])
        + (alignment.get("recommended_actions") or []),
        drivers_bucket=(alignment.get("drivers") or []) + (directives.get("drivers") or []),
    )

    _add_council(
        "Recovery board",
        status=recovery.get("status") or continuity.get("status") or assurance.get("status"),
        focus=(recovery.get("insight_drivers") or continuity.get("primary_constraints") or [None])[0],
        window=recovery.get("recovery_window_hours") or continuity.get("continuity_horizon_hours"),
        actions_bucket=(recovery.get("recommended_actions") or [])
        + (continuity.get("recommended_actions") or [])
        + (assurance.get("recommended_actions") or []),
        drivers_bucket=(assurance.get("drivers") or []) + (continuity.get("drivers") or []),
    )

    _add_council(
        "Support steering",
        status=sustain_status or support_status or readiness_level,
        focus=(support.get("drivers") or sustainment.get("drivers") or [None])[0],
        window=sustainment.get("resupply_window_hours")
        if isinstance(sustainment.get("resupply_window_hours"), (float, int))
        else support.get("support_window_hours"),
        actions_bucket=(support.get("recommended_actions") or [])
        + (sustainment.get("recommended_actions") or [])
        + (pressure.get("recommended_actions") or []),
        drivers_bucket=(pressure.get("drivers") or []) + (sustainment.get("drivers") or []),
    )

    _add_council(
        "Strategy forum",
        status=transformation.get("status") or outlook.get("status"),
        focus=(transformation.get("transformation_focus") or outlook.get("focus_areas") or [None])[0],
        window=transformation.get("next_review_hours") or outlook.get("planning_horizon_hours"),
        actions_bucket=(transformation.get("recommended_actions") or [])
        + (outlook.get("recommended_actions") or [])
        + (communication.get("recommended_actions") or []),
        drivers_bucket=(transformation.get("enablers") or []) + (outlook.get("drivers") or []),
    )

    actions = list(dict.fromkeys(filter(None, actions)))
    oversight_focus = list(dict.fromkeys(filter(None, oversight_focus)))
    oversight_drivers = list(dict.fromkeys(filter(None, oversight_drivers)))
    compliance_gaps = list(dict.fromkeys(filter(None, compliance_gaps)))
    watch_items = list(dict.fromkeys(filter(None, watch_items)))
    metrics = list(dict.fromkeys(filter(None, metrics)))

    governance_score = int(round(score))
    if governance_score >= 85:
        status = "synchronised"
    elif governance_score >= 70:
        status = "coordinated"
    elif governance_score >= 55:
        status = "watch"
    else:
        status = "fragmented"

    payload: Dict[str, Any] = {
        "status": status,
        "governance_score": governance_score,
    }
    if councils:
        payload["oversight_councils"] = councils
    if compliance_gaps:
        payload["compliance_gaps"] = compliance_gaps
    if oversight_focus:
        payload["oversight_focus"] = oversight_focus
    if oversight_drivers:
        payload["drivers"] = oversight_drivers
    if watch_items:
        payload["watch_items"] = watch_items
    if metrics:
        payload["governance_metrics"] = metrics
    if actions:
        payload["recommended_actions"] = actions
    if review_windows:
        payload["next_review_hours"] = min(review_windows)

    return payload


def _derive_contingency_plans(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create contingency scenarios that help teams prepare escalation paths."""

    outlook = brief.get("operational_outlook") or {}
    directives = brief.get("command_directives") or {}
    posture = brief.get("operational_posture") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    confidence = brief.get("intelligence_confidence") or {}
    health = brief.get("health") or {}
    freshness = brief.get("data_freshness") or {}
    gaps = brief.get("intelligence_gaps") or []
    detection_quality = brief.get("detection_quality") or {}
    comms_plan = brief.get("communication_plan") or {}

    if not any(
        [
            outlook,
            directives,
            posture,
            readiness,
            pressure,
            support,
            confidence,
            health,
            freshness,
            gaps,
            detection_quality,
        ]
    ):
        return None

    severity = 0
    drivers: List[str] = []
    watch_items: List[str] = []
    actions: List[str] = []
    window_candidates: List[float] = []
    scenario_map: Dict[str, Dict[str, Any]] = {}

    def _add_driver(message: str) -> None:
        if message:
            drivers.append(message)

    def _add_watch(item: str) -> None:
        if item:
            watch_items.append(item)

    def _add_action(message: str) -> None:
        if message:
            actions.append(message)

    def _get_scenario(
        key: str,
        name: str,
        objective: str,
        *,
        priority: int,
    ) -> Dict[str, Any]:
        entry = scenario_map.setdefault(
            key,
            {
                "id": key,
                "name": name,
                "objective": objective,
                "triggers": [],
                "actions": [],
                "owners": [],
                "confidence": "moderate",
                "priority": priority,
            },
        )
        return entry

    def _add_trigger(entry: Dict[str, Any], trigger: str) -> None:
        if trigger:
            triggers = entry.setdefault("triggers", [])
            if trigger not in triggers:
                triggers.append(trigger)

    def _add_owner(entry: Dict[str, Any], owner: str) -> None:
        if owner:
            owners = entry.setdefault("owners", [])
            if owner not in owners:
                owners.append(owner)

    def _set_confidence(entry: Dict[str, Any], confidence_level: str) -> None:
        entry["confidence"] = confidence_level

    def _add_scenario_action(entry: Dict[str, Any], action: str) -> None:
        if action:
            actions_list = entry.setdefault("actions", [])
            if action not in actions_list:
                actions_list.append(action)
            _add_action(action)

    outlook_status = str(outlook.get("status", "")).lower()
    outlook_severity = outlook.get("severity_score")
    if isinstance(outlook_severity, (int, float)):
        if outlook_severity >= 18:
            severity += 6
            _add_driver("Operational outlook severity is nearing escalation thresholds.")
        elif outlook_severity >= 12:
            severity += 4
            _add_driver("Operational outlook signals accelerated planning horizons.")
        elif outlook_severity >= 6:
            severity += 2
            _add_driver("Operational outlook indicates focused monitoring is required.")

    if outlook_status in {"escalation_imminent", "rapid_response"}:
        severity += 5
        scenario = _get_scenario(
            "escalation_playbook",
            "Escalation playbook",
            "Coordinate cross-team escalation handling",
            priority=0,
        )
        _add_trigger(scenario, "Operational outlook is at escalation posture.")
        for driver in outlook.get("drivers", []) or []:
            _add_trigger(scenario, str(driver))
        _set_confidence(scenario, "high")
        _add_scenario_action(
            scenario,
            "Activate executive incident bridge and execute escalation directives.",
        )
        for team in directives.get("coordination_teams", []) or []:
            _add_owner(scenario, str(team))

    directives_status = str(directives.get("status", "")).lower()
    directives_severity = directives.get("severity")
    if directives_status in {"escalate", "accelerate"}:
        severity += 3
        _add_driver("Command directives require accelerated response timelines.")
    if isinstance(directives_severity, (int, float)) and directives_severity >= 12:
        severity += 2
        _add_driver("Command directives severity score is elevated.")

    readiness_level = str(readiness.get("level", "")).lower()
    readiness_window = readiness.get("support_window_hours")
    if isinstance(readiness_window, (int, float)) and readiness_window > 0:
        window_candidates.append(float(readiness_window))
    if readiness_level == "critical":
        severity += 6
        scenario = _get_scenario(
            "rapid_reinforcement",
            "Rapid reinforcement",
            "Restore analyst readiness",
            priority=1,
        )
        _set_confidence(scenario, "high")
        _add_trigger(
            scenario,
            "Response readiness is critical and requires immediate coverage expansion.",
        )
        _add_scenario_action(
            scenario,
            "Mobilise reserve analysts and extend watch rotations to restore readiness.",
        )
        _add_owner(scenario, "Command Liaison")
    elif readiness_level == "strained":
        severity += 3
        scenario = _get_scenario(
            "reinforce_readiness",
            "Reinforce readiness",
            "Stabilise staffing and shift coverage",
            priority=2,
        )
        _add_trigger(scenario, "Response readiness is strained." )
        _add_scenario_action(
            scenario,
            "Coordinate shift swaps and schedule surge analysts for the next watch.",
        )
        _add_owner(scenario, "Operations Planning")

    pressure_status = str(pressure.get("status", "")).lower()
    pressure_severity = pressure.get("severity")
    clearance_window = pressure.get("estimated_clearance_hours")
    if isinstance(clearance_window, (int, float)) and clearance_window > 0:
        window_candidates.append(float(clearance_window))
    if pressure_status == "critical_backlog":
        severity += 5
        scenario = _get_scenario(
            "backlog_clearance",
            "Backlog clearance surge",
            "Clear critical analyst backlog",
            priority=1,
        )
        _add_trigger(
            scenario,
            "Analyst response pressure is in critical backlog status.",
        )
        _set_confidence(scenario, "high")
        _add_scenario_action(
            scenario,
            "Deploy surge staffing to burn down the backlog within the clearance window.",
        )
        _add_owner(scenario, "Analysis Cell")
    elif pressure_status in {"backlog", "prediction_gap", "prediction_gap_watch"}:
        severity += 3
        scenario = _get_scenario(
            "workload_rebalance",
            "Workload rebalance",
            "Stabilise analyst throughput",
            priority=2,
        )
        _add_trigger(
            scenario,
            "Analyst workload pressure indicates backlog or prediction gaps.",
        )
        _add_scenario_action(
            scenario,
            "Shift analysts to prediction triage and expedite model support coordination.",
        )
        _add_owner(scenario, "Analysis Cell")
        if pressure_status == "prediction_gap":
            _set_confidence(scenario, "high")
    if isinstance(pressure_severity, (int, float)) and pressure_severity >= 2:
        severity += 2

    support_status = str(support.get("status", "")).lower()
    if support_status == "mobilise":
        severity += 4
        _add_driver("Support priorities call for immediate cross-team mobilisation.")
    elif support_status == "reinforce":
        severity += 2
        _add_driver("Support priorities emphasise reinforcement actions.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        status = str(feed_info.get("status", "")).lower()
        age = feed_info.get("age_minutes")
        if isinstance(age, (int, float)) and age > 0:
            window_candidates.append(float(age) / 60.0)
        if status == "stale":
            severity += 5
            scenario = _get_scenario(
                f"restore_{feed_name}_feed",
                f"Restore {feed_name} feed",
                "Recover telemetry freshness",
                priority=1,
            )
            detail = f"{feed_name.capitalize()} feed is stale."
            _add_trigger(scenario, detail)
            _add_scenario_action(
                scenario,
                f"Dispatch telemetry engineering to restore the {feed_name} feed immediately.",
            )
            _add_owner(scenario, "Telemetry Operations")
            _set_confidence(scenario, "high")
        elif status == "warning":
            severity += 2
            scenario = _get_scenario(
                f"stabilise_{feed_name}_feed",
                f"Stabilise {feed_name} feed",
                "Prevent telemetry degradation",
                priority=3,
            )
            _add_trigger(
                scenario,
                f"{feed_name.capitalize()} feed freshness is degrading.",
            )
            _add_scenario_action(
                scenario,
                f"Schedule telemetry checks to stabilise the {feed_name} feed.",
            )
            _add_owner(scenario, "Telemetry Operations")

    if isinstance(gaps, list) and gaps:
        critical = 0
        major = 0
        for gap in gaps:
            if not isinstance(gap, dict):
                continue
            severity_label = str(gap.get("severity", "")).lower()
            detail = str(gap.get("detail", ""))
            action = gap.get("recommended_action")
            if severity_label == "critical":
                critical += 1
                severity += 4
                scenario = _get_scenario(
                    "recover_intel_gap",
                    "Recover critical intelligence gap",
                    "Restore degraded intelligence signals",
                    priority=0,
                )
                _add_trigger(scenario, detail or "Critical intelligence gap detected.")
                if action:
                    _add_scenario_action(scenario, str(action))
                _set_confidence(scenario, "high")
            elif severity_label == "major":
                major += 1
                severity += 2
                scenario = _get_scenario(
                    "resolve_major_gap",
                    "Resolve major intelligence gap",
                    "Address outstanding intelligence gaps",
                    priority=2,
                )
                _add_trigger(scenario, detail or "Major intelligence gap detected.")
                if action:
                    _add_scenario_action(scenario, str(action))
        if critical:
            _add_driver(f"{critical} critical intelligence gap(s) remain open.")
        if major:
            _add_driver(f"{major} major intelligence gap(s) identified.")

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)) and weighted_conf < 0.6:
        severity += 2
        _add_watch("Weighted detection confidence below 0.60.")
        scenario = _get_scenario(
            "uplift_detection_confidence",
            "Uplift detection confidence",
            "Improve detection quality and coverage",
            priority=3,
        )
        _add_trigger(
            scenario,
            "Detection confidence is degrading below 0.60.",
        )
        _add_scenario_action(
            scenario,
            "Partner with sensor engineering to recalibrate low-confidence classes.",
        )
        _add_owner(scenario, "Sensor Engineering")

    if isinstance(detection_quality.get("low_confidence_classes"), list):
        low_conf = detection_quality.get("low_confidence_classes")
        if low_conf:
            _add_watch(
                "Low-confidence classes present: "
                + ", ".join(sorted(str(cls) for cls in set(low_conf))),
            )

    risk_level = str(health.get("risk_level", "")).lower()
    if risk_level == "severe":
        severity += 5
        _add_driver("Health assessment indicates severe operational risk.")
    elif risk_level == "high":
        severity += 3
        _add_driver("Health assessment indicates high operational risk.")
    elif risk_level == "elevated":
        severity += 1

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        severity += 4
        _add_driver("Intelligence confidence is low and requires contingency coverage.")
    elif confidence_level == "guarded":
        severity += 2
        _add_driver("Intelligence confidence is guarded; prepare mitigation actions.")

    posture_status = str(posture.get("status", "")).lower()
    if posture_status == "recover":
        severity += 4
    elif posture_status == "stabilise":
        severity += 2

    if comms_plan:
        cadence = comms_plan.get("update_cadence_minutes")
        if isinstance(cadence, (int, float)) and cadence > 0:
            window_candidates.append(float(cadence) / 60.0)
        status = str(comms_plan.get("status", "")).lower()
        if status in {"crisis", "accelerate"}:
            severity += 2
            _add_driver("Communication plan is operating at elevated cadence.")

    coordination_teams = directives.get("coordination_teams") or support.get("teams") or []
    for entry in scenario_map.values():
        if not entry.get("owners"):
            for team in coordination_teams:
                _add_owner(entry, str(team))

    scenarios = sorted(
        scenario_map.values(),
        key=lambda item: (item.get("priority", 99), item.get("name", "")),
    )
    for entry in scenarios:
        entry.pop("priority", None)

    drivers = list(dict.fromkeys(drivers))
    watch_items = list(dict.fromkeys(watch_items))
    actions = list(dict.fromkeys(actions))

    status = "observe"
    if severity >= 20:
        status = "activate"
    elif severity >= 12:
        status = "ready"
    elif severity >= 6:
        status = "prepare"

    activation_window: Optional[float] = None
    positive_windows = [window for window in window_candidates if window and window > 0]
    if positive_windows:
        activation_window = round(min(positive_windows), 2)

    payload: Dict[str, Any] = {
        "status": status,
        "severity": severity,
    }
    if activation_window is not None:
        payload["activation_window_hours"] = activation_window
    if scenarios:
        payload["scenarios"] = scenarios
    if drivers:
        payload["drivers"] = drivers
    if watch_items:
        payload["watch_items"] = watch_items
    if actions:
        payload["recommended_actions"] = actions

    return payload if payload else None


def _derive_resource_sustainment(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Translate posture and support analytics into a resource sustainment plan."""

    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    freshness = brief.get("data_freshness") or {}
    gaps = brief.get("intelligence_gaps") or []
    outlook = brief.get("operational_outlook") or {}
    directives = brief.get("command_directives") or {}
    contingency = brief.get("contingency_plans") or {}
    communication = brief.get("communication_plan") or {}
    health = brief.get("health") or {}
    detection_quality = brief.get("detection_quality") or {}
    meta = brief.get("meta") or {}
    activity = brief.get("activity_summary") or {}

    if not any(
        [
            readiness,
            pressure,
            support,
            freshness,
            gaps,
            outlook,
            directives,
            contingency,
            communication,
            health,
            detection_quality,
            meta,
            activity,
        ]
    ):
        return None

    severity = 0
    drivers: List[str] = []
    actions: List[str] = []
    resource_needs: List[str] = []
    allocation: List[Dict[str, Any]] = []
    window_candidates: List[float] = []

    def _add_driver(message: str) -> None:
        if message:
            drivers.append(message)

    def _add_action(message: str) -> None:
        if message:
            actions.append(message)

    def _add_need(label: str) -> None:
        if label:
            resource_needs.append(label)

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            window_candidates.append(float(value))

    def _register_minutes(minutes: Optional[float]) -> Optional[float]:
        if isinstance(minutes, (float, int)) and minutes > 0:
            hours_value = float(minutes) / 60.0
            window_candidates.append(hours_value)
            return hours_value
        return None

    def _add_allocation(
        resource: str,
        priority: str,
        focus: str,
        *,
        quantity: Optional[float] = None,
        window: Optional[float] = None,
    ) -> None:
        if not resource or not focus:
            return
        entry: Dict[str, Any] = {
            "resource": resource,
            "priority": priority,
            "focus": focus,
        }
        if isinstance(quantity, (float, int)) and quantity > 0:
            entry["quantity"] = int(math.ceil(float(quantity)))
        if isinstance(window, (float, int)) and window > 0:
            entry["window_hours"] = round(float(window), 2)
        allocation.append(entry)

    readiness_level = str(readiness.get("level", "")).lower()
    support_window = readiness.get("support_window_hours")
    _register_window(support_window if isinstance(support_window, (float, int)) else None)
    recommended_staffing = readiness.get("recommended_staffing")
    if readiness_level == "critical":
        severity += 8
        _add_driver("Response readiness is critical and requires immediate staffing.")
        _add_need("Surge analyst coverage")
        _add_action("Mobilise reserve analysts to restore readiness coverage.")
        _add_allocation(
            "Analyst surge team",
            "immediate",
            "Restore readiness coverage",
            quantity=recommended_staffing,
            window=support_window if isinstance(support_window, (float, int)) else None,
        )
    elif readiness_level == "strained":
        severity += 4
        _add_driver("Response readiness is strained and needs reinforcement.")
        _add_need("Staffing reinforcement")
        _add_action("Schedule relief analysts to stabilise strained readiness.")
        _add_allocation(
            "Shift relief analysts",
            "next_shift",
            "Stabilise readiness levels",
            quantity=recommended_staffing,
            window=support_window if isinstance(support_window, (float, int)) else None,
        )
    elif isinstance(recommended_staffing, (float, int)) and recommended_staffing > 4:
        severity += 2
        _add_driver("Elevated staffing recommendations indicate heavier coverage requirements.")
        _add_need("Extended analyst coverage")
        _add_allocation(
            "Analyst coverage",
            "next_shift",
            "Sustain elevated staffing",
            quantity=recommended_staffing,
            window=support_window if isinstance(support_window, (float, int)) else None,
        )

    pressure_status = str(pressure.get("status", "")).lower()
    backlog = pressure.get("pending_predictions")
    unmatched = pressure.get("unmatched_detections")
    clearance = pressure.get("estimated_clearance_hours")
    _register_window(clearance if isinstance(clearance, (float, int)) else None)
    if pressure_status == "critical_backlog":
        severity += 6
        _add_driver("Analyst response pressure is in critical backlog status.")
        _add_need("Backlog triage cell")
        _add_action("Deploy surge analysts to clear the critical prediction backlog.")
        _add_allocation(
            "Backlog triage team",
            "immediate",
            "Clear prediction backlog",
            quantity=backlog,
            window=clearance if isinstance(clearance, (float, int)) else None,
        )
    elif pressure_status in {"backlog", "prediction_gap"}:
        severity += 4
        if pressure_status == "backlog":
            _add_driver("Analyst queue is building as predictions outpace detections.")
            _add_need("Analyst backlog relief")
            _add_action("Schedule additional analysts to work through the prediction backlog.")
            _add_allocation(
                "Prediction triage",
                "next_shift",
                "Work down prediction backlog",
                quantity=backlog,
                window=clearance if isinstance(clearance, (float, int)) else None,
            )
        else:
            _add_driver("Detections are outpacing predictions signalling modelling gaps.")
            _add_need("Model support surge")
            _add_action("Coordinate with modelling teams to regenerate predictions for unmatched detections.")
            _add_allocation(
                "Model operations",
                "immediate",
                "Regenerate predictions for unmatched detections",
                quantity=unmatched,
                window=clearance if isinstance(clearance, (float, int)) else None,
            )
    elif pressure_status in {"prediction_gap_watch", "quality_watch", "feedback_strain"}:
        severity += 2
        _add_driver("Analyst pressure signals quality or prediction coverage strain.")
        _add_need("Analyst quality support")
        _add_action("Pair analysts with engineering partners to stabilise throughput and confidence.")

    support_status = str(support.get("status", "")).lower()
    if support_status == "mobilise":
        severity += 5
        _add_driver("Support priorities call for immediate cross-team mobilisation.")
        _add_need("Cross-team mobilisation")
        _add_action("Coordinate mobilisation tasks across highlighted support teams.")
    elif support_status == "reinforce":
        severity += 3
        _add_driver("Support priorities emphasise reinforcement activities.")
        _add_need("Reinforcement coordination")
        _add_action("Confirm reinforcement tasks are staffed before the next shift.")

    priorities = support.get("priorities") if isinstance(support, dict) else None
    if isinstance(priorities, list):
        for entry in priorities:
            if not isinstance(entry, dict):
                continue
            team = str(entry.get("team", "")).strip()
            reason = str(entry.get("reason", "")).strip() or "Support task"
            urgency = str(entry.get("urgency", "monitor"))
            window = entry.get("support_window_hours")
            _register_window(window if isinstance(window, (float, int)) else None)
            if team:
                _add_need(f"{team} ({urgency})")
            _add_allocation(
                team or "Support team",
                urgency,
                reason,
                window=window if isinstance(window, (float, int)) else None,
            )

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    if isinstance(feeds, dict):
        for feed_name, info in feeds.items():
            if not isinstance(info, dict):
                continue
            status = str(info.get("status", "")).lower()
            age = info.get("age_minutes")
            if status == "stale":
                severity += 3
                _add_driver(f"{feed_name.capitalize()} feed is stale and blocking sustained operations.")
                _add_need(f"{feed_name} telemetry recovery")
                hours_value = _register_minutes(age)
                _add_action(f"Deploy telemetry engineers to restore the {feed_name} feed immediately.")
                _add_allocation(
                    "Telemetry engineering",
                    "immediate",
                    f"Restore {feed_name} feed",
                    window=hours_value,
                )
            elif status == "warning":
                severity += 1
                _add_driver(f"{feed_name.capitalize()} feed freshness is degrading toward stale thresholds.")
                _add_need(f"{feed_name} telemetry checks")
                hours_value = _register_minutes(age)
                _add_action(f"Schedule telemetry checks to stabilise the {feed_name} feed.")
                _add_allocation(
                    "Telemetry engineering",
                    "next_shift",
                    f"Stabilise {feed_name} feed freshness",
                    window=hours_value,
                )

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        gap_name = str(gap.get("gap", "")).strip() or "intelligence gap"
        detail = str(gap.get("detail", "")).strip()
        action = gap.get("recommended_action")
        severity_label = str(gap.get("severity", "")).lower()
        if severity_label == "critical":
            severity += 3
            _add_driver(detail or f"Critical gap detected: {gap_name}.")
            _add_need(f"Resolve {gap_name}")
            _add_action(action or f"Assign an owner to close the {gap_name} gap immediately.")
            _add_allocation(
                "Gap closure team",
                "immediate",
                detail or f"Close {gap_name} gap",
            )
        elif severity_label == "major":
            severity += 2
            _add_driver(detail or f"Major gap requires follow-up: {gap_name}.")
            _add_need(f"Address {gap_name}")
            if action:
                _add_action(action)
            _add_allocation(
                "Gap closure team",
                "next_shift",
                detail or f"Address {gap_name} gap",
            )
        elif action:
            severity += 1
            _add_need(f"Monitor {gap_name}")
            _add_action(action)

    outlook_status = str(outlook.get("status", "")).lower()
    outlook_severity = outlook.get("severity_score")
    horizon = outlook.get("planning_horizon_hours")
    _register_window(horizon if isinstance(horizon, (float, int)) else None)
    if isinstance(outlook_severity, (float, int)):
        if outlook_severity >= 18:
            severity += 4
            _add_driver("Operational outlook severity is approaching escalation thresholds.")
        elif outlook_severity >= 12:
            severity += 3
            _add_driver("Operational outlook signals accelerated planning horizons.")
        elif outlook_severity >= 6:
            severity += 1
            _add_driver("Operational outlook remains focused and needs resourcing oversight.")
    if outlook_status in {"rapid_response", "escalation_imminent"}:
        severity += 4
        _add_need("Rapid response staging")
        _add_action("Stage contingency resources to match the rapid response outlook.")
    elif outlook_status in {"heightened_watch", "stabilisation", "stabilize"}:
        severity += 2
        _add_need("Sustained monitoring resources")

    directive_severity = directives.get("severity")
    planning_window = directives.get("planning_window_hours")
    _register_window(planning_window if isinstance(planning_window, (float, int)) else None)
    if isinstance(directive_severity, (float, int)):
        if directive_severity >= 20:
            severity += 3
            _add_driver("Command directives severity is in the crisis band.")
        elif directive_severity >= 12:
            severity += 2
            _add_driver("Command directives highlight accelerated leadership tasks.")
        elif directive_severity >= 6:
            severity += 1
            _add_driver("Command directives emphasise focused follow-up actions.")

    contingency_status = str(contingency.get("status", "")).lower()
    activation_window = contingency.get("activation_window_hours")
    _register_window(activation_window if isinstance(activation_window, (float, int)) else None)
    if contingency_status == "activate":
        severity += 4
        _add_driver("Contingency scenarios are primed for activation.")
        _add_need("Contingency resource staging")
        _add_action("Pre-position contingency playbook owners and support teams.")
    elif contingency_status == "ready":
        severity += 2
        _add_need("Contingency readiness checks")

    communication_status = str(communication.get("status", "")).lower()
    cadence = communication.get("update_cadence_minutes")
    if isinstance(cadence, (float, int)) and cadence > 0:
        _register_minutes(cadence)
    if communication_status == "escalated":
        severity += 3
        _add_driver("Communication cadence is escalated requiring dedicated comms staffing.")
        _add_need("Communications surge support")
    elif communication_status == "heightened":
        severity += 2
        _add_need("Focused communications coverage")
    elif communication_status == "focused":
        severity += 1

    risk_level = str(health.get("risk_level", "")).lower()
    if risk_level in {"critical", "severe"}:
        severity += 4
        _add_driver("Overall risk level is severe and demands sustained resources.")
        _add_need("Incident management coverage")
    elif risk_level == "high":
        severity += 3
        _add_need("High-risk oversight")
    elif risk_level == "elevated":
        severity += 1

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)):
        if weighted_conf < 0.55:
            severity += 2
            _add_driver("Weighted detection confidence is critically low.")
            _add_need("Sensor calibration resources")
            _add_action("Partner with sensor engineering to uplift low-confidence detections.")
        elif weighted_conf < 0.7:
            severity += 1
            _add_need("Sensor performance monitoring")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)) and feedback_accuracy < 0.6:
        severity += 2
        _add_driver("Feedback accuracy is degraded, increasing rework cycles.")
        _add_need("Feedback calibration support")
        _add_action("Schedule analyst calibration to restore feedback accuracy.")

    tempo = str(activity.get("tempo", "")).lower()
    if tempo == "surge":
        severity += 3
        _add_driver("Operational tempo is surging within the window.")
        _add_need("Surge logistics support")
    elif tempo == "elevated":
        severity += 1
        _add_need("Elevated tempo monitoring")

    resource_needs = list(dict.fromkeys(resource_needs))
    drivers = list(dict.fromkeys(drivers))
    actions = list(dict.fromkeys(actions))

    unique_allocation: List[Dict[str, Any]] = []
    seen_allocations = set()
    for entry in allocation:
        key = (entry.get("resource"), entry.get("priority"), entry.get("focus"))
        if key in seen_allocations:
            continue
        seen_allocations.add(key)
        unique_allocation.append(entry)
    allocation = unique_allocation

    resupply_window: Optional[float] = None
    positive_windows = [window for window in window_candidates if window and window > 0]
    if positive_windows:
        resupply_window = round(min(positive_windows), 2)

    status = "balanced"
    if severity >= 20:
        status = "surge"
    elif severity >= 12:
        status = "accelerate"
    elif severity >= 6:
        status = "reinforce"
    elif severity >= 3:
        status = "watch"

    payload: Dict[str, Any] = {"status": status, "severity": severity}
    if resupply_window is not None:
        payload["resupply_window_hours"] = resupply_window
    if resource_needs:
        payload["resource_needs"] = resource_needs
    if allocation:
        payload["allocation_plan"] = allocation
    if drivers:
        payload["drivers"] = drivers
    if actions:
        payload["recommended_actions"] = actions

    return payload if payload else None


def _derive_communication_plan(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Produce a communications cadence and key messaging plan."""

    directives = brief.get("command_directives") or {}
    outlook = brief.get("operational_outlook") or {}
    posture = brief.get("operational_posture") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    confidence = brief.get("intelligence_confidence") or {}
    health = brief.get("health") or {}
    freshness = brief.get("data_freshness") or {}
    gaps = brief.get("intelligence_gaps") or []
    cluster_threats = brief.get("cluster_threats") or []
    recommendations = brief.get("recommendations") or []
    errors = brief.get("errors") or []

    if not any(
        [
            directives,
            outlook,
            posture,
            readiness,
            pressure,
            support,
            confidence,
            health,
            freshness,
            gaps,
            cluster_threats,
            recommendations,
            errors,
        ]
    ):
        return None

    severity = 0
    drivers: List[str] = []
    key_messages: List[str] = []
    actions: List[str] = []
    audience_map: Dict[str, Dict[str, Any]] = {}

    def _add_driver(message: str) -> None:
        if message:
            drivers.append(message)

    def _add_message(message: str) -> None:
        if message:
            key_messages.append(message)

    def _add_action(message: str) -> None:
        if message:
            actions.append(message)

    def _add_audience(
        name: Optional[str],
        cadence_minutes: Optional[float],
        focus: Optional[str],
        *,
        channel: Optional[str] = None,
    ) -> None:
        if not name or not focus:
            return
        entry = audience_map.setdefault(
            str(name),
            {"audience": str(name), "focus": []},
        )
        focus_list = entry.setdefault("focus", [])
        if focus not in focus_list:
            focus_list.append(focus)
        if isinstance(cadence_minutes, (float, int)) and cadence_minutes > 0:
            cadence_value = max(15, int(round(float(cadence_minutes))))
            existing = entry.get("cadence_minutes")
            if not isinstance(existing, int) or cadence_value < existing:
                entry["cadence_minutes"] = cadence_value
        if channel:
            entry["channel"] = channel

    directive_severity = directives.get("severity")
    if isinstance(directive_severity, (int, float)):
        severity_score = float(directive_severity)
        if severity_score >= 20:
            severity += 5
            _add_driver("Command directives severity is in the crisis band.")
        elif severity_score >= 12:
            severity += 3
            _add_driver("Command directives highlight accelerated leadership actions.")
        elif severity_score >= 6:
            severity += 2
            _add_driver("Command directives emphasise focused follow-up tasks.")
        elif severity_score > 0:
            severity += 1

    directive_status = str(directives.get("status", "")).lower()
    if directive_status in {"escalate", "accelerate"}:
        severity += 3
        _add_driver("Directive posture requires frequent leadership synchronisation.")
    elif directive_status == "focus":
        severity += 1

    for driver in directives.get("drivers", []) or []:
        _add_message(driver)
    for area in directives.get("focus_areas", []) or []:
        _add_message(f"Focus: {area}")

    posture_status = str(posture.get("status", "")).lower()
    if posture_status == "recover":
        severity += 3
        _add_driver("Operational posture is in recovery mode and needs tight comms loops.")
    elif posture_status == "stabilise":
        severity += 2
        _add_driver("Operational posture emphasises stabilisation work across teams.")
    elif posture_status == "reinforce":
        severity += 1

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level == "critical":
        severity += 3
        _add_driver("Response readiness is critical; leadership updates should be rapid.")
    elif readiness_level == "strained":
        severity += 2
        _add_driver("Response readiness is strained and requires reinforcement updates.")

    pressure_severity = pressure.get("severity")
    if isinstance(pressure_severity, (int, float)):
        if int(pressure_severity) >= 2:
            severity += 2
            _add_driver("Analyst response pressure is critical, signalling fast-changing queues.")
        elif int(pressure_severity) >= 1:
            severity += 1
            _add_driver("Analyst response pressure is mounting and should be monitored.")

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "prediction_gap"}:
        _add_message("Analyst backlog requires immediate triage updates.")
    elif pressure_status in {"backlog", "feedback_strain"}:
        _add_message("Analyst workload is trending high; coordinate relief messaging.")

    support_status = str(support.get("status", "")).lower()
    if support_status == "mobilise":
        severity += 2
        _add_driver("Support coordination is mobilising multiple teams.")
    elif support_status == "reinforce":
        severity += 1

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        severity += 2
        _add_driver("Intelligence confidence is low and needs validation messaging.")
        _add_message("Telemetry confidence is degraded; set expectations on data reliability.")
    elif confidence_level == "guarded":
        severity += 1

    risk_level = str(health.get("risk_level", "")).lower()
    if risk_level in {"severe", "critical"}:
        severity += 3
        _add_driver("Health assessment flags severe operational risk.")
    elif risk_level == "high":
        severity += 2
    elif risk_level == "elevated":
        severity += 1

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    stale_feeds: List[str] = []
    warn_feeds: List[str] = []
    for name, info in (feeds or {}).items():
        status = str(info.get("status", "")).lower()
        if status == "stale":
            stale_feeds.append(str(name))
        elif status == "warning":
            warn_feeds.append(str(name))
    if stale_feeds:
        severity += 2
        names = ", ".join(sorted(set(stale_feeds)))
        _add_driver(f"Stale telemetry feeds detected: {names}.")
        _add_message(f"Telemetry recovery required for: {names}.")
    elif warn_feeds:
        severity += 1
        names = ", ".join(sorted(set(warn_feeds)))
        _add_message(f"Telemetry freshness warnings for: {names}.")

    highest_threat_level: Optional[str] = None
    highest_threat_site: Optional[str] = None
    if cluster_threats:
        highest = max(
            [cluster for cluster in cluster_threats if isinstance(cluster, dict)],
            key=lambda cluster: (
                _threat_level_rank(cluster.get("threat_level")),
                cluster.get("threat_score", 0),
            ),
        )
        highest_threat_level = highest.get("threat_level")
        highest_threat_site = highest.get("nearest_site")
        threat_rank = _threat_level_rank(highest_threat_level)
        if threat_rank >= 3:
            severity += 3
            detail = "Critical threat cluster activity demands field alerts."
            if highest_threat_site:
                detail = f"Critical threat cluster converging near {highest_threat_site}."
            _add_driver(detail)
        elif threat_rank == 2:
            severity += 2
            if highest_threat_site:
                _add_driver(f"High-risk cluster tracking toward {highest_threat_site}.")

    critical_gaps = sum(1 for gap in gaps if isinstance(gap, dict) and str(gap.get("severity", "")).lower() == "critical")
    major_gaps = sum(1 for gap in gaps if isinstance(gap, dict) and str(gap.get("severity", "")).lower() == "major")
    if critical_gaps:
        severity += min(3, critical_gaps * 2)
        _add_driver(f"{critical_gaps} critical intelligence gap(s) remain open.")
    elif major_gaps:
        severity += 1

    outlook_status = str(outlook.get("status", "")).lower()
    if outlook_status in {"escalation_imminent", "rapid_response"}:
        severity += 3
    elif outlook_status in {"heightened_watch", "stabilise"}:
        severity += 1

    outlook_focus = outlook.get("focus_areas")
    if isinstance(outlook_focus, list):
        for focus in outlook_focus:
            _add_message(f"Outlook focus: {focus}")

    for rec in recommendations:
        _add_message(str(rec))

    if errors:
        _add_driver("Brief contains system warnings that should be communicated.")
        _add_message("Include telemetry warnings when briefing stakeholders.")

    if highest_threat_level:
        focus_text = "Monitor high-risk cluster routes"
        if highest_threat_site:
            focus_text = f"Monitor movements near {highest_threat_site}"
        _add_audience("Field Liaison", 90 if _threat_level_rank(highest_threat_level) >= 2 else 120, focus_text)

    analyst_focus = "Coordinate analyst relief and backlog updates."
    if pressure_status in {"critical_backlog", "backlog", "prediction_gap"}:
        _add_audience("Intelligence Cell Leads", 60, analyst_focus)

    if support_status in {"mobilise", "reinforce"}:
        _add_audience(
            "Support Coordination",
            90 if support_status == "mobilise" else 120,
            "Synchronise cross-team mobilisation tasks.",
        )

    # Base operations centre audience always present.
    _add_audience(
        "Operations Center",
        60 if severity >= 4 else 180,
        "Maintain situational awareness across posture, readiness, and telemetry.",
    )

    if severity >= 7:
        _add_audience(
            "Command Leadership",
            30 if severity >= 11 else 60,
            "Deliver concise status, directives, and readiness posture updates.",
            channel="Secure briefing",
        )
        _add_action("Publish a leadership situation report summarising directives within the next hour.")
    elif severity >= 4:
        _add_audience(
            "Duty Leadership",
            90,
            "Provide posture, readiness, and key risk updates for the upcoming shift.",
        )
        _add_action("Schedule a duty leadership sync covering posture and readiness drivers.")
    else:
        _add_action("Distribute a routine summary to duty teams during the next scheduled check-in.")

    if stale_feeds:
        _add_action("Include telemetry recovery status in all outbound updates until feeds stabilise.")
    if confidence_level == "low":
        _add_action("Add validation caveats to intelligence products until confidence improves.")
    if critical_gaps:
        _add_action("Track closure owners for critical intelligence gaps in each briefing.")

    base_cadence = 240
    if severity >= 11:
        status = "escalated"
        base_cadence = 30
    elif severity >= 7:
        status = "heightened"
        base_cadence = 60
    elif severity >= 4:
        status = "focused"
        base_cadence = 120
    else:
        status = "routine"

    if readiness_level == "critical" and base_cadence > 45:
        base_cadence = 45
    planning_window = directives.get("planning_window_hours")
    if isinstance(planning_window, (float, int)) and planning_window > 0:
        base_cadence = min(base_cadence, max(30, int(round(float(planning_window) * 60))))

    drivers = list(dict.fromkeys(drivers))
    key_messages = list(dict.fromkeys(key_messages))
    actions = list(dict.fromkeys(actions))

    audiences: List[Dict[str, Any]] = []
    for entry in audience_map.values():
        focus_field = entry.get("focus")
        if isinstance(focus_field, list):
            entry["focus"] = "; ".join(dict.fromkeys(focus_field))
        audiences.append(entry)
    audiences.sort(key=lambda item: item.get("cadence_minutes", 999))

    payload: Dict[str, Any] = {
        "status": status,
        "update_cadence_minutes": int(base_cadence),
    }
    if audiences:
        payload["audiences"] = audiences
    if key_messages:
        payload["key_messages"] = key_messages
    if drivers:
        payload["drivers"] = drivers
    if actions:
        payload["recommended_actions"] = actions

    return payload if payload else None


def _summarise_freshness(
    *,
    generated_at: datetime,
    activity: Dict[str, Any],
    clusters: Iterable[MutableMapping[str, Any]],
    hours: int,
) -> Optional[Dict[str, Any]]:
    """Assess data freshness for key feeds and return actionable insights."""

    feeds: List[Tuple[str, Optional[datetime]]] = [
        ("detections", _latest_timestamp(activity.get("detections", []))),
        ("predictions", _latest_timestamp(activity.get("predictions", []))),
        ("clusters", _latest_timestamp(clusters)),
    ]

    if not any(ts for _, ts in feeds):
        return None

    window_minutes = hours * 60
    warn_threshold = max(45.0, min(window_minutes * 0.5, 180.0))
    stale_threshold = max(90.0, min(window_minutes * 0.75, 360.0))

    summary: Dict[str, Any] = {"feeds": {}}
    max_age: Optional[float] = None
    stalest_feed: Optional[str] = None

    for name, latest in feeds:
        if latest is None:
            summary["feeds"][name] = {"status": "unknown"}
            continue
        minutes_old = (generated_at - latest).total_seconds() / 60.0
        minutes_old = max(0.0, round(minutes_old, 2))
        status = _freshness_status(
            minutes_old=minutes_old,
            warn_threshold=warn_threshold,
            stale_threshold=stale_threshold,
        )
        summary["feeds"][name] = {
            "latest_timestamp": latest.isoformat().replace("+00:00", "Z"),
            "age_minutes": minutes_old,
            "status": status,
        }
        if max_age is None or minutes_old > max_age:
            max_age = minutes_old
            stalest_feed = name

    if max_age is not None:
        summary["worst_case_minutes"] = max_age
    if stalest_feed is not None:
        summary["stalest_feed"] = stalest_feed

    return summary


def _assess_activity(
    activity: Dict[str, Any], *, hours: int, activity_limit: int
) -> Optional[Dict[str, Any]]:
    """Summarise operational tempo and data coverage for the brief."""

    detections = activity.get("detections", []) if activity else []
    predictions = activity.get("predictions", []) if activity else []

    detection_count = len(detections)
    prediction_count = len(predictions)
    if detection_count == 0 and prediction_count == 0:
        return None

    summary: Dict[str, Any] = {
        "detections": detection_count,
        "predictions": prediction_count,
        "detection_rate_per_hour": round(detection_count / float(hours), 2)
        if hours
        else None,
    }

    coverage_ratio: Optional[float] = None
    if detection_count:
        coverage_ratio = prediction_count / detection_count
        summary["prediction_coverage"] = round(coverage_ratio, 2)

    surge_threshold = max(math.ceil(activity_limit * 0.75), 6)
    elevated_threshold = max(math.ceil(activity_limit * 0.4), 3)

    if detection_count >= surge_threshold:
        tempo = "surge"
    elif detection_count >= elevated_threshold:
        tempo = "elevated"
    elif detection_count > 0:
        tempo = "steady"
    else:
        tempo = "quiet"
    summary["tempo"] = tempo

    notes: List[str] = []
    if coverage_ratio is not None:
        if coverage_ratio < 0.5:
            notes.append(
                "Prediction coverage is below 50%; inference jobs may be stalled."
            )
        elif coverage_ratio < 0.75:
            notes.append("Prediction coverage is drifting lower than usual.")

    if tempo == "surge":
        notes.append("Detections are hitting surge levels for the configured window.")
    elif tempo == "elevated":
        notes.append("Detections are elevated compared to the configured limit.")

    if notes:
        summary["notes"] = notes

    return summary


def _threat_level_rank(level: Optional[str]) -> int:
    """Translate textual threat levels to a comparable severity score."""

    mapping = {
        "critical": 3,
        "severe": 3,
        "extreme": 3,
        "high": 2,
        "elevated": 1,
        "medium": 1,
        "moderate": 1,
        "low": 0,
    }
    if level is None:
        return 0
    return mapping.get(level.lower(), 0)


def _risk_level_rank(level: Optional[str]) -> int:
    """Translate health risk levels into numeric severity."""

    mapping = {
        "severe": 4,
        "critical": 4,
        "high": 3,
        "elevated": 2,
        "guarded": 1,
        "low": 1,
        "minimal": 0,
        "stable": 0,
    }
    if level is None:
        return 0
    return mapping.get(level.lower(), 0)


def _derive_brief_health(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Generate a holistic health snapshot for the intelligence brief."""

    activity_summary = brief.get("activity_summary") or {}
    meta = brief.get("meta") or {}
    threats = brief.get("cluster_threats") or []
    freshness = brief.get("data_freshness") or {}

    if not any([activity_summary, meta, threats, freshness]):
        return None

    drivers: List[str] = []
    risk_score = 0
    confidence_score = 3  # 3 = high, 2 = moderate, 1 = low

    tempo = (activity_summary.get("tempo") or "").lower()
    if tempo == "surge":
        risk_score += 2
        drivers.append("Detections are surging against the configured limit.")
    elif tempo == "elevated":
        risk_score += 1
        drivers.append("Detections remain elevated for this window.")

    coverage = activity_summary.get("prediction_coverage")
    if isinstance(coverage, (float, int)) and coverage < 0.5:
        risk_score += 1
        confidence_score = min(confidence_score, 2)
        drivers.append("Prediction coverage is degraded below 50%.")

    threat_level = None
    if threats:
        threat = max(threats, key=lambda c: _threat_level_rank(c.get("threat_level")))
        threat_level = threat.get("threat_level")
        rank = _threat_level_rank(threat_level)
        if rank >= 2:
            risk_score += rank
            drivers.append(
                "Highest cluster threat is flagged as high or above."
            )
        elif rank == 1:
            risk_score += 1
            drivers.append("Cluster threat levels are moderate within the window.")

    feeds = freshness.get("feeds") or {}
    feed_statuses = [str(info.get("status", "unknown")).lower() for info in feeds.values()]
    stale_count = feed_statuses.count("stale")
    warn_count = feed_statuses.count("warning")

    if stale_count:
        risk_score += 2
        confidence_score = 1
        drivers.append("One or more data feeds are stale.")
    elif warn_count:
        risk_score += 1
        confidence_score = min(confidence_score, 2)
        drivers.append("Data freshness is degrading toward stale thresholds.")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)):
        if feedback_accuracy < 0.6:
            confidence_score = 1
            drivers.append("Operator feedback accuracy is critically low.")
        elif feedback_accuracy < 0.75:
            confidence_score = min(confidence_score, 2)
            drivers.append("Feedback accuracy is trending below target levels.")

    confidence_map = {3: "high", 2: "moderate", 1: "low"}
    confidence = confidence_map.get(max(min(confidence_score, 3), 1), "moderate")

    if risk_score >= 5:
        risk_level = "severe"
    elif risk_score >= 3:
        risk_level = "high"
    elif risk_score >= 1:
        risk_level = "elevated"
    else:
        risk_level = "guarded"

    summary_parts = [
        f"Operational risk assessed as {risk_level}.",
        f"Confidence in the brief is {confidence}.",
    ]
    summary = " ".join(summary_parts) if summary_parts else None

    recommended_actions: List[str] = []
    if risk_level in {"severe", "high"}:
        recommended_actions.append(
            "Coordinate immediate response options with the duty officer."
        )
    if confidence == "low":
        recommended_actions.append(
            "Prioritise restoration of telemetry feeds and analyst validation."
        )

    health_payload: Dict[str, Any] = {
        "risk_level": risk_level,
        "confidence": confidence,
        "drivers": drivers,
    }
    if summary:
        health_payload["summary"] = summary.strip()
    if recommended_actions:
        health_payload["recommended_actions"] = recommended_actions
    if threat_level:
        health_payload["highest_threat_level"] = threat_level

    return health_payload


def _derive_operational_posture(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Summarise the recommended operational posture for the duty team."""

    health = brief.get("health") or {}
    activity_summary = brief.get("activity_summary") or {}
    freshness = brief.get("data_freshness") or {}
    threats = brief.get("cluster_threats") or []

    if not any([health, activity_summary, freshness, threats]):
        return None

    risk_level = health.get("risk_level")
    risk_rank = _risk_level_rank(risk_level)

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    stale_feeds: List[str] = []
    warning_feeds: List[str] = []
    for feed_name, info in (feeds or {}).items():
        status = str(info.get("status", "")).lower()
        if status == "stale":
            stale_feeds.append(feed_name)
        elif status == "warning":
            warning_feeds.append(feed_name)

    tempo = str(activity_summary.get("tempo", "")).lower()
    coverage = activity_summary.get("prediction_coverage")

    highest_threat_level: Optional[str] = None
    if threats:
        top_cluster = max(threats, key=lambda c: _threat_level_rank(c.get("threat_level")))
        highest_threat_level = top_cluster.get("threat_level")

    status = "monitor"
    focus = "Maintain situational awareness with routine coverage."
    horizon_hours = 12.0
    drivers: List[str] = []

    if stale_feeds:
        status = "recover"
        focus = "Restore telemetry coverage for stale feeds to regain confidence."
        horizon_hours = 1.0
        drivers.append(f"Stale feeds detected: {', '.join(sorted(stale_feeds))}.")
    elif risk_rank >= 4:
        status = "stabilise"
        focus = "Coordinate immediate response actions with leadership oversight."
        horizon_hours = 2.0
        drivers.append("Risk level is assessed as severe.")
    elif risk_rank == 3:
        status = "stabilise"
        focus = "Escalate to leadership and ready contingency assets."
        horizon_hours = 4.0
        drivers.append("Risk level is high.")
    elif risk_rank == 2:
        status = "reinforce"
        focus = "Reinforce monitoring teams and pre-stage rapid response options."
        horizon_hours = 6.0
        drivers.append("Risk level is elevated.")

    if tempo in {"surge", "elevated"}:
        if status == "monitor":
            status = "reinforce"
            focus = "Sustain elevated watch rotations due to heightened tempo."
            horizon_hours = min(horizon_hours, 6.0)
        drivers.append(f"Operational tempo registered as {tempo}.")

    if isinstance(coverage, (float, int)) and coverage < 0.5:
        drivers.append("Prediction coverage is degraded below 50%.")

    if highest_threat_level and _threat_level_rank(highest_threat_level) >= 2:
        if status == "monitor":
            status = "reinforce"
            focus = "Maintain readiness for high-threat cluster escalation."
            horizon_hours = min(horizon_hours, 4.0)
        drivers.append(f"Highest cluster threat level is {highest_threat_level}.")

    if warning_feeds and status != "recover":
        drivers.append(f"Feeds trending stale: {', '.join(sorted(warning_feeds))}.")
        if status == "monitor":
            focus = "Address telemetry drift while maintaining baseline watch."
            horizon_hours = min(horizon_hours, 8.0)

    drivers = list(dict.fromkeys(drivers))

    posture: Dict[str, Any] = {
        "status": status,
        "focus": focus,
        "horizon_hours": round(horizon_hours, 2),
        "confidence": health.get("confidence", "moderate"),
    }
    if drivers:
        posture["drivers"] = drivers
    if highest_threat_level:
        posture["highest_threat_level"] = highest_threat_level
    if risk_level:
        posture["risk_level"] = risk_level

    return posture


def _derive_response_readiness(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Recommend staffing and readiness actions for operational support teams."""

    health = brief.get("health") or {}
    posture = brief.get("operational_posture") or {}
    freshness = brief.get("data_freshness") or {}
    activity_summary = brief.get("activity_summary") or {}
    meta = brief.get("meta") or {}

    if not any([health, posture, freshness, activity_summary, meta]):
        return None

    drivers: List[str] = []
    actions: List[str] = []

    severity = 0  # 0 steady, 1 strained, 2 critical

    posture_status = str(posture.get("status", "")).lower()
    if posture_status == "recover":
        severity = max(severity, 2)
        drivers.append("Operational posture is set to telemetry recovery.")
    elif posture_status in {"stabilise", "reinforce"}:
        severity = max(severity, 1)
        focus = posture.get("focus")
        if focus:
            drivers.append(f"Posture guidance: {focus}")

    risk_level = health.get("risk_level")
    risk_rank = _risk_level_rank(risk_level)
    if risk_rank >= 4:
        severity = 2
        drivers.append("Health assessment marks risk as severe.")
    elif risk_rank >= 3:
        severity = max(severity, 2)
        drivers.append("Risk level is high requiring rapid coordination.")
    elif risk_rank >= 2:
        severity = max(severity, 1)
        drivers.append("Risk is elevated and needs reinforced coverage.")

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    feed_statuses = [str(info.get("status", "")).lower() for info in (feeds or {}).values()]
    stale_count = feed_statuses.count("stale")
    warn_count = feed_statuses.count("warning")
    if stale_count:
        severity = 2
        drivers.append("One or more telemetry feeds are stale.")
        actions.append("Assign engineers to restore stale telemetry immediately.")
    elif warn_count:
        severity = max(severity, 1)
        drivers.append("Telemetry freshness is degrading toward stale thresholds.")

    tempo = str(activity_summary.get("tempo", "")).lower()
    if tempo == "surge":
        severity = max(severity, 2)
        drivers.append("Operational tempo is surging within the window.")
    elif tempo == "elevated":
        severity = max(severity, 1)
        drivers.append("Operational tempo remains elevated.")

    coverage = activity_summary.get("prediction_coverage")
    if isinstance(coverage, (float, int)) and coverage < 0.5:
        severity = max(severity, 1)
        drivers.append("Prediction coverage is degraded below 50%.")
        actions.append("Review inference pipeline capacity to raise coverage.")

    feedback_accuracy = meta.get("feedback_accuracy")
    if isinstance(feedback_accuracy, (float, int)):
        if feedback_accuracy < 0.6:
            severity = 2
            drivers.append("Feedback accuracy is critically low.")
            actions.append("Schedule immediate analyst feedback calibration.")
        elif feedback_accuracy < 0.75:
            severity = max(severity, 1)
            drivers.append("Feedback accuracy is trending below target levels.")

    cluster_count = meta.get("cluster_count")
    if isinstance(cluster_count, (float, int)):
        if cluster_count >= 25:
            severity = 2
            drivers.append("High volume of active movement clusters detected.")
        elif cluster_count >= 10:
            severity = max(severity, 1)
            drivers.append("Movement cluster load is elevated.")

    severity = max(0, min(severity, 2))
    if severity == 2:
        level = "critical"
        recommended_staffing = 6
        support_window = 2.0
        actions.append("Stage rapid response teams and leadership liaisons.")
    elif severity == 1:
        level = "strained"
        recommended_staffing = 4
        support_window = 4.0
        actions.append("Extend watch rotations and brief standby responders.")
    else:
        level = "steady"
        recommended_staffing = 2
        support_window = 8.0

    posture_horizon = posture.get("horizon_hours")
    if isinstance(posture_horizon, (float, int)) and posture_horizon > 0:
        support_window = min(support_window, float(posture_horizon))

    drivers = list(dict.fromkeys(drivers))
    actions = list(dict.fromkeys(actions))

    readiness: Dict[str, Any] = {
        "level": level,
        "recommended_staffing": recommended_staffing,
        "support_window_hours": round(support_window, 2),
    }
    if drivers:
        readiness["drivers"] = drivers
    if actions:
        readiness["priority_actions"] = actions
    if risk_level:
        readiness["risk_level"] = risk_level
    if tempo:
        readiness["tempo"] = tempo

    return readiness


def _derive_operational_risk_register(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Summarise critical risks surfaced by the fused intelligence analytics."""

    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    freshness = brief.get("data_freshness") or {}
    gaps = brief.get("intelligence_gaps") or []
    confidence = brief.get("intelligence_confidence") or {}
    health = brief.get("health") or {}
    outlook = brief.get("operational_outlook") or {}
    posture = brief.get("operational_posture") or {}
    directives = brief.get("command_directives") or {}
    contingency = brief.get("contingency_plans") or {}
    sustainment = brief.get("resource_sustainment") or {}
    communication = brief.get("communication_plan") or {}
    detection_quality = brief.get("detection_quality") or {}

    if not any(
        [
            readiness,
            pressure,
            support,
            freshness,
            gaps,
            confidence,
            health,
            outlook,
            posture,
            directives,
            contingency,
            sustainment,
            communication,
            detection_quality,
        ]
    ):
        return None

    risks: List[Dict[str, Any]] = []
    actions: List[str] = []
    driver_notes: List[str] = []
    focus_names: List[str] = []
    window_candidates: List[float] = []
    severity_total = 0
    highest_severity = 0

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            window_candidates.append(float(value))

    def _register_minutes(minutes: Optional[float]) -> None:
        if isinstance(minutes, (float, int)) and minutes > 0:
            window_candidates.append(float(minutes) / 60.0)

    def _add_action(message: Optional[str]) -> None:
        if message:
            actions.append(str(message))

    def _add_drivers(values: Iterable[str]) -> None:
        for value in values:
            if value:
                driver_notes.append(str(value))

    def _add_focus(name: str) -> None:
        if name:
            focus_names.append(str(name))

    def _add_risk(
        name: str,
        *,
        category: Optional[str] = None,
        severity: int = 1,
        status: Optional[str] = None,
        detail: Optional[str] = None,
        drivers: Optional[Iterable[str]] = None,
        action: Optional[str] = None,
        window: Optional[float] = None,
    ) -> None:
        nonlocal severity_total, highest_severity
        if not name:
            return
        entry: Dict[str, Any] = {"name": str(name)}
        if category:
            entry["category"] = str(category)
        severity_value = max(0, int(severity))
        if severity_value:
            entry["severity"] = severity_value
            severity_total += severity_value
            highest_severity = max(highest_severity, severity_value)
        if status:
            entry["status"] = str(status)
        if detail:
            entry["detail"] = str(detail)
            driver_notes.append(str(detail))
        if drivers:
            driver_list = [str(item) for item in drivers if item]
            if driver_list:
                entry["drivers"] = driver_list
                _add_drivers(driver_list)
        if action:
            entry["recommended_action"] = str(action)
            _add_action(action)
        if isinstance(window, (float, int)) and window > 0:
            entry["review_window_hours"] = round(float(window), 2)
            window_candidates.append(float(window))
        risks.append(entry)
        _add_focus(str(name))

    readiness_level = str(readiness.get("level", "")).lower()
    support_window = readiness.get("support_window_hours")
    _register_window(support_window if isinstance(support_window, (float, int)) else None)
    readiness_action = None
    if isinstance(readiness.get("priority_actions"), list) and readiness["priority_actions"]:
        readiness_action = str(readiness["priority_actions"][0])
    if readiness_level == "critical":
        _add_risk(
            "Response readiness",
            category="operations",
            severity=5,
            status="critical",
            detail="Readiness level is critical and requires immediate staffing.",
            drivers=readiness.get("drivers", []),
            action=readiness_action,
            window=support_window if isinstance(support_window, (float, int)) else None,
        )
    elif readiness_level == "strained":
        _add_risk(
            "Response readiness",
            category="operations",
            severity=3,
            status="strained",
            detail="Readiness is strained and needs reinforcement planning.",
            drivers=readiness.get("drivers", []),
            action=readiness_action,
            window=support_window if isinstance(support_window, (float, int)) else None,
        )

    pressure_status = str(pressure.get("status", "")).lower()
    clearance = pressure.get("estimated_clearance_hours")
    _register_window(clearance if isinstance(clearance, (float, int)) else None)
    pressure_action = None
    if isinstance(pressure.get("recommended_actions"), list) and pressure["recommended_actions"]:
        pressure_action = str(pressure["recommended_actions"][0])
    if pressure_status == "critical_backlog":
        _add_risk(
            "Analyst response pressure",
            category="workload",
            severity=5,
            status="critical",
            detail="Analyst queue is critically backlogged.",
            drivers=pressure.get("drivers", []),
            action=pressure_action,
            window=clearance if isinstance(clearance, (float, int)) else None,
        )
    elif pressure_status == "prediction_gap":
        _add_risk(
            "Prediction coverage",
            category="modelling",
            severity=4,
            status="gap",
            detail="Detections are outpacing predictions, signalling modelling gaps.",
            drivers=pressure.get("drivers", []),
            action=pressure_action,
            window=clearance if isinstance(clearance, (float, int)) else None,
        )
    elif pressure_status in {"backlog", "prediction_gap_watch", "feedback_strain", "quality_watch"}:
        _add_risk(
            "Analyst response pressure",
            category="workload",
            severity=2,
            status=pressure_status,
            detail="Analyst workload is straining and requires monitoring.",
            drivers=pressure.get("drivers", []),
            action=pressure_action,
            window=clearance if isinstance(clearance, (float, int)) else None,
        )

    confidence_level = str(confidence.get("level", "")).lower()
    confidence_action = None
    if isinstance(confidence.get("recommended_actions"), list) and confidence["recommended_actions"]:
        confidence_action = str(confidence["recommended_actions"][0])
    if confidence_level == "low":
        _add_risk(
            "Intelligence confidence",
            category="telemetry",
            severity=4,
            status="low",
            detail="Telemetry confidence is low and requires validation.",
            drivers=confidence.get("drivers", []),
            action=confidence_action,
        )
    elif confidence_level == "guarded":
        _add_risk(
            "Intelligence confidence",
            category="telemetry",
            severity=2,
            status="guarded",
            detail="Telemetry confidence is guarded and trending downward.",
            drivers=confidence.get("drivers", []),
            action=confidence_action,
        )

    risk_level = str(health.get("risk_level", "")).lower()
    health_action = None
    if isinstance(health.get("recommended_actions"), list) and health["recommended_actions"]:
        health_action = str(health["recommended_actions"][0])
    if risk_level in {"critical", "severe"}:
        _add_risk(
            "Overall risk posture",
            category="leadership",
            severity=5,
            status=risk_level,
            detail="Health assessment reports severe operational risk.",
            drivers=health.get("drivers", []),
            action=health_action,
        )
    elif risk_level == "high":
        _add_risk(
            "Overall risk posture",
            category="leadership",
            severity=4,
            status=risk_level,
            detail="Risk level is high and needs coordinated oversight.",
            drivers=health.get("drivers", []),
            action=health_action,
        )
    elif risk_level == "elevated":
        _add_risk(
            "Overall risk posture",
            category="leadership",
            severity=2,
            status=risk_level,
            detail="Risk posture is elevated and should be reviewed.",
            drivers=health.get("drivers", []),
            action=health_action,
        )

    support_status = str(support.get("status", "")).lower()
    if support_status in {"mobilise", "reinforce", "monitor"}:
        support_severity = 4 if support_status == "mobilise" else (3 if support_status == "reinforce" else 1)
        _add_risk(
            "Support coordination",
            category="coordination",
            severity=support_severity,
            status=support_status,
            detail="Support priorities signal cross-team coordination requirements.",
            drivers=support.get("drivers", []),
            action=(support.get("recommended_actions") or [None])[0]
            if support.get("recommended_actions")
            else None,
        )
    priorities = support.get("priorities") if isinstance(support, dict) else None
    if isinstance(priorities, list):
        for entry in priorities:
            if not isinstance(entry, dict):
                continue
            window = entry.get("support_window_hours")
            _register_window(window if isinstance(window, (float, int)) else None)

    posture_status = str(posture.get("status", "")).lower()
    posture_focus = posture.get("focus")
    posture_window = posture.get("horizon_hours")
    _register_window(posture_window if isinstance(posture_window, (float, int)) else None)
    if posture_status in {"recover", "stabilise", "reinforce"}:
        posture_severity = 4 if posture_status == "recover" else 2
        _add_risk(
            "Operational posture",
            category="operations",
            severity=posture_severity,
            status=posture_status,
            detail="Operational posture requires focused attention.",
            drivers=[posture_focus] if posture_focus else [],
        )

    outlook_status = str(outlook.get("status", "")).lower()
    outlook_severity = outlook.get("severity_score")
    horizon = outlook.get("planning_horizon_hours")
    _register_window(horizon if isinstance(horizon, (float, int)) else None)
    if isinstance(outlook_severity, (float, int)) and outlook_severity > 0:
        scaled = 3 if outlook_severity >= 12 else (2 if outlook_severity >= 6 else 1)
        _add_risk(
            "Operational outlook",
            category="planning",
            severity=scaled,
            status=outlook_status or "focused",
            detail="Operational outlook severity is influencing planning horizons.",
            drivers=outlook.get("focus_areas", []),
            action=(outlook.get("recommended_actions") or [None])[0]
            if outlook.get("recommended_actions")
            else None,
            window=horizon if isinstance(horizon, (float, int)) else None,
        )

    directive_severity = directives.get("severity")
    planning_window = directives.get("planning_window_hours")
    _register_window(planning_window if isinstance(planning_window, (float, int)) else None)
    if isinstance(directive_severity, (float, int)) and directive_severity > 0:
        scaled = 4 if directive_severity >= 18 else (3 if directive_severity >= 12 else 2)
        _add_risk(
            "Command directives",
            category="leadership",
            severity=scaled,
            status=directives.get("status"),
            detail="Command directives volume is escalating.",
            drivers=directives.get("drivers", []),
            action=(directives.get("recommended_actions") or [None])[0]
            if directives.get("recommended_actions")
            else None,
            window=planning_window if isinstance(planning_window, (float, int)) else None,
        )

    sustainment_status = str(sustainment.get("status", "")).lower()
    resupply_window = sustainment.get("resupply_window_hours")
    _register_window(resupply_window if isinstance(resupply_window, (float, int)) else None)
    sustainment_action = None
    if isinstance(sustainment.get("recommended_actions"), list) and sustainment["recommended_actions"]:
        sustainment_action = str(sustainment["recommended_actions"][0])
    if sustainment_status in {"surge", "accelerate"}:
        _add_risk(
            "Resource sustainment",
            category="logistics",
            severity=4 if sustainment_status == "surge" else 3,
            status=sustainment_status,
            detail="Resource sustainment plan requires accelerated execution.",
            drivers=sustainment.get("drivers", []),
            action=sustainment_action,
            window=resupply_window if isinstance(resupply_window, (float, int)) else None,
        )
    elif sustainment_status == "reinforce":
        _add_risk(
            "Resource sustainment",
            category="logistics",
            severity=2,
            status=sustainment_status,
            detail="Resource sustainment recommends reinforcement activities.",
            drivers=sustainment.get("drivers", []),
            action=sustainment_action,
            window=resupply_window if isinstance(resupply_window, (float, int)) else None,
        )

    contingency_status = str(contingency.get("status", "")).lower()
    activation_window = contingency.get("activation_window_hours")
    _register_window(activation_window if isinstance(activation_window, (float, int)) else None)
    contingency_action = None
    if isinstance(contingency.get("recommended_actions"), list) and contingency["recommended_actions"]:
        contingency_action = str(contingency["recommended_actions"][0])
    if contingency_status in {"activate", "ready"}:
        _add_risk(
            "Contingency planning",
            category="planning",
            severity=4 if contingency_status == "activate" else 2,
            status=contingency_status,
            detail="Contingency scenarios are primed for execution.",
            drivers=contingency.get("drivers", []),
            action=contingency_action,
            window=activation_window if isinstance(activation_window, (float, int)) else None,
        )

    communication_status = str(communication.get("status", "")).lower()
    cadence = communication.get("update_cadence_minutes")
    _register_minutes(cadence if isinstance(cadence, (float, int)) else None)
    communication_action = None
    if isinstance(communication.get("recommended_actions"), list) and communication["recommended_actions"]:
        communication_action = str(communication["recommended_actions"][0])
    if communication_status in {"escalated", "heightened", "focused"}:
        severity_map = {"escalated": 3, "heightened": 2, "focused": 1}
        _add_risk(
            "Communications cadence",
            category="engagement",
            severity=severity_map.get(communication_status, 1),
            status=communication_status,
            detail="Communications tempo is increasing and needs coordination.",
            drivers=communication.get("drivers", []),
            action=communication_action,
            window=(float(cadence) / 60.0) if isinstance(cadence, (float, int)) else None,
        )

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, info in (feeds or {}).items():
        if not isinstance(info, dict):
            continue
        status = str(info.get("status", "")).lower()
        age_minutes = info.get("age_minutes")
        _register_minutes(age_minutes if isinstance(age_minutes, (float, int)) else None)
        if status == "stale":
            _add_risk(
                f"{feed_name.capitalize()} freshness",
                category="telemetry",
                severity=4,
                status=status,
                detail=f"{feed_name.capitalize()} feed is stale and blocking situational awareness.",
                action=f"Restore the {feed_name} feed immediately to unblock telemetry.",
                window=(float(age_minutes) / 60.0)
                if isinstance(age_minutes, (float, int)) and age_minutes > 0
                else None,
            )
        elif status == "warning":
            _add_risk(
                f"{feed_name.capitalize()} freshness",
                category="telemetry",
                severity=2,
                status=status,
                detail=f"{feed_name.capitalize()} feed freshness is degrading.",
                action=f"Schedule checks to stabilise the {feed_name} feed before it stalls.",
                window=(float(age_minutes) / 60.0)
                if isinstance(age_minutes, (float, int)) and age_minutes > 0
                else None,
            )

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        gap_name = str(gap.get("gap", "")).strip() or "intelligence gap"
        severity_label = str(gap.get("severity", "")).lower()
        detail = str(gap.get("detail", "")).strip() or None
        action = gap.get("recommended_action")
        if severity_label == "critical":
            _add_risk(
                gap_name,
                category="intelligence",
                severity=4,
                status="critical",
                detail=detail or f"Critical gap detected: {gap_name}.",
                action=action,
            )
        elif severity_label == "major":
            _add_risk(
                gap_name,
                category="intelligence",
                severity=3,
                status="major",
                detail=detail or f"Major gap detected: {gap_name}.",
                action=action,
            )
        elif action:
            _add_risk(
                gap_name,
                category="intelligence",
                severity=1,
                status="minor",
                detail=detail or f"Gap requires monitoring: {gap_name}.",
                action=action,
            )

    weighted_conf = detection_quality.get("weighted_avg_confidence")
    if isinstance(weighted_conf, (float, int)):
        if weighted_conf < 0.55:
            _add_risk(
                "Detection confidence",
                category="telemetry",
                severity=3,
                status="critical",
                detail="Weighted detection confidence is critically low.",
                drivers=detection_quality.get("drivers", []),
                action=(detection_quality.get("recommended_actions") or [None])[0]
                if detection_quality.get("recommended_actions")
                else None,
            )
        elif weighted_conf < 0.65:
            _add_risk(
                "Detection confidence",
                category="telemetry",
                severity=2,
                status="watch",
                detail="Detection confidence is degrading and should be monitored.",
                drivers=detection_quality.get("drivers", []),
                action=(detection_quality.get("recommended_actions") or [None])[0]
                if detection_quality.get("recommended_actions")
                else None,
            )

    if not risks:
        return None

    risks.sort(key=lambda item: (-int(item.get("severity", 0)), item.get("name", "")))
    actions = list(dict.fromkeys(actions))
    driver_notes = list(dict.fromkeys(driver_notes))
    focus_names = list(dict.fromkeys(focus_names))

    status = "stable"
    if highest_severity >= 5 or severity_total >= 18:
        status = "critical"
    elif highest_severity >= 4 or severity_total >= 12:
        status = "escalated"
    elif highest_severity >= 3 or severity_total >= 6:
        status = "elevated"
    elif severity_total > 0:
        status = "watch"

    if status == "critical":
        _add_action("Escalate the operational risk register to command leadership immediately.")
    elif status == "escalated":
        _add_action("Schedule an accelerated risk coordination session within the next shift.")
    elif status == "elevated":
        _add_action("Assign owners to close out the highest severity risks before the next review.")

    actions = list(dict.fromkeys(actions))

    payload: Dict[str, Any] = {
        "status": status,
        "severity_score": severity_total,
        "risk_count": len(risks),
        "risks": risks,
    }
    if driver_notes:
        payload["drivers"] = driver_notes
    if actions:
        payload["recommended_actions"] = actions
    if focus_names:
        payload["focus_areas"] = focus_names
    if window_candidates:
        payload["next_review_hours"] = round(min(window_candidates), 2)

    return payload


def _derive_command_alignment(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evaluate whether leadership, support, and sustainment plans stay aligned."""

    directives = brief.get("command_directives") or {}
    communication = brief.get("communication_plan") or {}
    contingency = brief.get("contingency_plans") or {}
    sustainment = brief.get("resource_sustainment") or {}
    risk_register = brief.get("operational_risks") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    outlook = brief.get("operational_outlook") or {}
    posture = brief.get("operational_posture") or {}
    confidence = brief.get("intelligence_confidence") or {}
    health = brief.get("health") or {}
    gaps = brief.get("intelligence_gaps") or []

    if not any(
        [
            directives,
            communication,
            contingency,
            sustainment,
            risk_register,
            readiness,
            pressure,
            support,
            outlook,
            posture,
            confidence,
            health,
            gaps,
        ]
    ):
        return None

    score = 100.0
    drivers: List[str] = []
    focus: List[str] = []
    gaps_list: List[str] = []
    actions: List[str] = []
    sync_windows: List[float] = []

    def _penalise(amount: float, reason: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = max(0.0, score - float(amount))
        if reason:
            drivers.append(reason)

    def _add_focus(values: Iterable[Any]) -> None:
        for value in values:
            if value:
                focus.append(str(value))

    def _add_gap(message: Optional[str]) -> None:
        if message:
            gaps_list.append(str(message))

    def _add_actions(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                actions.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            sync_windows.append(float(value))

    def _register_minutes(minutes: Optional[float]) -> None:
        if isinstance(minutes, (float, int)) and minutes > 0:
            sync_windows.append(float(minutes) / 60.0)

    directive_severity = directives.get("severity")
    if isinstance(directive_severity, (float, int)):
        if directive_severity >= 18:
            _penalise(25, "Command directives severity is signalling crisis coordination.")
        elif directive_severity >= 12:
            _penalise(18, "Command directives require accelerated leadership focus.")
        elif directive_severity >= 6:
            _penalise(10, "Command directives emphasise focused follow-up work.")
    directive_status = str(directives.get("status", "")).lower()
    if directive_status == "escalate":
        _penalise(15, "Directive status is escalate and requires tight alignment.")
        _add_gap("Leadership directives are in escalation and need synchronised support.")
    elif directive_status == "accelerate":
        _penalise(8, "Directive status is accelerate and needs rapid execution support.")
    elif directive_status == "focus":
        _penalise(4, "Directive status is focus and should be monitored for alignment drift.")
    _add_actions(directives.get("recommended_actions"))
    _add_focus(directives.get("focus_areas", []))
    _register_window(directives.get("planning_window_hours"))
    for team in directives.get("coordination_teams", []) or []:
        if team:
            focus.append(f"Team: {team}")

    comm_status = str(communication.get("status", "")).lower()
    if comm_status == "escalated":
        _penalise(12, "Communication cadence is escalated and taxing coordination loops.")
        _add_gap("Communication plan is escalated; ensure messaging owners stay aligned.")
    elif comm_status == "heightened":
        _penalise(7, "Communication cadence is heightened and requires deliberate syncs.")
    elif comm_status == "focused":
        _penalise(3, "Communication cadence is focused and should stay on script.")
    _add_actions(communication.get("recommended_actions"))
    _add_focus(
        [entry.get("focus") for entry in communication.get("audiences", []) if isinstance(entry, dict)]
    )
    _register_minutes(communication.get("update_cadence_minutes"))

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status == "surge":
        _penalise(12, "Resource sustainment is surging and at risk of misalignment.")
        _add_gap("Sustainment plan requires surge resourcing and command confirmation.")
    elif sustainment_status == "accelerate":
        _penalise(8, "Resource sustainment needs accelerated support to stay aligned.")
    elif sustainment_status == "reinforce":
        _penalise(5, "Resource sustainment recommends reinforcement across teams.")
    elif sustainment_status == "watch":
        _penalise(2)
    _add_actions(sustainment.get("recommended_actions"))
    _add_focus(sustainment.get("resource_needs", []))
    _register_window(sustainment.get("resupply_window_hours"))

    risk_score = risk_register.get("severity_score")
    if isinstance(risk_score, (float, int)):
        if risk_score >= 18:
            _penalise(20, "Operational risk register is critical and dominating planning.")
            _add_gap("Operational risk register contains critical items needing ownership.")
        elif risk_score >= 12:
            _penalise(15, "Operational risk register is escalated and requires follow-through.")
        elif risk_score >= 6:
            _penalise(8, "Operational risk register is elevated and should inform alignment.")
    risk_status = str(risk_register.get("status", "")).lower()
    if risk_status == "critical":
        _add_gap("Critical risks require leadership and support teams to stay locked in.")
    _add_actions(risk_register.get("recommended_actions"))
    _add_focus(risk_register.get("focus_areas", []))
    _add_focus([
        entry.get("name")
        for entry in risk_register.get("risks", [])
        if isinstance(entry, dict) and entry.get("severity", 0) >= 4
    ])
    _register_window(risk_register.get("next_review_hours"))

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level == "critical":
        _penalise(20, "Response readiness is critical and alignment is under strain.")
        _add_gap("Readiness is critical; ensure staffing and directives align.")
    elif readiness_level == "strained":
        _penalise(12, "Response readiness is strained and needs reinforcement alignment.")
    elif readiness_level == "steady":
        _penalise(2)
    _add_actions(readiness.get("priority_actions"))
    _register_window(readiness.get("support_window_hours"))

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "prediction_gap"}:
        _penalise(16, "Analyst pressure is severe and desynchronising execution.")
        _add_gap("Analyst pressure is critical; align staffing and modelling owners.")
    elif pressure_status in {"backlog", "feedback_strain", "quality_watch"}:
        _penalise(9, "Analyst pressure is building and needs coordination.")
    elif pressure_status in {"prediction_gap_watch"}:
        _penalise(5)
    _add_actions(pressure.get("recommended_actions"))
    _register_window(pressure.get("estimated_clearance_hours"))

    support_status = str(support.get("status", "")).lower()
    if support_status == "mobilise":
        _penalise(10, "Support teams are mobilising and must stay synchronised.")
        _add_gap("Support mobilisation requires alignment with directives and sustainment.")
    elif support_status == "reinforce":
        _penalise(6, "Support teams are reinforcing existing plans.")
    elif support_status == "monitor":
        _penalise(2)
    _add_actions(support.get("recommended_actions"))
    _add_focus(
        [
            entry.get("reason")
            for entry in support.get("priorities", [])
            if isinstance(entry, dict) and entry.get("reason")
        ]
    )
    _add_focus(
        [
            entry.get("team")
            for entry in support.get("priorities", [])
            if isinstance(entry, dict) and entry.get("team")
        ]
    )

    outlook_severity = outlook.get("severity_score")
    if isinstance(outlook_severity, (float, int)):
        if outlook_severity >= 12:
            _penalise(10, "Operational outlook is severe and guiding near-term focus.")
        elif outlook_severity >= 6:
            _penalise(6, "Operational outlook is elevated and shaping coordination.")
    _add_actions(outlook.get("recommended_actions"))
    _add_focus(outlook.get("focus_areas", []))
    _register_window(outlook.get("planning_horizon_hours"))

    posture_status = str(posture.get("status", "")).lower()
    if posture_status == "recover":
        _penalise(8, "Operational posture is in recovery and alignment risk is high.")
    elif posture_status == "stabilise":
        _penalise(5, "Operational posture emphasises stabilisation across teams.")
    elif posture_status == "reinforce":
        _penalise(3)
    posture_focus = posture.get("focus")
    if posture_focus:
        focus.append(str(posture_focus))
    _register_window(posture.get("horizon_hours"))

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(12, "Intelligence confidence is low and eroding alignment trust.")
        _add_gap("Low intelligence confidence requires validation owners and clear comms.")
    elif confidence_level == "guarded":
        _penalise(6, "Intelligence confidence is guarded and should be reinforced.")
    _add_actions(confidence.get("recommended_actions"))

    risk_level = str(health.get("risk_level", "")).lower()
    if risk_level in {"critical", "severe"}:
        _penalise(14, "Overall risk posture is severe and alignment must be command-led.")
        _add_gap("Operational risk posture is severe and needs coordinated mitigation.")
    elif risk_level == "high":
        _penalise(10, "Operational risk posture is high and requires structured follow-up.")
    elif risk_level == "elevated":
        _penalise(5)
    _add_actions(health.get("recommended_actions"))
    _add_focus(health.get("drivers", []))

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity = str(gap.get("severity", "")).lower()
        detail = str(gap.get("detail", "")).strip() or gap.get("gap")
        if severity == "critical":
            _penalise(12)
            _add_gap(f"Critical intelligence gap: {detail}.")
        elif severity == "major":
            _penalise(7)
            _add_gap(f"Major intelligence gap: {detail}.")
        elif severity:
            _penalise(3)

    for entry in contingency.get("scenarios", []) if isinstance(contingency, dict) else []:
        if isinstance(entry, dict) and entry.get("name"):
            focus.append(str(entry["name"]))
    contingency_status = str(contingency.get("status", "")).lower()
    if contingency_status == "activate":
        _penalise(10, "Contingency plans are primed for activation and need orchestration.")
        _add_gap("Contingency activation requires aligned ownership across teams.")
    elif contingency_status == "ready":
        _penalise(6, "Contingency plans are ready and need rehearsal alignment.")
    elif contingency_status == "watch":
        _penalise(2)
    _add_actions(contingency.get("recommended_actions"))
    _register_window(contingency.get("activation_window_hours"))

    positive_sync = [value for value in sync_windows if value and value > 0]
    next_sync: Optional[float] = None
    if positive_sync:
        next_sync = round(min(positive_sync), 2)

    drivers = list(dict.fromkeys(drivers))
    focus = list(dict.fromkeys([item for item in focus if item]))
    gaps_list = list(dict.fromkeys(gaps_list))
    actions = list(dict.fromkeys(actions))

    alignment_score = int(round(score))
    if alignment_score >= 80:
        status = "aligned"
    elif alignment_score >= 60:
        status = "watch"
    elif alignment_score >= 40:
        status = "at_risk"
    else:
        status = "misaligned"

    payload: Dict[str, Any] = {
        "status": status,
        "alignment_score": alignment_score,
    }
    if drivers:
        payload["drivers"] = drivers
    if focus:
        payload["focus_areas"] = focus
    if gaps_list:
        payload["coordination_gaps"] = gaps_list
    if actions:
        payload["recommended_actions"] = actions
    if next_sync is not None:
        payload["next_sync_hours"] = next_sync

    return payload if payload else None


def _derive_mission_assurance(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fuse operational telemetry into a mission assurance scoreboard."""

    readiness = brief.get("response_readiness") or {}
    alignment = brief.get("command_alignment") or {}
    sustainment = brief.get("resource_sustainment") or {}
    risk_register = brief.get("operational_risks") or {}
    contingency = brief.get("contingency_plans") or {}
    communication = brief.get("communication_plan") or {}
    directives = brief.get("command_directives") or {}
    outlook = brief.get("operational_outlook") or {}
    posture = brief.get("operational_posture") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    confidence = brief.get("intelligence_confidence") or {}
    health = brief.get("health") or {}
    gaps = brief.get("intelligence_gaps") or []
    freshness = brief.get("data_freshness") or {}

    if not any(
        [
            readiness,
            alignment,
            sustainment,
            risk_register,
            contingency,
            communication,
            directives,
            outlook,
            posture,
            pressure,
            support,
            confidence,
            health,
            gaps,
            freshness,
        ]
    ):
        return None

    score = 100.0
    drivers: List[str] = []
    focus: List[str] = []
    blockers: List[str] = []
    actions: List[str] = []
    dependencies: List[Dict[str, Any]] = []
    checkpoint_windows: List[float] = []

    def _penalise(amount: float, reason: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = max(0.0, score - float(amount))
        if reason:
            drivers.append(reason)

    def _add_actions(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                actions.append(str(value))

    def _add_focus(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                focus.append(str(value))

    def _add_blocker(message: Optional[str]) -> None:
        if message:
            blockers.append(str(message))

    def _add_drivers(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                drivers.append(str(value))

    def _register_dependency(name: str, hours: Optional[float]) -> None:
        if not isinstance(hours, (float, int)) or hours <= 0:
            return
        window = round(float(hours), 2)
        dependencies.append({"name": name, "window_hours": window})
        checkpoint_windows.append(window)

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level == "critical":
        _penalise(25, "Response readiness is critical and jeopardises mission assurance.")
        _add_blocker("Response readiness is critical; surge coverage is required.")
    elif readiness_level == "strained":
        _penalise(16, "Response readiness is strained and needs reinforcement.")
    elif readiness_level == "steady":
        _penalise(4)
    _add_actions(readiness.get("priority_actions"))
    _add_drivers(readiness.get("drivers"))
    _register_dependency("Readiness support window", readiness.get("support_window_hours"))

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status == "misaligned":
        _penalise(22, "Command alignment is misaligned across teams.")
        _add_blocker("Command directives, comms, and sustainment are misaligned.")
    elif alignment_status == "at_risk":
        _penalise(14, "Command alignment is at risk and needs coordination.")
    elif alignment_status == "watch":
        _penalise(8)
    _add_drivers(alignment.get("drivers"))
    _add_focus(alignment.get("focus_areas"))
    for gap in alignment.get("coordination_gaps", []) or []:
        _add_blocker(f"Alignment gap: {gap}")
    _add_actions(alignment.get("recommended_actions"))
    _register_dependency("Next alignment sync", alignment.get("next_sync_hours"))

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status == "surge":
        _penalise(15, "Resource sustainment is in surge mode.")
        _add_blocker("Sustainment plan requires surge resources to stay afloat.")
    elif sustainment_status == "accelerate":
        _penalise(10, "Resource sustainment needs acceleration.")
    elif sustainment_status == "reinforce":
        _penalise(6)
    elif sustainment_status == "watch":
        _penalise(3)
    _add_focus(sustainment.get("resource_needs"))
    _add_actions(sustainment.get("recommended_actions"))
    _register_dependency("Resupply window", sustainment.get("resupply_window_hours"))

    risk_score = risk_register.get("severity_score")
    if isinstance(risk_score, (float, int)):
        if risk_score >= 18:
            _penalise(18, "Operational risk register is critical.")
            _add_blocker("Operational risk register contains critical items.")
        elif risk_score >= 12:
            _penalise(12, "Operational risk register is escalated.")
        elif risk_score >= 6:
            _penalise(7)
    _add_focus(risk_register.get("focus_areas"))
    _add_actions(risk_register.get("recommended_actions"))
    _register_dependency("Risk review", risk_register.get("next_review_hours"))

    contingency_status = str(contingency.get("status", "")).lower()
    if contingency_status == "activate":
        _penalise(12, "Contingency plans are primed for activation.")
        _add_blocker("Contingency playbooks are standing by for activation.")
    elif contingency_status == "ready":
        _penalise(7)
    elif contingency_status == "watch":
        _penalise(3)
    _add_focus([entry.get("name") for entry in contingency.get("scenarios", []) if isinstance(entry, dict)])
    _add_actions(contingency.get("recommended_actions"))
    _register_dependency("Contingency activation", contingency.get("activation_window_hours"))
    _add_drivers(contingency.get("drivers"))

    comm_status = str(communication.get("status", "")).lower()
    if comm_status == "escalated":
        _penalise(10, "Communication cadence is escalated.")
    elif comm_status == "heightened":
        _penalise(6)
    elif comm_status == "focused":
        _penalise(3)
    _add_actions(communication.get("recommended_actions"))
    _add_focus(
        [
            entry.get("focus")
            for entry in communication.get("audiences", [])
            if isinstance(entry, dict) and entry.get("focus")
        ]
    )
    cadence = communication.get("update_cadence_minutes")
    if isinstance(cadence, (float, int)) and cadence > 0:
        hours = float(cadence) / 60.0
        _register_dependency("Comms cadence", hours)

    directive_status = str(directives.get("status", "")).lower()
    if directive_status == "escalate":
        _penalise(14, "Command directives are in escalation.")
    elif directive_status == "accelerate":
        _penalise(9)
    elif directive_status == "focus":
        _penalise(5)
    directive_severity = directives.get("severity")
    if isinstance(directive_severity, (float, int)) and directive_severity >= 18:
        _penalise(6)
    _add_focus(directives.get("focus_areas"))
    _add_actions(directives.get("recommended_actions"))
    _register_dependency("Directive planning window", directives.get("planning_window_hours"))
    _add_focus(directives.get("coordination_teams"))

    outlook_severity = outlook.get("severity_score")
    if isinstance(outlook_severity, (float, int)):
        if outlook_severity >= 12:
            _penalise(10, "Operational outlook is severe.")
        elif outlook_severity >= 6:
            _penalise(6)
    _add_focus(outlook.get("focus_areas"))
    _add_actions(outlook.get("recommended_actions"))
    _register_dependency("Outlook horizon", outlook.get("planning_horizon_hours"))
    _add_drivers(outlook.get("drivers"))

    posture_status = str(posture.get("status", "")).lower()
    if posture_status == "recover":
        _penalise(9, "Operational posture is in recovery mode.")
    elif posture_status == "stabilise":
        _penalise(6)
    elif posture_status == "reinforce":
        _penalise(4)
    focus_field = posture.get("focus")
    if focus_field:
        focus.append(str(focus_field))
    _register_dependency("Posture horizon", posture.get("horizon_hours"))

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "prediction_gap"}:
        _penalise(14, "Analyst pressure is severe.")
        _add_blocker("Analyst response pressure is severe and needs relief.")
    elif pressure_status in {"backlog", "feedback_strain", "quality_watch"}:
        _penalise(9)
    elif pressure_status in {"prediction_gap_watch"}:
        _penalise(5)
    _add_actions(pressure.get("recommended_actions"))
    _register_dependency("Pressure clearance", pressure.get("estimated_clearance_hours"))
    _add_drivers(pressure.get("drivers"))

    support_status = str(support.get("status", "")).lower()
    if support_status == "mobilise":
        _penalise(9, "Support priorities are mobilising.")
    elif support_status == "reinforce":
        _penalise(6)
    elif support_status == "monitor":
        _penalise(3)
    _add_actions(support.get("recommended_actions"))
    _add_focus(
        [
            entry.get("team")
            for entry in support.get("priorities", [])
            if isinstance(entry, dict) and entry.get("team")
        ]
    )
    _add_focus(
        [
            entry.get("reason")
            for entry in support.get("priorities", [])
            if isinstance(entry, dict) and entry.get("reason")
        ]
    )
    _register_dependency(
        "Support window",
        min(
            (
                float(entry.get("support_window_hours"))
                for entry in support.get("priorities", [])
                if isinstance(entry, dict)
                and isinstance(entry.get("support_window_hours"), (float, int))
                and float(entry["support_window_hours"]) > 0
            ),
            default=None,
        ),
    )

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(12, "Intelligence confidence is low.")
        _add_blocker("Low intelligence confidence is undermining assurance.")
    elif confidence_level == "guarded":
        _penalise(7)
    _add_actions(confidence.get("recommended_actions"))
    _add_drivers(confidence.get("drivers"))

    risk_level = str(health.get("risk_level", "")).lower()
    if risk_level in {"critical", "severe"}:
        _penalise(12, "Health risk posture is severe.")
        _add_blocker("Health risk posture is severe and requires leadership focus.")
    elif risk_level == "high":
        _penalise(9)
    elif risk_level == "elevated":
        _penalise(5)
    _add_actions(health.get("recommended_actions"))
    _add_drivers(health.get("drivers"))

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        message_prefix = f"{str(feed_name).capitalize()} feed"
        if status == "stale":
            _penalise(10, f"{message_prefix} is stale.")
            _add_blocker(f"{message_prefix} is stale and blocking decision confidence.")
        elif status == "warning":
            _penalise(6, f"{message_prefix} is drifting toward stale thresholds.")

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity = str(gap.get("severity", "")).lower()
        detail = str(gap.get("detail", "")).strip() or gap.get("gap")
        if severity == "critical":
            _penalise(12)
            _add_blocker(f"Critical intelligence gap: {detail}.")
        elif severity == "major":
            _penalise(8)
            _add_blocker(f"Major intelligence gap: {detail}.")
        elif severity:
            _penalise(4)

    drivers = list(dict.fromkeys(drivers))
    focus = list(dict.fromkeys([item for item in focus if item]))
    blockers = list(dict.fromkeys(blockers))
    actions = list(dict.fromkeys(actions))
    deduped_dependencies: List[Dict[str, Any]] = []
    seen_dependencies: set[Tuple[Any, Any]] = set()
    for dep in dependencies:
        name = dep.get("name") if isinstance(dep, dict) else None
        window = dep.get("window_hours") if isinstance(dep, dict) else None
        key = (name, window)
        if key in seen_dependencies:
            continue
        seen_dependencies.add(key)
        deduped_dependencies.append(dep)
    dependencies = deduped_dependencies

    assurance_score = int(round(score))
    if assurance_score >= 85:
        status = "assured"
    elif assurance_score >= 70:
        status = "watch"
    elif assurance_score >= 55:
        status = "at_risk"
    else:
        status = "critical"

    if blockers and status == "assured":
        status = "watch"
    if any("critical" in blocker.lower() for blocker in blockers) and status != "critical":
        status = "at_risk" if assurance_score >= 55 else "critical"

    payload: Dict[str, Any] = {
        "status": status,
        "assurance_score": assurance_score,
    }
    if drivers:
        payload["drivers"] = drivers
    if focus:
        payload["focus_areas"] = focus
    if blockers:
        payload["blockers"] = blockers
    if actions:
        payload["recommended_actions"] = actions
    if dependencies:
        payload["dependency_windows"] = dependencies
    if checkpoint_windows:
        payload["next_checkpoint_hours"] = round(min(checkpoint_windows), 2)

    return payload


def _derive_operational_resilience(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Blend mission telemetry into an operational resilience pulse."""

    assurance = brief.get("mission_assurance") or {}
    readiness = brief.get("response_readiness") or {}
    sustainment = brief.get("resource_sustainment") or {}
    risk_register = brief.get("operational_risks") or {}
    contingency = brief.get("contingency_plans") or {}
    communication = brief.get("communication_plan") or {}
    alignment = brief.get("command_alignment") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    freshness = brief.get("data_freshness") or {}
    confidence = brief.get("intelligence_confidence") or {}
    gaps = brief.get("intelligence_gaps") or []
    outlook = brief.get("operational_outlook") or {}

    if not any(
        [
            assurance,
            readiness,
            sustainment,
            risk_register,
            contingency,
            communication,
            alignment,
            pressure,
            support,
            freshness,
            confidence,
            gaps,
            outlook,
        ]
    ):
        return None

    score = 100.0
    reinforcing: List[str] = []
    weak_spots: List[str] = []
    actions: List[str] = []
    drivers: List[str] = []
    windows: List[float] = []

    def _penalise(amount: float, reason: Optional[str] = None) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = max(0.0, score - float(amount))
        if reason:
            weak_spots.append(reason)

    def _reinforce(message: Optional[str]) -> None:
        if message:
            reinforcing.append(str(message))

    def _add_actions(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                actions.append(str(value))

    def _add_drivers(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                drivers.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if not isinstance(value, (float, int)) or value <= 0:
            return
        windows.append(round(float(value), 2))

    def _flag_gap(message: Optional[str]) -> None:
        if message:
            weak_spots.append(str(message))

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status == "critical":
        _penalise(22, "Mission assurance is critical and eroding resilience.")
    elif assurance_status == "at_risk":
        _penalise(14, "Mission assurance is at risk across key domains.")
    elif assurance_status == "watch":
        _penalise(7, "Mission assurance requires close monitoring.")
    elif assurance_status == "assured":
        _reinforce("Mission assurance remains steady.")
    _add_actions(assurance.get("recommended_actions"))
    _add_drivers(assurance.get("drivers"))
    _add_drivers(assurance.get("focus_areas"))
    _register_window(assurance.get("next_checkpoint_hours"))

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level == "critical":
        _penalise(18, "Response readiness is critical and stretching resilience.")
    elif readiness_level == "strained":
        _penalise(12, "Response readiness is strained and needs reinforcement.")
    elif readiness_level == "steady":
        _reinforce("Response readiness is steady across shifts.")
    _add_actions(readiness.get("priority_actions"))
    _add_drivers(readiness.get("drivers"))
    _register_window(readiness.get("support_window_hours"))

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status == "surge":
        _penalise(12, "Resource sustainment is in surge mode.")
    elif sustainment_status == "accelerate":
        _penalise(8, "Resource sustainment needs acceleration to keep pace.")
    elif sustainment_status == "reinforce":
        _penalise(5, "Resource sustainment requires reinforcement.")
    elif sustainment_status == "monitor":
        _reinforce("Resource sustainment is stable.")
    _add_actions(sustainment.get("recommended_actions"))
    _add_drivers(sustainment.get("resource_needs"))
    _register_window(sustainment.get("resupply_window_hours"))

    risk_score = risk_register.get("severity_score")
    if isinstance(risk_score, (float, int)):
        if risk_score >= 18:
            _penalise(16, "Operational risk register is critical.")
        elif risk_score >= 12:
            _penalise(11, "Operational risk register is elevated.")
        elif risk_score >= 6:
            _penalise(6, "Operational risk register is trending upward.")
        elif risk_score <= 3:
            _reinforce("Operational risks remain contained.")
    _add_actions(risk_register.get("recommended_actions"))
    _add_drivers(risk_register.get("focus_areas"))
    _register_window(risk_register.get("next_review_hours"))

    contingency_status = str(contingency.get("status", "")).lower()
    if contingency_status == "activate":
        _penalise(9, "Contingency plans are on the brink of activation.")
    elif contingency_status == "ready":
        _penalise(6, "Contingency plans are ready and draining resilience.")
    elif contingency_status == "watch":
        _reinforce("Contingency plans are in watch posture.")
    _add_actions(contingency.get("recommended_actions"))
    _add_drivers(entry.get("name") for entry in contingency.get("scenarios", []) if isinstance(entry, dict))
    _register_window(contingency.get("activation_window_hours"))

    communication_status = str(communication.get("status", "")).lower()
    if communication_status in {"escalated", "crisis"}:
        _penalise(9, "Communication cadence is escalated to crisis mode.")
    elif communication_status == "reinforce":
        _penalise(5, "Communication cadence is in reinforce mode.")
    elif communication_status in {"steady", "routine"}:
        _reinforce("Communication cadence remains steady.")
    _add_actions(communication.get("recommended_actions"))
    _add_drivers(communication.get("key_messages"))
    audiences = communication.get("audiences")
    if isinstance(audiences, list):
        _add_drivers(entry.get("focus") for entry in audiences if isinstance(entry, dict))

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status == "misaligned":
        _penalise(14, "Command alignment is misaligned and reducing resilience.")
    elif alignment_status == "at_risk":
        _penalise(9, "Command alignment is at risk.")
    elif alignment_status == "watch":
        _penalise(5, "Command alignment needs attention.")
    elif alignment_status == "aligned":
        _reinforce("Command alignment is holding together.")
    _add_actions(alignment.get("recommended_actions"))
    _add_drivers(alignment.get("drivers"))
    _add_drivers(alignment.get("focus_areas"))
    _register_window(alignment.get("next_sync_hours"))
    for gap in alignment.get("coordination_gaps", []) or []:
        _flag_gap(f"Alignment gap: {gap}")

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "prediction_gap"}:
        _penalise(13, "Analyst pressure is critical.")
    elif pressure_status in {"backlog", "feedback_strain", "quality_watch"}:
        _penalise(8, "Analyst pressure is building.")
    elif pressure_status == "balanced":
        _reinforce("Analyst throughput is balanced.")
    _add_actions(pressure.get("recommended_actions"))
    _register_window(pressure.get("estimated_clearance_hours"))

    support_status = str(support.get("status", "")).lower()
    if support_status == "mobilise":
        _penalise(9, "Support teams are mobilising and straining resilience.")
    elif support_status == "reinforce":
        _penalise(6, "Support teams are reinforcing active plans.")
    elif support_status == "monitor":
        _reinforce("Support teams are monitoring without additional load.")
    _add_actions(support.get("recommended_actions"))
    _add_drivers(
        entry.get("team")
        for entry in support.get("priorities", [])
        if isinstance(entry, dict)
    )
    _register_window(
        min(
            (
                float(entry.get("support_window_hours"))
                for entry in support.get("priorities", [])
                if isinstance(entry, dict)
                and isinstance(entry.get("support_window_hours"), (float, int))
                and float(entry["support_window_hours"]) > 0
            ),
            default=None,
        )
    )

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        label = f"{str(feed_name).capitalize()} feed"
        if status == "stale":
            _penalise(10, f"{label} is stale and undermining resilience.")
        elif status == "warning":
            _penalise(6, f"{label} is drifting toward stale thresholds.")

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(11, "Intelligence confidence is low.")
    elif confidence_level == "guarded":
        _penalise(6, "Intelligence confidence is guarded.")
    elif confidence_level == "high":
        _reinforce("Intelligence confidence remains high.")
    _add_actions(confidence.get("recommended_actions"))
    _add_drivers(confidence.get("drivers"))

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity = str(gap.get("severity", "")).lower()
        detail = str(gap.get("detail", "")).strip() or gap.get("gap")
        if severity == "critical":
            _penalise(12, f"Critical intelligence gap: {detail}.")
        elif severity == "major":
            _penalise(8, f"Major intelligence gap: {detail}.")
        elif severity:
            _penalise(4, f"Intelligence gap: {detail}.")

    outlook_status = str(outlook.get("status", "")).lower()
    if outlook_status == "escalation_imminent":
        _penalise(12, "Operational outlook indicates escalation is imminent.")
    elif outlook_status == "rapid_response":
        _penalise(8, "Operational outlook is driving rapid response planning.")
    elif outlook_status == "heightened_watch":
        _penalise(5, "Operational outlook remains on heightened watch.")
    elif outlook_status in {"stabilise", "steady_watch"}:
        _reinforce("Operational outlook is steady.")
    _add_actions(outlook.get("recommended_actions"))
    _add_drivers(outlook.get("drivers"))
    _register_window(outlook.get("planning_horizon_hours"))

    reinforcing = list(dict.fromkeys(reinforcing))
    weak_spots = list(dict.fromkeys([item for item in weak_spots if item]))
    actions = list(dict.fromkeys(actions))
    drivers = list(dict.fromkeys([item for item in drivers if item]))
    windows = [value for value in windows if isinstance(value, (float, int)) and value > 0]

    resilience_score = int(round(score))
    if resilience_score >= 82:
        status = "resilient"
    elif resilience_score >= 66:
        status = "steady"
    elif resilience_score >= 48:
        status = "vulnerable"
    else:
        status = "critical"

    payload: Dict[str, Any] = {
        "status": status,
        "resilience_score": resilience_score,
    }
    if reinforcing:
        payload["reinforcing_factors"] = reinforcing
    if weak_spots:
        payload["weak_spots"] = weak_spots
    if actions:
        payload["recommended_actions"] = actions
    if drivers:
        payload["drivers"] = drivers
    if windows:
        payload["stability_window_hours"] = min(windows)

    return payload


def _derive_operational_continuity(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Synthesize continuity posture from mission, resilience, and support telemetry."""

    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    sustainment = brief.get("resource_sustainment") or {}
    risk_register = brief.get("operational_risks") or {}
    contingency = brief.get("contingency_plans") or {}
    communication = brief.get("communication_plan") or {}
    directives = brief.get("command_directives") or {}
    alignment = brief.get("command_alignment") or {}
    support = brief.get("support_priorities") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    confidence = brief.get("intelligence_confidence") or {}
    freshness = brief.get("data_freshness") or {}
    outlook = brief.get("operational_outlook") or {}

    if not any(
        [
            assurance,
            resilience,
            sustainment,
            risk_register,
            contingency,
            communication,
            directives,
            alignment,
            support,
            readiness,
            pressure,
            confidence,
            freshness,
            outlook,
        ]
    ):
        return None

    score = 100.0
    constraints: List[str] = []
    stability: List[str] = []
    actions: List[str] = []
    drivers: List[str] = []
    risks: List[Dict[str, Any]] = []
    horizons: List[float] = []
    watch_items: List[str] = []

    def _penalise(
        amount: float,
        *,
        name: Optional[str] = None,
        severity: Optional[str] = None,
        detail: Optional[str] = None,
        constraint: Optional[str] = None,
    ) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = max(0.0, score - float(amount))
        if constraint:
            constraints.append(str(constraint))
        risk: Dict[str, Any] = {}
        if name:
            risk["name"] = str(name)
        if severity:
            risk["severity"] = str(severity)
        if detail:
            risk["detail"] = str(detail)
        if risk:
            risks.append(risk)

    def _record_constraint(message: Optional[str]) -> None:
        if message:
            constraints.append(str(message))

    def _reward(message: Optional[str]) -> None:
        if message:
            stability.append(str(message))

    def _collect_actions(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                actions.append(str(value))

    def _collect_drivers(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                drivers.append(str(value))

    def _register_horizon(value: Optional[float]) -> None:
        if not isinstance(value, (float, int)) or value <= 0:
            return
        horizons.append(round(float(value), 2))

    def _collect_watch(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if value:
                watch_items.append(str(value))

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status == "critical":
        _penalise(
            24,
            name="Mission assurance",
            severity="critical",
            detail="Mission assurance is critical",
            constraint="Mission assurance blockers threaten continuity.",
        )
    elif assurance_status == "at_risk":
        _penalise(
            16,
            name="Mission assurance",
            severity="major",
            detail="Mission assurance is at risk",
            constraint="Mission assurance requires shoring up dependencies.",
        )
    elif assurance_status == "watch":
        _penalise(
            8,
            name="Mission assurance",
            severity="moderate",
            detail="Mission assurance under watch",
        )
    elif assurance_status == "assured":
        _reward("Mission assurance baseline is steady.")
    _collect_actions(assurance.get("recommended_actions"))
    _collect_drivers(assurance.get("drivers"))
    _collect_drivers(assurance.get("focus_areas"))
    _register_horizon(assurance.get("next_checkpoint_hours"))
    _collect_watch(assurance.get("blockers"))

    resilience_status = str(resilience.get("status", "")).lower()
    if resilience_status == "critical":
        _penalise(
            20,
            name="Operational resilience",
            severity="critical",
            detail="Resilience posture is critical",
            constraint="Resilience weak spots limit extended operations.",
        )
    elif resilience_status == "vulnerable":
        _penalise(
            14,
            name="Operational resilience",
            severity="major",
            detail="Resilience posture is vulnerable",
        )
    elif resilience_status == "steady":
        _reward("Operational resilience remains steady.")
    elif resilience_status == "resilient":
        _reward("Operational resilience is reinforcing continuity.")
    _collect_actions(resilience.get("recommended_actions"))
    _collect_drivers(resilience.get("drivers"))
    _collect_watch(resilience.get("weak_spots"))
    _collect_watch(resilience.get("reinforcing_factors"))
    _register_horizon(resilience.get("stability_window_hours"))

    sustain_status = str(sustainment.get("status", "")).lower()
    if sustain_status == "surge":
        _penalise(
            12,
            name="Resource sustainment",
            severity="major",
            detail="Sustainment is in surge mode",
            constraint="Sustainment surge is draining reserves.",
        )
    elif sustain_status == "accelerate":
        _penalise(
            8,
            name="Resource sustainment",
            severity="moderate",
            detail="Sustainment requires acceleration",
        )
    elif sustain_status == "reinforce":
        _penalise(5, name="Resource sustainment", severity="moderate", detail="Sustainment requires reinforcement")
    elif sustain_status == "monitor":
        _reward("Sustainment posture is holding steady.")
    _collect_actions(sustainment.get("recommended_actions"))
    _collect_drivers(sustainment.get("resource_needs"))
    _collect_watch(sustainment.get("resource_needs"))
    _register_horizon(sustainment.get("resupply_window_hours"))

    risk_score = risk_register.get("severity_score")
    if isinstance(risk_score, (float, int)):
        if risk_score >= 18:
            _penalise(
                14,
                name="Operational risk register",
                severity="critical",
                detail="Risk register contains critical threats",
            )
        elif risk_score >= 12:
            _penalise(
                10,
                name="Operational risk register",
                severity="major",
                detail="Risk register is elevated",
            )
        elif risk_score >= 6:
            _penalise(
                6,
                name="Operational risk register",
                severity="moderate",
                detail="Risk register trending upward",
            )
        elif risk_score <= 3:
            _reward("Operational risk register remains contained.")
    _collect_actions(risk_register.get("recommended_actions"))
    _collect_drivers(risk_register.get("focus_areas"))
    _register_horizon(risk_register.get("next_review_hours"))

    contingency_status = str(contingency.get("status", "")).lower()
    if contingency_status == "activate":
        _penalise(
            10,
            name="Contingency planning",
            severity="major",
            detail="Contingency plans near activation",
            constraint="Contingency teams are on standby and draining capacity.",
        )
    elif contingency_status == "ready":
        _penalise(
            7,
            name="Contingency planning",
            severity="moderate",
            detail="Contingency plans ready to launch",
        )
    elif contingency_status == "watch":
        _reward("Contingency planning remains on watch.")
    _collect_actions(contingency.get("recommended_actions"))
    _collect_drivers(
        entry.get("name")
        for entry in contingency.get("scenarios", [])
        if isinstance(entry, dict) and entry.get("name")
    )
    _collect_watch(contingency.get("watch_items"))
    _register_horizon(contingency.get("activation_window_hours"))

    communication_status = str(communication.get("status", "")).lower()
    if communication_status in {"crisis", "escalated"}:
        _penalise(
            8,
            name="Communication cadence",
            severity="major",
            detail="Communication cadence escalated",
        )
    elif communication_status in {"reinforce", "heightened"}:
        _penalise(
            5,
            name="Communication cadence",
            severity="moderate",
            detail="Communication cadence heightened",
        )
    elif communication_status in {"steady", "routine", "focused"}:
        _reward("Communication cadence is supporting continuity.")
    _collect_actions(communication.get("recommended_actions"))
    _collect_drivers(communication.get("key_messages"))
    audiences = communication.get("audiences")
    if isinstance(audiences, list):
        _collect_drivers(
            entry.get("focus") for entry in audiences if isinstance(entry, dict) and entry.get("focus")
        )
    cadence = communication.get("update_cadence_minutes")
    if isinstance(cadence, (float, int)) and cadence > 0:
        _register_horizon(float(cadence) / 60.0)

    directive_status = str(directives.get("status", "")).lower()
    if directive_status == "escalate":
        _penalise(
            9,
            name="Command directives",
            severity="major",
            detail="Command directives escalated",
            constraint="Directive escalation requires rapid coordination.",
        )
    elif directive_status == "accelerate":
        _penalise(
            6,
            name="Command directives",
            severity="moderate",
            detail="Command directives accelerating",
        )
    elif directive_status == "focus":
        _penalise(
            4,
            name="Command directives",
            severity="moderate",
            detail="Command directives focused",
        )
    elif directive_status == "monitor":
        _reward("Command directives remain on monitor posture.")
    directive_severity = directives.get("severity")
    if isinstance(directive_severity, (float, int)) and directive_severity >= 18:
        _penalise(
            6,
            name="Command directives",
            severity="critical",
            detail="Directive severity flagged as high",
        )
    _collect_actions(directives.get("recommended_actions"))
    _collect_drivers(directives.get("focus_areas"))
    _collect_drivers(directives.get("coordination_teams"))
    _register_horizon(directives.get("planning_window_hours"))

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status == "misaligned":
        _penalise(
            12,
            name="Command alignment",
            severity="major",
            detail="Command alignment misaligned",
            constraint="Alignment gaps require immediate coordination.",
        )
    elif alignment_status == "at_risk":
        _penalise(
            8,
            name="Command alignment",
            severity="moderate",
            detail="Command alignment at risk",
        )
    elif alignment_status == "watch":
        _penalise(
            5,
            name="Command alignment",
            severity="moderate",
            detail="Command alignment under watch",
        )
    elif alignment_status == "aligned":
        _reward("Command alignment is supporting continuity.")
    _collect_actions(alignment.get("recommended_actions"))
    _collect_drivers(alignment.get("drivers"))
    _collect_drivers(alignment.get("focus_areas"))
    _register_horizon(alignment.get("next_sync_hours"))
    _collect_watch(alignment.get("coordination_gaps"))

    support_status = str(support.get("status", "")).lower()
    if support_status == "mobilise":
        _penalise(
            8,
            name="Support priorities",
            severity="major",
            detail="Support teams mobilising",
        )
    elif support_status == "reinforce":
        _penalise(
            6,
            name="Support priorities",
            severity="moderate",
            detail="Support teams reinforcing",
        )
    elif support_status == "monitor":
        _reward("Support priorities remain in monitor posture.")
    _collect_actions(support.get("recommended_actions"))
    for entry in support.get("priorities", []) if isinstance(support.get("priorities"), list) else []:
        if not isinstance(entry, dict):
            continue
        reason = entry.get("reason")
        team = entry.get("team")
        if reason:
            _record_constraint(str(reason))
        if team:
            _collect_drivers([team])
        window = entry.get("support_window_hours")
        _register_horizon(window if isinstance(window, (float, int)) else None)

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level == "critical":
        _penalise(
            12,
            name="Response readiness",
            severity="critical",
            detail="Response readiness critical",
            constraint="Critical readiness level limits sustained ops.",
        )
    elif readiness_level == "strained":
        _penalise(
            8,
            name="Response readiness",
            severity="major",
            detail="Response readiness strained",
        )
    elif readiness_level == "steady":
        _reward("Response readiness providing stable coverage.")
    elif readiness_level == "reinforced":  # defensive: allow optional future value
        _reward("Response readiness reinforced for extended ops.")
    _collect_actions(readiness.get("priority_actions"))
    _collect_drivers(readiness.get("drivers"))
    _register_horizon(readiness.get("support_window_hours"))

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "prediction_gap"}:
        _penalise(
            10,
            name="Response pressure",
            severity="major",
            detail="Analyst response pressure critical",
            constraint="Analyst backlog threatens continuity horizon.",
        )
    elif pressure_status in {"backlog", "feedback_strain", "quality_watch"}:
        _penalise(
            6,
            name="Response pressure",
            severity="moderate",
            detail="Analyst response pressure elevated",
        )
    elif pressure_status == "balanced":
        _reward("Analyst pressure balanced for sustained throughput.")
    _collect_actions(pressure.get("recommended_actions"))
    _collect_drivers(pressure.get("drivers"))
    _register_horizon(pressure.get("estimated_clearance_hours"))

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(
            9,
            name="Intelligence confidence",
            severity="major",
            detail="Intelligence confidence low",
            constraint="Low intelligence confidence slows decision cadence.",
        )
    elif confidence_level == "guarded":
        _penalise(
            6,
            name="Intelligence confidence",
            severity="moderate",
            detail="Intelligence confidence guarded",
        )
    elif confidence_level == "high":
        _reward("Intelligence confidence supports continuity decisions.")
    _collect_actions(confidence.get("recommended_actions"))
    _collect_drivers(confidence.get("drivers"))

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        label = f"{str(feed_name).capitalize()} feed"
        if status == "stale":
            _penalise(
                9,
                name=f"{label} freshness",
                severity="major",
                detail=f"{label} is stale",
                constraint=f"{label} requires recovery to sustain ops.",
            )
        elif status == "warning":
            _penalise(
                5,
                name=f"{label} freshness",
                severity="moderate",
                detail=f"{label} nearing stale threshold",
            )

    outlook_status = str(outlook.get("status", "")).lower()
    if outlook_status == "escalation_imminent":
        _penalise(
            8,
            name="Operational outlook",
            severity="critical",
            detail="Operational outlook predicts escalation",
        )
    elif outlook_status == "rapid_response":
        _penalise(
            6,
            name="Operational outlook",
            severity="major",
            detail="Operational outlook driving rapid response",
        )
    elif outlook_status in {"heightened_watch"}:
        _penalise(
            4,
            name="Operational outlook",
            severity="moderate",
            detail="Operational outlook on heightened watch",
        )
    elif outlook_status in {"stabilise", "steady_watch"}:
        _reward("Operational outlook steady for continuity planning.")
    _collect_actions(outlook.get("recommended_actions"))
    _collect_drivers(outlook.get("drivers"))
    _collect_drivers(outlook.get("focus_areas"))
    _register_horizon(outlook.get("planning_horizon_hours"))

    constraints = list(dict.fromkeys(filter(None, constraints)))
    stability = list(dict.fromkeys(filter(None, stability)))
    actions = list(dict.fromkeys(filter(None, actions)))
    drivers = list(dict.fromkeys(filter(None, drivers)))
    watch_items = list(dict.fromkeys(filter(None, watch_items)))

    deduped_risks: List[Dict[str, Any]] = []
    seen_risks: set[Tuple[Any, Any, Any]] = set()
    for entry in risks:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        severity = entry.get("severity")
        detail = entry.get("detail")
        key = (name, severity, detail)
        if key in seen_risks:
            continue
        seen_risks.add(key)
        deduped_risks.append({k: v for k, v in entry.items() if v})
    risks = deduped_risks

    horizons = [value for value in horizons if isinstance(value, (float, int)) and value > 0]

    continuity_score = int(round(score))
    if continuity_score >= 82:
        status = "sustained"
    elif continuity_score >= 68:
        status = "watch"
    elif continuity_score >= 52:
        status = "strained"
    else:
        status = "critical"

    if any(str(risk.get("severity", "")).lower() == "critical" for risk in risks):
        status = "critical"
    elif status == "watch":
        major_risks = sum(1 for risk in risks if str(risk.get("severity", "")).lower() in {"major", "critical"})
        if major_risks >= 2:
            status = "strained"

    payload: Dict[str, Any] = {"status": status, "continuity_score": continuity_score}
    if constraints:
        payload["primary_constraints"] = constraints
    if stability:
        payload["stability_factors"] = stability
    if actions:
        payload["recommended_actions"] = actions
    if drivers:
        payload["drivers"] = drivers
    if risks:
        payload["continuity_risks"] = risks
    if watch_items:
        payload["watch_items"] = watch_items
    if horizons:
        payload["continuity_horizon_hours"] = min(horizons)

    return payload


def _derive_escalation_matrix(brief: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Fuse mission telemetry into an escalation readiness matrix for leadership."""

    directives = brief.get("command_directives") or {}
    continuity = brief.get("operational_continuity") or {}
    resilience = brief.get("operational_resilience") or {}
    assurance = brief.get("mission_assurance") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    contingency = brief.get("contingency_plans") or {}
    communication = brief.get("communication_plan") or {}
    sustainment = brief.get("resource_sustainment") or {}
    risk_register = brief.get("operational_risks") or {}
    gaps = brief.get("intelligence_gaps") or []
    freshness = brief.get("data_freshness") or {}
    confidence = brief.get("intelligence_confidence") or {}
    outlook = brief.get("operational_outlook") or {}
    alignment = brief.get("command_alignment") or {}

    if not any(
        [
            directives,
            continuity,
            resilience,
            assurance,
            readiness,
            pressure,
            support,
            contingency,
            communication,
            sustainment,
            risk_register,
            gaps,
            freshness,
            confidence,
            outlook,
            alignment,
        ]
    ):
        return None

    score = 100.0
    signals: List[str] = []
    stability: List[str] = []
    drivers: List[str] = []
    actions: List[str] = []
    watch_items: List[str] = []
    review_windows: List[float] = []
    pathway_index: Dict[Tuple[str, str], Dict[str, Any]] = {}

    priority_order = {
        "immediate": 0,
        "prepare": 1,
        "next_shift": 2,
        "monitor": 3,
        "standby": 4,
    }

    def _normalise_priority(value: Any) -> str:
        key = str(value or "").lower()
        mapping = {
            "escalate": "immediate",
            "accelerate": "immediate",
            "focus": "prepare",
            "reinforce": "prepare",
            "watch": "monitor",
            "observe": "monitor",
            "standby": "standby",
        }
        if key in priority_order:
            return key
        return mapping.get(key, "monitor")

    def _add_pathway(
        name: Optional[str],
        priority: Any,
        *,
        trigger: Optional[str] = None,
        action: Optional[str] = None,
    ) -> None:
        label = str(name or "").strip()
        if not label:
            return
        normalised = _normalise_priority(priority)
        key = (label, normalised)
        entry = pathway_index.setdefault(key, {"name": label, "priority": normalised})
        if trigger:
            triggers = entry.setdefault("triggers", [])
            if trigger not in triggers:
                triggers.append(trigger)
        if action:
            actions_list = entry.setdefault("actions", [])
            if action not in actions_list:
                actions_list.append(action)

    def _penalise(
        amount: float,
        message: Optional[str] = None,
        *,
        source: Optional[str] = None,
        priority: Any = None,
        trigger: Optional[str] = None,
        action: Optional[str] = None,
    ) -> None:
        nonlocal score
        if amount > 0:
            score = max(0.0, score - float(amount))
        text = str(message or "").strip()
        if text:
            signals.append(text)
        if source or trigger or action:
            _add_pathway(source or "Escalation", priority or "monitor", trigger=trigger or text, action=action)

    def _reinforce(message: Optional[str]) -> None:
        if message:
            stability.append(str(message))

    def _collect_actions(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if not value:
                continue
            text = str(value)
            if text not in actions:
                actions.append(text)

    def _collect_drivers(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if not value:
                continue
            text = str(value)
            if text not in drivers:
                drivers.append(text)

    def _collect_watch(values: Optional[Iterable[Any]]) -> None:
        for value in values or []:
            if not value:
                continue
            text = str(value)
            if text not in watch_items:
                watch_items.append(text)

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            review_windows.append(round(float(value), 2))

    directive_severity = directives.get("severity")
    if isinstance(directive_severity, (int, float)):
        if directive_severity >= 20:
            _penalise(
                22,
                "Command directives require immediate leadership escalation.",
                source="Command directives",
                priority="immediate",
                trigger="Directive severity critical",
            )
        elif directive_severity >= 12:
            _penalise(
                15,
                "Command directives highlight accelerated escalation tracks.",
                source="Command directives",
                priority="prepare",
                trigger="Directive severity elevated",
            )
        elif directive_severity >= 6:
            _penalise(
                8,
                "Command directives recommend near-term escalation planning.",
                source="Command directives",
                priority="next_shift",
                trigger="Directive severity raised",
            )
        else:
            _reinforce("Command directives remain within routine thresholds.")
    _register_window(directives.get("planning_window_hours"))
    _collect_drivers(directives.get("drivers"))
    _collect_actions(
        entry.get("action")
        for entry in directives.get("directives", [])
        if isinstance(entry, dict)
    )
    for entry in directives.get("directives", []) if isinstance(directives.get("directives"), list) else []:
        if not isinstance(entry, dict):
            continue
        priority = entry.get("priority")
        trigger = entry.get("context") or entry.get("source")
        _add_pathway("Command directives", priority, trigger=trigger, action=entry.get("action"))

    continuity_status = str(continuity.get("status", "")).lower()
    if continuity_status == "critical":
        _penalise(
            24,
            "Operational continuity is critical and requires escalated oversight.",
            source="Operational continuity",
            priority="immediate",
            trigger="Continuity status critical",
        )
    elif continuity_status == "strained":
        _penalise(
            16,
            "Operational continuity is strained across key dependencies.",
            source="Operational continuity",
            priority="prepare",
            trigger="Continuity status strained",
        )
    elif continuity_status == "watch":
        _penalise(
            9,
            "Operational continuity is under watch and may escalate if constraints persist.",
            source="Operational continuity",
            priority="next_shift",
            trigger="Continuity status watch",
        )
    elif continuity_status == "sustained":
        _reinforce("Operational continuity is sustained with manageable constraints.")
    _collect_drivers(continuity.get("drivers"))
    _collect_watch(continuity.get("primary_constraints"))
    _collect_watch(continuity.get("watch_items"))
    _register_window(continuity.get("continuity_horizon_hours"))
    _collect_actions(continuity.get("recommended_actions"))

    resilience_status = str(resilience.get("status", "")).lower()
    if resilience_status == "critical":
        _penalise(
            18,
            "Operational resilience is critical and limits escalation capacity.",
            source="Operational resilience",
            priority="immediate",
        )
    elif resilience_status == "vulnerable":
        _penalise(
            12,
            "Operational resilience is vulnerable and requires reinforcement before escalation.",
            source="Operational resilience",
            priority="prepare",
        )
    elif resilience_status == "steady":
        _reinforce("Operational resilience is steady and can absorb escalations.")
    elif resilience_status == "resilient":
        _reinforce("Operational resilience is strong across key dimensions.")
    _collect_drivers(resilience.get("drivers"))
    _collect_actions(resilience.get("recommended_actions"))
    _register_window(resilience.get("stability_window_hours"))

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status == "critical":
        _penalise(
            16,
            "Mission assurance is critical and blocks escalation pathways.",
            source="Mission assurance",
            priority="immediate",
            trigger="Mission assurance blockers",
        )
    elif assurance_status == "at_risk":
        _penalise(
            10,
            "Mission assurance is at risk and constrains escalation.",
            source="Mission assurance",
            priority="prepare",
        )
    elif assurance_status == "watch":
        _penalise(
            6,
            "Mission assurance is in watch posture for dependencies.",
            source="Mission assurance",
            priority="next_shift",
        )
    elif assurance_status == "assured":
        _reinforce("Mission assurance remains stable for escalation planning.")
    _collect_watch(assurance.get("blockers"))
    _collect_drivers(assurance.get("focus_areas"))
    _collect_actions(assurance.get("recommended_actions"))
    _register_window(assurance.get("next_checkpoint_hours"))

    readiness_level = str(readiness.get("level", "")).lower()
    if readiness_level == "critical":
        _penalise(
            18,
            "Response readiness is critical and needs emergency escalation support.",
            source="Response readiness",
            priority="immediate",
            trigger="Readiness level critical",
            action=(readiness.get("priority_actions") or [None])[0],
        )
    elif readiness_level == "strained":
        _penalise(
            12,
            "Response readiness is strained and requires reinforcement before escalation.",
            source="Response readiness",
            priority="prepare",
            trigger="Readiness level strained",
        )
    elif readiness_level == "steady":
        _reinforce("Response readiness is steady across shifts.")
    _collect_actions(readiness.get("priority_actions"))
    _collect_drivers(readiness.get("drivers"))
    _register_window(readiness.get("support_window_hours"))

    pressure_status = str(pressure.get("status", "")).lower()
    if pressure_status in {"critical_backlog", "prediction_gap"}:
        _penalise(
            16,
            "Analyst pressure is critical and will force escalation.",
            source="Response pressure",
            priority="immediate",
            trigger=f"Pressure status: {pressure_status}",
        )
    elif pressure_status in {"backlog", "feedback_strain", "quality_watch", "prediction_gap_watch"}:
        _penalise(
            9,
            "Analyst pressure indicates pending escalation triggers.",
            source="Response pressure",
            priority="prepare",
            trigger=f"Pressure status: {pressure_status}",
        )
    elif pressure_status == "balanced":
        _reinforce("Analyst pressure is balanced for escalation support.")
    _collect_actions(pressure.get("recommended_actions"))
    _register_window(pressure.get("estimated_clearance_hours"))

    support_status = str(support.get("status", "")).lower()
    if support_status == "mobilise":
        _penalise(
            12,
            "Support teams are mobilising to cover escalation pathways.",
            source="Support priorities",
            priority="immediate",
        )
    elif support_status == "reinforce":
        _penalise(
            8,
            "Support teams are reinforcing operations ahead of escalation.",
            source="Support priorities",
            priority="prepare",
        )
    elif support_status == "monitor":
        _reinforce("Support teams remain on monitor posture.")
    _collect_actions(support.get("recommended_actions"))
    for entry in support.get("priorities", []) if isinstance(support.get("priorities"), list) else []:
        if not isinstance(entry, dict):
            continue
        reason = str(entry.get("reason", "")).strip()
        if reason:
            _collect_watch([reason])
        _register_window(entry.get("support_window_hours"))

    contingency_status = str(contingency.get("status", "")).lower()
    if contingency_status == "activate":
        _penalise(
            14,
            "Contingency plans are primed for activation.",
            source="Contingency planning",
            priority="immediate",
        )
    elif contingency_status == "ready":
        _penalise(
            10,
            "Contingency plans are ready and require leadership awareness.",
            source="Contingency planning",
            priority="prepare",
        )
    elif contingency_status == "watch":
        _penalise(
            6,
            "Contingency plans are on watch status.",
            source="Contingency planning",
            priority="next_shift",
        )
    else:
        _reinforce("Contingency planning remains in observe posture.")
    _collect_watch(contingency.get("watch_items"))
    _collect_actions(contingency.get("recommended_actions"))
    _register_window(contingency.get("activation_window_hours"))

    comm_status = str(communication.get("status", "")).lower()
    if comm_status in {"escalated", "crisis"}:
        _penalise(
            12,
            "Communication cadence is escalated for crisis messaging.",
            source="Communication plan",
            priority="immediate",
        )
    elif comm_status in {"reinforce", "accelerate"}:
        _penalise(
            8,
            "Communication cadence is accelerating to support escalation.",
            source="Communication plan",
            priority="prepare",
        )
    elif comm_status in {"steady", "routine"}:
        _reinforce("Communication cadence remains steady for escalation messaging.")
    _collect_actions(communication.get("recommended_actions"))
    _collect_drivers(communication.get("key_messages"))

    sustainment_status = str(sustainment.get("status", "")).lower()
    if sustainment_status in {"surge", "accelerate"}:
        _penalise(
            10,
            "Resource sustainment is in surge to cover escalation demand.",
            source="Resource sustainment",
            priority="immediate",
        )
    elif sustainment_status in {"reinforce", "stabilise"}:
        _penalise(
            6,
            "Resource sustainment is reinforcing for future escalation.",
            source="Resource sustainment",
            priority="prepare",
        )
    elif sustainment_status == "monitor":
        _reinforce("Resource sustainment remains on monitor posture.")
    _collect_actions(sustainment.get("recommended_actions"))
    _register_window(sustainment.get("resupply_window_hours"))
    _collect_drivers(
        entry.get("team")
        for entry in sustainment.get("allocation_plan", [])
        if isinstance(entry, dict)
    )

    risk_score = risk_register.get("severity_score")
    if isinstance(risk_score, (int, float)):
        if risk_score >= 18:
            _penalise(
                14,
                "Operational risk register is severe and drives escalation governance.",
                source="Operational risks",
                priority="immediate",
            )
        elif risk_score >= 12:
            _penalise(
                9,
                "Operational risk register remains elevated.",
                source="Operational risks",
                priority="prepare",
            )
        elif risk_score >= 6:
            _penalise(
                5,
                "Operational risk register is trending upward.",
                source="Operational risks",
                priority="next_shift",
            )
        else:
            _reinforce("Operational risk register remains contained.")
    _collect_actions(risk_register.get("recommended_actions"))
    _collect_watch(
        entry.get("detail")
        for entry in risk_register.get("risks", [])
        if isinstance(entry, dict)
    )
    _register_window(risk_register.get("next_review_hours"))

    for gap in gaps if isinstance(gaps, list) else []:
        if not isinstance(gap, dict):
            continue
        severity = str(gap.get("severity", "")).lower()
        detail = str(gap.get("detail", "") or gap.get("gap", "")).strip()
        trigger = f"Gap: {detail}" if detail else "Open intelligence gap"
        if severity == "critical":
            _penalise(
                12,
                f"Critical intelligence gap: {detail}.",
                source="Intelligence gaps",
                priority="immediate",
                trigger=trigger,
                action=gap.get("recommended_action"),
            )
        elif severity == "major":
            _penalise(
                8,
                f"Major intelligence gap: {detail}.",
                source="Intelligence gaps",
                priority="prepare",
                trigger=trigger,
                action=gap.get("recommended_action"),
            )
        else:
            _penalise(
                4,
                f"Open intelligence gap: {detail}.",
                source="Intelligence gaps",
                priority="next_shift",
                trigger=trigger,
                action=gap.get("recommended_action"),
            )
        if detail:
            _collect_watch([detail])

    feeds = freshness.get("feeds") if isinstance(freshness, dict) else {}
    for feed_name, feed_info in (feeds or {}).items():
        if not isinstance(feed_info, dict):
            continue
        status = str(feed_info.get("status", "")).lower()
        label = f"{str(feed_name).capitalize()} feed"
        if status == "stale":
            _penalise(
                10,
                f"{label} is stale and will trigger escalation incident response.",
                source="Data freshness",
                priority="immediate",
                trigger=f"{label} stale",
            )
        elif status == "warning":
            _penalise(
                6,
                f"{label} is nearing stale thresholds.",
                source="Data freshness",
                priority="prepare",
                trigger=f"{label} warning",
            )
        elif status == "fresh":
            _reinforce(f"{label} remains fresh for escalation decisions.")

    confidence_level = str(confidence.get("level", "")).lower()
    if confidence_level == "low":
        _penalise(
            11,
            "Intelligence confidence is low and undermines escalation decisions.",
            source="Intelligence confidence",
            priority="immediate",
        )
    elif confidence_level == "guarded":
        _penalise(
            7,
            "Intelligence confidence is guarded and requires validation before escalation.",
            source="Intelligence confidence",
            priority="prepare",
        )
    elif confidence_level == "high":
        _reinforce("Intelligence confidence is high for escalation choices.")
    _collect_actions(confidence.get("recommended_actions"))
    _collect_drivers(confidence.get("drivers"))

    outlook_status = str(outlook.get("status", "")).lower()
    if outlook_status == "escalation_imminent":
        _penalise(
            14,
            "Operational outlook reports escalation is imminent.",
            source="Operational outlook",
            priority="immediate",
        )
    elif outlook_status == "rapid_response":
        _penalise(
            10,
            "Operational outlook is in rapid response posture.",
            source="Operational outlook",
            priority="prepare",
        )
    elif outlook_status in {"heightened_watch", "stabilise"}:
        _penalise(
            6,
            "Operational outlook demands heightened monitoring.",
            source="Operational outlook",
            priority="next_shift",
        )
    elif outlook_status:
        _reinforce("Operational outlook indicates steady posture.")
    _collect_actions(outlook.get("recommended_actions"))
    _collect_drivers(outlook.get("focus_areas"))
    _register_window(outlook.get("planning_horizon_hours"))

    alignment_status = str(alignment.get("status", "")).lower()
    if alignment_status == "misaligned":
        _penalise(
            12,
            "Command alignment is misaligned and complicates escalation.",
            source="Command alignment",
            priority="immediate",
        )
    elif alignment_status == "at_risk":
        _penalise(
            8,
            "Command alignment is at risk and needs synchronisation before escalation.",
            source="Command alignment",
            priority="prepare",
        )
    elif alignment_status == "watch":
        _penalise(
            5,
            "Command alignment watch items remain open.",
            source="Command alignment",
            priority="next_shift",
        )
    elif alignment_status == "aligned":
        _reinforce("Command alignment is intact for escalation decisions.")
    _collect_actions(alignment.get("recommended_actions"))
    _collect_watch(alignment.get("coordination_gaps"))
    _register_window(alignment.get("next_sync_hours"))

    signals = [item for item in dict.fromkeys(signals) if item]
    stability = [item for item in dict.fromkeys(stability) if item]
    drivers = [item for item in dict.fromkeys(drivers) if item]
    actions = [item for item in dict.fromkeys(actions) if item]
    watch_items = [item for item in dict.fromkeys(watch_items) if item]
    review_windows = [value for value in review_windows if isinstance(value, (float, int)) and value > 0]

    pathways = list(pathway_index.values())
    pathways.sort(key=lambda item: (priority_order.get(item.get("priority", "monitor"), 99), item.get("name", "")))

    readiness_score = int(round(score))
    if readiness_score >= 82:
        status = "standby"
    elif readiness_score >= 66:
        status = "monitor"
    elif readiness_score >= 48:
        status = "prepare"
    else:
        status = "escalate"

    payload: Dict[str, Any] = {
        "status": status,
        "readiness_score": readiness_score,
    }
    if pathways:
        payload["escalation_pathways"] = pathways
    if signals:
        payload["escalation_signals"] = signals
    if stability:
        payload["stability_factors"] = stability
    if drivers:
        payload["drivers"] = drivers
    if actions:
        payload["recommended_actions"] = actions
    if watch_items:
        payload["watch_items"] = watch_items
    if review_windows:
        payload["next_review_hours"] = min(review_windows)

    return payload if payload else None


def _derive_automation_force_projection(
    brief: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Fuse automation posture into a force projection plan for Ukrainian operators."""

    strategic = brief.get("automation_strategic_convergence") or {}
    supreme = brief.get("automation_supreme_command") or {}
    theater = brief.get("automation_theater_command") or {}
    joint_ops = brief.get("automation_joint_operations") or {}
    campaign = brief.get("automation_campaign_orchestration") or {}
    battle = brief.get("automation_battle_management") or {}
    mission_control = brief.get("automation_mission_control") or {}
    overwatch = brief.get("automation_overwatch") or {}
    guardrails = brief.get("automation_guardrails") or {}
    playbook = brief.get("automation_playbook") or {}
    autonomy = brief.get("automation_autonomy") or {}
    failsafes = brief.get("automation_failsafes") or {}
    validation = brief.get("automation_validation") or {}
    deployment = brief.get("automation_deployment") or {}

    frontline = brief.get("frontline_support") or {}
    sustainment = brief.get("resource_sustainment") or {}
    readiness = brief.get("response_readiness") or {}
    pressure = brief.get("response_pressure") or {}
    support = brief.get("support_priorities") or {}
    assurance = brief.get("mission_assurance") or {}
    resilience = brief.get("operational_resilience") or {}
    continuity = brief.get("operational_continuity") or {}
    recovery = brief.get("operational_recovery") or {}
    transformation = brief.get("operational_transformation") or {}
    governance = brief.get("operational_governance") or {}
    risk_register = brief.get("operational_risks") or {}

    if not any(
        [
            strategic,
            supreme,
            theater,
            joint_ops,
            campaign,
            battle,
            mission_control,
            overwatch,
            guardrails,
            playbook,
            autonomy,
            failsafes,
            validation,
            deployment,
            frontline,
            sustainment,
            readiness,
            pressure,
            support,
            assurance,
            resilience,
            continuity,
            recovery,
            transformation,
            governance,
            risk_register,
        ]
    ):
        return None

    score = 91.0
    severity = 0
    drivers: List[str] = []
    watch_items: List[str] = []
    recommended_actions: List[str] = []
    prompts: List[str] = []
    projection_channels: List[str] = []
    force_packages: List[str] = []
    dependencies: List[str] = []
    projection_nodes: List[str] = []
    projection_tracks: List[Dict[str, Any]] = []
    windows: List[float] = []

    def _penalise(
        amount: float,
        note: Optional[str] = None,
        *,
        driver: Optional[str] = None,
        action: Optional[str] = None,
        prompt: Optional[str] = None,
    ) -> None:
        nonlocal score, severity
        if amount <= 0:
            return
        severity += int(math.ceil(amount))
        score = max(0.0, score - float(amount))
        if note:
            watch_items.append(str(note))
        if driver:
            drivers.append(str(driver))
        if action:
            recommended_actions.append(str(action))
        if prompt:
            prompts.append(str(prompt))

    def _boost(
        amount: float,
        driver: Optional[str] = None,
        *,
        prompt: Optional[str] = None,
        note: Optional[str] = None,
    ) -> None:
        nonlocal score
        if amount <= 0:
            return
        score = min(100.0, score + float(amount))
        if driver:
            drivers.append(str(driver))
        if prompt:
            prompts.append(str(prompt))
        if note:
            watch_items.append(str(note))

    def _collect_text(values: Optional[Iterable[Any]], target: List[str]) -> None:
        for value in values or []:
            if not value:
                continue
            target.append(str(value))

    def _register_window(value: Optional[float]) -> None:
        if isinstance(value, (float, int)) and value > 0:
            windows.append(round(float(value), 2))

    def _collect_tracks(
        entries: Optional[Iterable[MutableMapping[str, Any]]],
        *,
        source: str,
    ) -> None:
        for entry in entries or []:
            if not isinstance(entry, MutableMapping):
                continue
            name = entry.get("name") or entry.get("track") or entry.get("task")
            if not name:
                continue
            track: Dict[str, Any] = {"name": str(name)}
            lead = entry.get("lead") or entry.get("owner") or entry.get("team")
            if lead:
                track["lead"] = str(lead)
                force_packages.append(str(lead))
            readiness_tag = entry.get("readiness") or entry.get("status")
            if readiness_tag:
                track["readiness"] = str(readiness_tag)
            mode = entry.get("mode") or entry.get("phase")
            if mode:
                track["mode"] = str(mode)
            focus = entry.get("focus")
            if focus:
                track["focus"] = str(focus)
                force_packages.append(str(focus))
            window_value = (
                entry.get("window_hours")
                or entry.get("support_window_hours")
                or entry.get("clearance_hours")
            )
            if isinstance(window_value, (float, int)) and window_value > 0:
                window_float = round(float(window_value), 2)
                track["window_hours"] = window_float
                _register_window(window_float)
            status_tag = entry.get("status")
            if status_tag:
                track["status"] = str(status_tag)
            track["source"] = source
            projection_tracks.append(track)

    def _dedupe(values: Iterable[str]) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            ordered.append(text)
        return ordered

    def _dedupe_tracks(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[Tuple[str, str, str, str]] = set()
        ordered: List[Dict[str, Any]] = []
        for entry in entries:
            name = str(entry.get("name", "")).strip()
            lead = str(entry.get("lead", "")).strip()
            source = str(entry.get("source", "")).strip()
            readiness = str(entry.get("readiness", "")).strip()
            key = (name, lead, source, readiness)
            if not name or key in seen:
                continue
            seen.add(key)
            ordered.append(entry)
        return ordered

    def _collect_actions(source: MutableMapping[str, Any]) -> None:
        _collect_text(source.get("recommended_actions"), recommended_actions)

    def _collect_prompts(source: MutableMapping[str, Any]) -> None:
        _collect_text(source.get("ukrainian_operator_prompts"), prompts)
        _collect_text(source.get("ukrainian_operator_notes"), prompts)
        _collect_text(source.get("ukrainian_safeguards"), prompts)

    def _collect_nodes(values: Optional[Iterable[Any]]) -> None:
        _collect_text(values, projection_nodes)

    # Force projection sensitivity from frontline, sustainment, readiness, and pressure
    frontline_status = str(frontline.get("status", "")).lower()
    if "critical" in frontline_status or "manual" in frontline_status:
        _penalise(
            12,
            "Frontline sustainment is critical; automation must bridge with brigade liaisons.",
            prompt="Негайно узгодьте автоматизовані рішення з офіцером зв'язку бригади.",
            driver="Frontline sustainment under strain",
        )
    elif "mobilise" in frontline_status or "surge" in frontline_status:
        _penalise(
            9,
            "Frontline support is mobilising to cover force projection demands.",
            driver="Frontline mobilisation in progress",
        )
    elif "reinforce" in frontline_status:
        _penalise(5, "Frontline support requires reinforcement to sustain automation outputs.")
    elif "steady" in frontline_status:
        _boost(2, driver="Frontline sustainment steady for projection windows")

    sustainment_status = str(sustainment.get("status", "")).lower()
    if any(tag in sustainment_status for tag in ("surge", "mobilise", "critical")):
        _penalise(
            8,
            "Sustainment posture is surging and risks projection resupply queues.",
            prompt="Підготуйте резервні колони забезпечення для автоматизованих задач.",
        )
    elif any(tag in sustainment_status for tag in ("reinforce", "accelerate")):
        _penalise(5, "Sustainment cadence elevated; pair automation with logistics control.")
    elif "steady" in sustainment_status or "reinforced" in sustainment_status:
        _boost(3, driver="Sustainment plan supporting force projection cadence")

    readiness_level = str(readiness.get("level", "")).lower()
    _register_window(
        readiness.get("support_window_hours")
        if isinstance(readiness.get("support_window_hours"), (float, int))
        else None
    )
    if readiness_level == "critical":
        _penalise(
            10,
            "Response readiness is critical and limits projection coverage.",
            prompt="Посильте бойові зміни для контролю автоматизованих каналів.",
        )
    elif readiness_level == "strained":
        _penalise(6, "Response readiness strained; maintain manual pairing on releases.")
    elif readiness_level in {"steady", "ready"}:
        _boost(3, driver="Readiness coverage supports projected automation runs")

    pressure_status = str(pressure.get("status", "")).lower()
    _register_window(
        pressure.get("estimated_clearance_hours")
        if isinstance(pressure.get("estimated_clearance_hours"), (float, int))
        else None
    )
    if "critical" in pressure_status:
        _penalise(
            9,
            "Analyst pressure is critical; projection requires backlog relief before scaling.",
        )
    elif pressure_status in {"backlog", "prediction_gap"}:
        _penalise(6, "Analyst queues elevated; sequence projection launches carefully.")
    elif "steady" in pressure_status or "controlled" in pressure_status:
        _boost(2, driver="Analyst pressure steady for projection windows")

    assurance_status = str(assurance.get("status", "")).lower()
    if assurance_status in {"critical", "at_risk"}:
        _penalise(6, "Mission assurance is at risk; leadership requires manual coordination.")
    elif assurance_status in {"stabilise", "secured"}:
        _boost(2, driver="Mission assurance supporting projection agenda")

    resilience_status = str(resilience.get("status", "")).lower()
    if resilience_status in {"fragile", "stressed"}:
        _penalise(5, "Operational resilience fragile; protect automated force packages.")
    elif resilience_status in {"resilient", "reinforced"}:
        _boost(2, driver="Resilience factors cushioning automation scale-up")

    continuity_status = str(continuity.get("status", "")).lower()
    if continuity_status in {"disrupted", "constrained", "degraded"}:
        _penalise(5, "Continuity constraints limit projection corridors.")
    elif continuity_status in {"stable", "protected"}:
        _boost(2, driver="Continuity protections covering projection corridors")

    recovery_status = str(recovery.get("status", "")).lower()
    if recovery_status in {"stalled", "recover"}:
        _penalise(3, "Recovery tracks still stabilising logistics nodes.")

    transform_score = transformation.get("transformation_score")
    if isinstance(transform_score, (float, int)):
        if transform_score >= 78:
            _boost(3, driver="Transformation agenda unlocking automation expansion")
        elif transform_score < 55:
            _penalise(3, "Transformation maturity low; projection requires manual guardrails.")

    governance_score = governance.get("governance_score")
    if isinstance(governance_score, (float, int)) and governance_score < 60:
        _penalise(3, "Governance cadence lagging for national projection approvals.")
    _register_window(
        governance.get("next_review_hours")
        if isinstance(governance.get("next_review_hours"), (float, int))
        else None
    )

    risk_score = risk_register.get("severity_score")
    if isinstance(risk_score, (float, int)):
        if risk_score >= 90:
            _penalise(7, "Operational risk register flags critical automation blockers.")
        elif risk_score >= 75:
            _penalise(4, "Operational risk register highlights major automation constraints.")

    # Automation posture blending
    def _status_text(payload: MutableMapping[str, Any]) -> str:
        return str(payload.get("status", "")).lower()

    strategic_status = _status_text(strategic)
    if "manual" in strategic_status:
        _penalise(
            8,
            "Strategic convergence requires manual bridge before national projection.",
        )
    elif "bridge" in strategic_status or "coalition" in strategic_status:
        _penalise(5, "Strategic convergence still bridging allied command nodes.")
    elif strategic_status in {"mission_ready", "strategic_sync"}:
        _boost(4, driver="Strategic convergence aligned for projection")

    supreme_status = _status_text(supreme)
    if "manual" in supreme_status or "hold" in supreme_status:
        _penalise(8, "Supreme automation command enforcing manual posture.")
    elif "watch" in supreme_status or "paired" in supreme_status:
        _penalise(4, "Supreme command keeping automation under watch before releases.")
    elif "mission_ready" in supreme_status:
        _boost(3, driver="Supreme command cleared for projection cadence")

    theater_status = _status_text(theater)
    if "manual" in theater_status:
        _penalise(6, "Theatre automation is bridged; coordinate releases manually.")
    elif "synchronised" in theater_status or "ready" in theater_status:
        _boost(2, driver="Theatre automation synchronised for deployment")

    joint_status = _status_text(joint_ops)
    if "manual" in joint_status:
        _penalise(6, "Joint automation requires coalition bridge before projection.")
    elif "ready" in joint_status or "coalition" in joint_status:
        _boost(2, driver="Joint automation ready for coalition deployment")

    battle_status = _status_text(battle)
    if "manual" in battle_status or "bridge" in battle_status:
        _penalise(5, "Battle management enforcing manual guardrails on automation.")
    elif "mission_ready" in battle_status or "coordinated" in battle_status:
        _boost(2, driver="Battle management synchronised for projection")

    mission_status = _status_text(mission_control)
    if "manual" in mission_status:
        _penalise(5, "Mission control supervising automation manually.")
    elif "autonomous" in mission_status or "mission_ready" in mission_status:
        _boost(2, driver="Mission control aligned for projected automation")

    overwatch_status = _status_text(overwatch)
    if "manual" in overwatch_status or "hold" in overwatch_status:
        _penalise(4, "Automation overwatch gating unattended releases.")

    guardrail_status = _status_text(guardrails)
    if "locked" in guardrail_status or "manual" in guardrail_status:
        _penalise(6, "Automation guardrails locked down for projection tasks.")
    elif "autonomous" in guardrail_status:
        _boost(2, driver="Guardrails supporting wider projection windows")

    playbook_status = _status_text(playbook)
    if "manual" in playbook_status:
        _penalise(5, "Automation playbook running in manual mode.")
    elif "autonomous" in playbook_status or "steady" in playbook_status:
        _boost(2, driver="Automation playbook sustaining projection rhythm")

    autonomy_status = _status_text(autonomy)
    if "manual" in autonomy_status:
        _penalise(6, "Automation autonomy requires supervision before projecting tasks.")
    elif "autonomous" in autonomy_status or "mission_ready" in autonomy_status:
        _boost(3, driver="Automation autonomy cleared for wider release windows")

    deployment_status = _status_text(deployment)
    if "hold" in deployment_status or "paused" in deployment_status:
        _penalise(6, "Automation deployment paused; defer projection launches.")
    elif "ready" in deployment_status or "go" in deployment_status:
        _boost(3, driver="Deployment checks cleared for projection wave")

    validation_status = _status_text(validation)
    if "manual" in validation_status or "hold" in validation_status:
        _penalise(4, "Automation validation requires manual sampling.")

    failsafe_status = _status_text(failsafes)
    if "manual" in failsafe_status or "at_risk" in failsafe_status:
        _penalise(4, "Automation failsafes require manual oversight.")

    # Collect supporting context
    _collect_text(frontline.get("priority_units"), force_packages)
    _collect_text(frontline.get("support_corridors"), dependencies)
    _collect_text(frontline.get("drivers"), drivers)
    _collect_text(frontline.get("signals"), watch_items)
    _collect_text(frontline.get("ukrainian_operator_notes"), prompts)

    _collect_text(sustainment.get("resource_needs"), force_packages)
    _collect_text(sustainment.get("support_dependencies"), dependencies)
    for entry in sustainment.get("allocation_plan", []) or []:
        if isinstance(entry, MutableMapping):
            resource = entry.get("resource") or entry.get("focus")
            quantity = entry.get("quantity")
            window = entry.get("window_hours")
            if resource:
                descriptor = str(resource)
                if isinstance(quantity, (float, int)) and quantity > 0:
                    descriptor = f"{descriptor} ({int(math.ceil(float(quantity)))} units)"
                force_packages.append(descriptor)
            if isinstance(window, (float, int)):
                _register_window(float(window))

    for priority in support.get("priorities", []) or []:
        if isinstance(priority, MutableMapping):
            name = priority.get("name") or priority.get("team") or priority.get("focus")
            if name:
                force_packages.append(str(name))
            _register_window(priority.get("support_window_hours") if isinstance(priority.get("support_window_hours"), (float, int)) else None)

    _collect_text(joint_ops.get("support_cells"), force_packages)
    _collect_text(joint_ops.get("integration_channels"), projection_channels)
    _collect_text(joint_ops.get("coalition_partners"), projection_nodes)

    _collect_text(theater.get("command_channels"), projection_channels)
    _collect_nodes(theater.get("coordinating_theaters"))
    _collect_nodes(theater.get("coalition_commanders"))

    _collect_text(supreme.get("integration_channels"), projection_channels)
    _collect_nodes(supreme.get("command_nodes"))
    _collect_text(supreme.get("coalition_liaisons"), projection_nodes)
    _collect_text(supreme.get("support_dependencies"), dependencies)

    _collect_nodes(strategic.get("national_command_nodes"))
    _collect_text(strategic.get("strategic_channels"), projection_channels)
    _collect_text(strategic.get("coalition_partners"), projection_nodes)
    _register_window(
        strategic.get("next_convergence_window_hours")
        if isinstance(strategic.get("next_convergence_window_hours"), (float, int))
        else None
    )

    _collect_text(battle.get("coordination_cells"), projection_nodes)
    _collect_text(battle.get("mission_channels"), projection_channels)

    _collect_text(mission_control.get("mission_channels"), projection_channels)
    _collect_text(mission_control.get("handoff_requirements"), dependencies)

    _collect_text(overwatch.get("monitoring_channels"), projection_channels)
    _collect_text(guardrails.get("monitoring_channels"), projection_channels)
    _collect_text(playbook.get("automation_channels"), projection_channels)

    _collect_text(failsafes.get("fallback_channels"), projection_channels)

    # Tracks across automation pillars
    _collect_tracks(strategic.get("cross_domain_tracks"), source="strategic")
    _collect_tracks(supreme.get("command_tracks"), source="supreme")
    _collect_tracks(theater.get("command_tracks"), source="theater")
    _collect_tracks(joint_ops.get("joint_operation_tracks"), source="joint")
    _collect_tracks(campaign.get("orchestration_tracks"), source="campaign")
    _collect_tracks(battle.get("coordination_tracks"), source="battle")
    _collect_tracks(mission_control.get("control_tracks"), source="mission_control")
    _collect_tracks(playbook.get("automation_tasks"), source="playbook")
    _collect_tracks(deployment.get("deployment_tracks"), source="deployment")

    _collect_actions(frontline)
    _collect_actions(sustainment)
    _collect_actions(support)
    _collect_actions(readiness)
    _collect_actions(pressure)
    _collect_actions(strategic)
    _collect_actions(supreme)
    _collect_actions(theater)
    _collect_actions(joint_ops)
    _collect_actions(campaign)
    _collect_actions(battle)
    _collect_actions(mission_control)
    _collect_actions(overwatch)
    _collect_actions(guardrails)
    _collect_actions(playbook)
    _collect_actions(autonomy)
    _collect_actions(failsafes)
    _collect_actions(validation)
    _collect_actions(deployment)
    _collect_actions(assurance)
    _collect_actions(resilience)
    _collect_actions(continuity)
    _collect_actions(recovery)
    _collect_actions(transformation)

    _collect_prompts(frontline)
    _collect_prompts(playbook)
    _collect_prompts(guardrails)
    _collect_prompts(mission_control)
    _collect_prompts(overwatch)
    _collect_prompts(autonomy)
    _collect_prompts(failsafes)
    _collect_prompts(strategic)
    _collect_prompts(supreme)
    _collect_prompts(theater)
    _collect_prompts(joint_ops)

    # Deduplicate collections
    force_packages = _dedupe(force_packages)
    dependencies = _dedupe(dependencies)
    projection_channels = _dedupe(projection_channels)
    projection_nodes = _dedupe(projection_nodes)
    drivers = _dedupe(drivers)
    watch_items = _dedupe(watch_items)
    recommended_actions = _dedupe(recommended_actions)
    prompts = _dedupe(prompts)
    projection_tracks = _dedupe_tracks(projection_tracks)

    projection_window: Optional[float] = None
    positive_windows = [value for value in windows if value > 0]
    if positive_windows:
        projection_window = round(min(positive_windows), 2)

    status = "projection_ready"
    if severity >= 34 or score < 50:
        status = "manual_override"
    elif severity >= 24 or score < 60:
        status = "projection_bridge"
    elif severity >= 16 or score < 70:
        status = "mobilise"
    elif severity >= 9 or score < 78:
        status = "reinforce"
    elif severity >= 4 or score < 88:
        status = "watch"
    elif score >= 96 and severity <= 3:
        status = "campaign_ready"

    payload: Dict[str, Any] = {
        "status": status,
        "force_projection_score": round(score, 1),
    }

    if severity > 0:
        payload["severity_index"] = severity
    if projection_window is not None:
        payload["projection_window_hours"] = projection_window
    if force_packages:
        payload["force_packages"] = force_packages
    if dependencies:
        payload["support_dependencies"] = dependencies
    if projection_channels:
        payload["projection_channels"] = projection_channels
    if projection_nodes:
        payload["projection_nodes"] = projection_nodes
    if projection_tracks:
        payload["projection_tracks"] = projection_tracks
    if drivers:
        payload["drivers"] = drivers
    if watch_items:
        payload["watch_items"] = watch_items
    if recommended_actions:
        payload["recommended_actions"] = recommended_actions
    if prompts:
        payload["ukrainian_operator_prompts"] = prompts

    return payload if payload else None


def gather_intelligence_brief(
    *,
    area: Optional[str] = None,
    hours: int = 24,
    activity_limit: int = 20,
) -> Dict[str, Any]:
    """Return a consolidated intelligence brief.

    Parameters
    ----------
    area:
        Restrict the report to a particular operational area when provided.
    hours:
        Look-back window for time-bounded metrics such as detection summaries
        and cluster scoring.
    activity_limit:
        Maximum number of raw detection/prediction records to include.
    """

    if hours <= 0:
        raise ValueError("hours must be a positive integer")
    if activity_limit <= 0:
        raise ValueError("activity_limit must be a positive integer")

    normalized_area = area.strip() if area else None
    if normalized_area == "":
        normalized_area = None

    generated_at = _utcnow()
    brief: Dict[str, Any] = {
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "area": normalized_area,
        "errors": [],
    }

    # Meta overview (detection counts, feedback accuracy, cluster count)
    try:
        meta = meta_analysis(hours=hours)
        brief["meta"] = meta
        if meta.get("detections"):
            top_cls, stats = max(
                meta["detections"].items(),
                key=lambda item: item[1].get("count", 0),
            )
            brief.setdefault("insights", {})["top_detection_class"] = {
                "class": top_cls,
                **stats,
            }
        if meta.get("feedback_accuracy") is not None and meta["feedback_accuracy"] < 0.75:
            _append_recommendation(
                brief,
                "Feedback accuracy is trending low; schedule a targeted review session.",
            )
        quality = _analyse_detection_quality(meta)
        if quality:
            brief["detection_quality"] = quality
            detection_insight: Dict[str, Any] = {
                key: value
                for key, value in quality.items()
                if key in {"weighted_avg_confidence", "low_confidence_classes", "active_class_ratio"}
            }
            if detection_insight:
                brief.setdefault("insights", {})["detection_quality"] = detection_insight
            low_conf = quality.get("low_confidence_classes", [])
            if low_conf:
                joined = ", ".join(low_conf)
                _append_recommendation(
                    brief,
                    f"Low detection confidence flagged for classes: {joined}. Calibrate the associated sensors.",
                )
            sparse = quality.get("sparse_class_coverage", [])
            if sparse:
                joined = ", ".join(sparse)
                _append_recommendation(
                    brief,
                    f"Detection coverage is sparse for classes: {joined}. Review collection plans to balance coverage.",
                )
            for note in quality.get("notes", []):
                _append_recommendation(brief, note)
    except (PyMongoError, ConnectionError, OSError) as exc:
        brief["errors"].append(f"Meta analysis unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - defensive catch
        brief["errors"].append(f"Meta analysis failed: {exc}")

    # Recent detections and predictions
    activity: Dict[str, Any] = {}
    try:
        if normalized_area:
            activity["detections"] = [
                _normalize_document(doc)
                for doc in recent_detections(normalized_area, limit=activity_limit)
            ]
            activity["predictions"] = [
                _normalize_document(doc)
                for doc in recent_predictions(normalized_area, limit=activity_limit)
            ]
        else:
            activity["detections"] = _recent_documents(
                "detections", hours=hours, limit=activity_limit
            )
            activity["predictions"] = _recent_documents(
                "predictions", hours=hours, limit=activity_limit
            )
    except (PyMongoError, ConnectionError, OSError) as exc:
        brief["errors"].append(f"Failed to load recent activity: {exc}")
    except Exception as exc:  # pragma: no cover - defensive catch
        brief["errors"].append(f"Unexpected activity error: {exc}")
    if activity:
        brief["recent_activity"] = activity
        if activity.get("detections") and not activity.get("predictions"):
            _append_recommendation(
                brief,
                "Predictions are unavailable for the selected scope; verify the inference pipeline.",
            )
        summary = _assess_activity(activity, hours=hours, activity_limit=activity_limit)
        if summary:
            brief["activity_summary"] = summary
            brief.setdefault("insights", {})["operational_tempo"] = {
                key: value
                for key, value in summary.items()
                if key in {"tempo", "prediction_coverage", "detections", "predictions"}
            }
            for note in summary.get("notes", []):
                _append_recommendation(brief, note)

    # Threat scoring from movement clusters
    cluster_docs: List[Dict[str, Any]] = []
    try:
        clusters = _recent_clusters(hours=hours, area=normalized_area)
        cluster_docs = clusters
        if clusters:
            scored = score_clusters(clusters)
            brief["cluster_threats"] = scored
            highest = max(scored, key=lambda c: c.get("threat_score", 0))
            brief.setdefault("insights", {})["highest_threat_cluster"] = {
                "threat_level": highest.get("threat_level"),
                "threat_score": highest.get("threat_score"),
                "nearest_site": highest.get("nearest_site"),
                "eta_minutes": highest.get("eta_minutes"),
            }
            if any(c.get("threat_level") in {"high", "critical"} for c in scored):
                _append_recommendation(
                    brief,
                    "Escalate monitoring on clusters flagged as high or critical threat levels.",
                )
        else:
            brief.setdefault("insights", {})["highest_threat_cluster"] = None
    except (PyMongoError, ConnectionError, OSError) as exc:
        brief["errors"].append(f"Threat assessment unavailable: {exc}")
    except Exception as exc:  # pragma: no cover - defensive catch
        brief["errors"].append(f"Threat assessment failed: {exc}")

    freshness = _summarise_freshness(
        generated_at=generated_at,
        activity=activity,
        clusters=cluster_docs,
        hours=hours,
    )
    if freshness:
        brief["data_freshness"] = freshness
        feeds = freshness.get("feeds", {})
        for feed_name, feed_info in feeds.items():
            status = feed_info.get("status")
            if status == "warning":
                _append_recommendation(
                    brief,
                    f"{feed_name.capitalize()} feed is getting stale; investigate pipeline latency.",
                )
            elif status == "stale":
                _append_recommendation(
                    brief,
                    f"{feed_name.capitalize()} feed is stale; prioritise data ingestion recovery.",
                )
        if freshness.get("stalest_feed"):
            brief.setdefault("insights", {})["data_freshness"] = {
                "stalest_feed": freshness["stalest_feed"],
                "worst_case_minutes": freshness.get("worst_case_minutes"),
            }

    health = _derive_brief_health(brief)
    if health:
        brief["health"] = health
        for action in health.get("recommended_actions", []):
            _append_recommendation(brief, action)

    posture = _derive_operational_posture(brief)
    if posture:
        brief["operational_posture"] = posture
        brief.setdefault("insights", {})["operational_posture"] = {
            "status": posture.get("status"),
            "focus": posture.get("focus"),
            "horizon_hours": posture.get("horizon_hours"),
        }
        status = posture.get("status")
        if status == "recover":
            _append_recommendation(
                brief,
                "Assign a telemetry recovery lead to restore degraded feeds within the hour.",
            )
        elif status == "stabilise":
            _append_recommendation(
                brief,
                "Ensure command staff are briefed on the stabilisation posture and response plans.",
            )
        elif status == "reinforce":
            _append_recommendation(
                brief,
                "Extend analyst coverage to manage the elevated operational tempo.",
            )

    readiness = _derive_response_readiness(brief)
    if readiness:
        brief["response_readiness"] = readiness
        brief.setdefault("insights", {})["response_readiness"] = {
            "level": readiness.get("level"),
            "recommended_staffing": readiness.get("recommended_staffing"),
            "support_window_hours": readiness.get("support_window_hours"),
        }
        for action in readiness.get("priority_actions", []):
            _append_recommendation(brief, action)

    pressure = _derive_response_pressure(brief)
    if pressure:
        brief["response_pressure"] = pressure
        brief.setdefault("insights", {})["response_pressure"] = {
            "status": pressure.get("status"),
            "pending_predictions": pressure.get("pending_predictions"),
            "unmatched_detections": pressure.get("unmatched_detections"),
            "severity": pressure.get("severity"),
        }
        for action in pressure.get("recommended_actions", []):
            _append_recommendation(brief, action)

    gaps = _derive_intelligence_gaps(brief)
    if gaps:
        brief["intelligence_gaps"] = gaps
        critical = sum(1 for gap in gaps if gap.get("severity") == "critical")
        major = sum(1 for gap in gaps if gap.get("severity") == "major")
        brief.setdefault("insights", {})["intelligence_gaps"] = {
            "total": len(gaps),
            "critical": critical,
            "major": major,
        }
        for gap in gaps:
            action = gap.get("recommended_action")
            if action:
                _append_recommendation(brief, action)

    support = _derive_support_priorities(brief)
    if support:
        brief["support_priorities"] = support
        brief.setdefault("insights", {})["support_priorities"] = {
            "status": support.get("status"),
            "priority_count": len(support.get("priorities", [])),
        }
        for action in support.get("recommended_actions", []):
            _append_recommendation(brief, action)

    confidence = _derive_intelligence_confidence(brief)
    if confidence:
        brief["intelligence_confidence"] = confidence
        brief.setdefault("insights", {})["intelligence_confidence"] = {
            "level": confidence.get("level"),
            "score": confidence.get("score"),
            "status": confidence.get("status"),
        }
        for action in confidence.get("recommended_actions", []):
            _append_recommendation(brief, action)

    outlook = _derive_operational_outlook(brief)
    if outlook:
        brief["operational_outlook"] = outlook
        brief.setdefault("insights", {})["operational_outlook"] = {
            "status": outlook.get("status"),
            "severity_score": outlook.get("severity_score"),
            "planning_horizon_hours": outlook.get("planning_horizon_hours"),
        }
        for action in outlook.get("recommended_actions", []):
            _append_recommendation(brief, action)

    if not brief.get("recommendations") and not brief.get("errors"):
        brief["recommendations"] = [
            "Continue routine monitoring; no immediate anomalies detected in the selected window."
        ]

    directives = _derive_command_directives(brief)
    if directives:
        brief["command_directives"] = directives
        counts = directives.get("directive_counts", {})
        insight: Dict[str, Any] = {
            "status": directives.get("status"),
            "severity": directives.get("severity"),
            "immediate": counts.get("immediate", 0),
            "next_shift": counts.get("next_shift", 0),
        }
        if directives.get("planning_window_hours") is not None:
            insight["planning_window_hours"] = directives["planning_window_hours"]
        brief.setdefault("insights", {})["command_directives"] = insight

    comms_plan = _derive_communication_plan(brief)
    if comms_plan:
        brief["communication_plan"] = comms_plan
        insight: Dict[str, Any] = {
            "status": comms_plan.get("status"),
            "audience_count": len(comms_plan.get("audiences", [])),
            "update_cadence_minutes": comms_plan.get("update_cadence_minutes"),
        }
        key_messages = comms_plan.get("key_messages")
        if isinstance(key_messages, list) and key_messages:
            insight["key_messages"] = key_messages[:2]
        brief.setdefault("insights", {})["communication_plan"] = insight
        for action in comms_plan.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    contingency = _derive_contingency_plans(brief)
    if contingency:
        brief["contingency_plans"] = contingency
        brief.setdefault("insights", {})["contingency_plans"] = {
            "status": contingency.get("status"),
            "scenario_count": len(contingency.get("scenarios", [])),
            "watch_items": contingency.get("watch_items", [])[:3],
        }
        for action in contingency.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    sustainment = _derive_resource_sustainment(brief)
    if sustainment:
        brief["resource_sustainment"] = sustainment
        insight: Dict[str, Any] = {
            "status": sustainment.get("status"),
            "needs": len(sustainment.get("resource_needs", [])),
            "resupply_window_hours": sustainment.get("resupply_window_hours"),
        }
        allocation = sustainment.get("allocation_plan")
        if isinstance(allocation, list) and allocation:
            insight["allocation_count"] = len(allocation)
        brief.setdefault("insights", {})["resource_sustainment"] = insight
        for action in sustainment.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    risk_register = _derive_operational_risk_register(brief)
    if risk_register:
        brief["operational_risks"] = risk_register
        insight = {
            "status": risk_register.get("status"),
            "risk_count": risk_register.get("risk_count"),
            "severity_score": risk_register.get("severity_score"),
        }
        top_risk = None
        risks = risk_register.get("risks")
        if isinstance(risks, list) and risks:
            top_risk = risks[0]
        if isinstance(top_risk, dict) and top_risk.get("name"):
            insight["top_risk"] = top_risk["name"]
        if risk_register.get("next_review_hours") is not None:
            insight["next_review_hours"] = risk_register["next_review_hours"]
        brief.setdefault("insights", {})["operational_risks"] = insight
        for action in risk_register.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    alignment = _derive_command_alignment(brief)
    if alignment:
        brief["command_alignment"] = alignment
        insight: Dict[str, Any] = {
            "status": alignment.get("status"),
            "alignment_score": alignment.get("alignment_score"),
        }
        if alignment.get("coordination_gaps"):
            insight["coordination_gaps"] = len(alignment.get("coordination_gaps", []))
        focus = alignment.get("focus_areas")
        if isinstance(focus, list) and focus:
            insight["focus_areas"] = focus[:3]
        if alignment.get("next_sync_hours") is not None:
            insight["next_sync_hours"] = alignment["next_sync_hours"]
        brief.setdefault("insights", {})["command_alignment"] = insight
        for action in alignment.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    assurance = _derive_mission_assurance(brief)
    if assurance:
        brief["mission_assurance"] = assurance
        insight: Dict[str, Any] = {
            "status": assurance.get("status"),
            "assurance_score": assurance.get("assurance_score"),
        }
        blockers = assurance.get("blockers")
        if isinstance(blockers, list) and blockers:
            insight["blocker_count"] = len(blockers)
        checkpoint = assurance.get("next_checkpoint_hours")
        if checkpoint is not None:
            insight["next_checkpoint_hours"] = checkpoint
        focus = assurance.get("focus_areas")
        if isinstance(focus, list) and focus:
            insight["focus_areas"] = focus[:3]
        brief.setdefault("insights", {})["mission_assurance"] = insight
        for action in assurance.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    resilience = _derive_operational_resilience(brief)
    if resilience:
        brief["operational_resilience"] = resilience
        insight: Dict[str, Any] = {
            "status": resilience.get("status"),
            "resilience_score": resilience.get("resilience_score"),
        }
        weak = resilience.get("weak_spots")
        if isinstance(weak, list) and weak:
            insight["weak_spot_count"] = len(weak)
        reinforce = resilience.get("reinforcing_factors")
        if isinstance(reinforce, list) and reinforce:
            insight["reinforcing_factors"] = reinforce[:2]
        window = resilience.get("stability_window_hours")
        if isinstance(window, (float, int)):
            insight["stability_window_hours"] = window
        brief.setdefault("insights", {})["operational_resilience"] = insight
        for action in resilience.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    continuity = _derive_operational_continuity(brief)
    if continuity:
        brief["operational_continuity"] = continuity
        insight: Dict[str, Any] = {
            "status": continuity.get("status"),
            "score": continuity.get("continuity_score"),
        }
        horizon = continuity.get("continuity_horizon_hours")
        if isinstance(horizon, (float, int)):
            insight["horizon_hours"] = horizon
        constraints = continuity.get("primary_constraints")
        if isinstance(constraints, list) and constraints:
            insight["constraints"] = constraints[:2]
        brief.setdefault("insights", {})["operational_continuity"] = insight
        for action in continuity.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    escalation = _derive_escalation_matrix(brief)
    if escalation:
        brief["escalation_readiness"] = escalation
        insight: Dict[str, Any] = {
            "status": escalation.get("status"),
            "score": escalation.get("readiness_score"),
        }
        pathways = escalation.get("escalation_pathways")
        if isinstance(pathways, list) and pathways:
            first = pathways[0]
            if isinstance(first, dict) and first.get("priority"):
                insight["primary_priority"] = first["priority"]
        review = escalation.get("next_review_hours")
        if isinstance(review, (float, int)):
            insight["next_review_hours"] = review
        brief.setdefault("insights", {})["escalation_readiness"] = insight
        for action in escalation.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    recovery = _derive_operational_recovery(brief)
    if recovery:
        brief["operational_recovery"] = recovery
        insight: Dict[str, Any] = {
            "status": recovery.get("status"),
            "score": recovery.get("recovery_score"),
        }
        if recovery.get("recovery_phase"):
            insight["phase"] = recovery.get("recovery_phase")
        if recovery.get("critical_dependencies"):
            insight["dependency_count"] = len(recovery.get("critical_dependencies", []))
        brief.setdefault("insights", {})["operational_recovery"] = insight
        for action in recovery.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    transformation = _derive_operational_transformation(brief)
    if transformation:
        brief["operational_transformation"] = transformation
        insight: Dict[str, Any] = {
            "status": transformation.get("status"),
            "score": transformation.get("transformation_score"),
        }
        if transformation.get("maturity_stage"):
            insight["stage"] = transformation.get("maturity_stage")
        if transformation.get("quick_wins"):
            insight["quick_wins"] = len(transformation.get("quick_wins", []))
        if transformation.get("long_horizon_initiatives"):
            insight["initiatives"] = len(transformation.get("long_horizon_initiatives", []))
        brief.setdefault("insights", {})["operational_transformation"] = insight
        for action in transformation.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    frontline = _derive_frontline_support(brief)
    if frontline:
        brief["frontline_support"] = frontline
        insight: Dict[str, Any] = {"status": frontline.get("status")}
        score = frontline.get("support_score")
        if isinstance(score, (float, int)):
            insight["support_score"] = score
        units = frontline.get("priority_units")
        if isinstance(units, list) and units:
            insight["priority_unit_count"] = len(units)
        window = frontline.get("coordination_window_hours")
        if isinstance(window, (float, int)):
            insight["coordination_window_hours"] = window
        brief.setdefault("insights", {})["frontline_support"] = insight
        for action in frontline.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    automation = _derive_automation_playbook(brief)
    if automation:
        brief["automation_playbook"] = automation
        insight = {
            "status": automation.get("status"),
            "automation_score": automation.get("automation_score"),
        }
        tasks = automation.get("automation_tasks")
        if isinstance(tasks, list) and tasks:
            insight["task_count"] = len(tasks)
        window = automation.get("automation_window_hours")
        if isinstance(window, (float, int)):
            insight["automation_window_hours"] = window
        brief.setdefault("insights", {})["automation_playbook"] = insight
        for action in automation.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    guardrails = _derive_automation_guardrails(brief)
    if guardrails:
        brief["automation_guardrails"] = guardrails
        insight = {
            "status": guardrails.get("status"),
            "score": guardrails.get("autonomy_score"),
        }
        review = guardrails.get("next_review_hours")
        if isinstance(review, (float, int)):
            insight["next_review_hours"] = review
        guardrail_count = guardrails.get("guardrails")
        if isinstance(guardrail_count, list) and guardrail_count:
            insight["guardrail_count"] = len(guardrail_count)
        brief.setdefault("insights", {})["automation_guardrails"] = insight
        for action in guardrails.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    mission_control = _derive_automation_mission_control(brief)
    if mission_control:
        brief["automation_mission_control"] = mission_control
        insight = {
            "status": mission_control.get("status"),
            "score": mission_control.get("mission_control_score"),
        }
        next_sync = mission_control.get("next_sync_hours")
        if isinstance(next_sync, (float, int)):
            insight["next_sync_hours"] = next_sync
        supervision = mission_control.get("supervision_level")
        if supervision:
            insight["supervision_level"] = supervision
        brief.setdefault("insights", {})["automation_mission_control"] = insight
        for action in mission_control.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    autonomy = _derive_automation_autonomy(brief)
    if autonomy:
        brief["automation_autonomy"] = autonomy
        insight = {
            "status": autonomy.get("status"),
            "score": autonomy.get("autonomy_score"),
        }
        window = autonomy.get("autonomy_window_hours")
        if isinstance(window, (float, int)):
            insight["autonomy_window_hours"] = window
        trusted = autonomy.get("trusted_tasks")
        if isinstance(trusted, list) and trusted:
            insight["trusted_task_count"] = len(trusted)
        brief.setdefault("insights", {})["automation_autonomy"] = insight
        for action in autonomy.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    failsafes = _derive_automation_failsafes(brief)
    if failsafes:
        brief["automation_failsafes"] = failsafes
        insight = {
            "status": failsafes.get("status"),
            "score": failsafes.get("failsafe_score"),
        }
        window = failsafes.get("failsafe_window_hours")
        if isinstance(window, (float, int)):
            insight["failsafe_window_hours"] = window
        tests = failsafes.get("failsafe_tests")
        if isinstance(tests, list) and tests:
            insight["test_count"] = len(tests)
        brief.setdefault("insights", {})["automation_failsafes"] = insight
        for action in failsafes.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    validation = _derive_automation_validation(brief)
    if validation:
        brief["automation_validation"] = validation
        insight = {
            "status": validation.get("status"),
            "score": validation.get("validation_score"),
        }
        window = validation.get("validation_window_hours")
        if isinstance(window, (float, int)):
            insight["validation_window_hours"] = window
        requirements = validation.get("training_requirements")
        if isinstance(requirements, list) and requirements:
            insight["training_requirement_count"] = len(requirements)
        brief.setdefault("insights", {})["automation_validation"] = insight
        for action in validation.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    deployment = _derive_automation_deployment(brief)
    if deployment:
        brief["automation_deployment"] = deployment
        insight = {
            "status": deployment.get("status"),
            "deployment_score": deployment.get("deployment_score"),
        }
        window = deployment.get("deployment_window_hours")
        if isinstance(window, (float, int)):
            insight["deployment_window_hours"] = window
        brief.setdefault("insights", {})["automation_deployment"] = insight
        for action in deployment.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    overwatch = _derive_automation_overwatch(brief)
    if overwatch:
        brief["automation_overwatch"] = overwatch
        insight = {
            "status": overwatch.get("status"),
            "overwatch_score": overwatch.get("overwatch_score"),
        }
        next_sync = overwatch.get("next_sync_hours")
        if isinstance(next_sync, (float, int)):
            insight["next_sync_hours"] = next_sync
        watch_teams = overwatch.get("watch_teams")
        if isinstance(watch_teams, list) and watch_teams:
            insight["watch_team_count"] = len(watch_teams)
        brief.setdefault("insights", {})["automation_overwatch"] = insight
        for action in overwatch.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    battle_management = _derive_automation_battle_management(brief)
    if battle_management:
        brief["automation_battle_management"] = battle_management
        insight = {
            "status": battle_management.get("status"),
            "battle_management_score": battle_management.get("battle_management_score"),
        }
        window = battle_management.get("battle_management_window_hours")
        if isinstance(window, (float, int)):
            insight["battle_management_window_hours"] = window
        tracks = battle_management.get("coordination_tracks")
        if isinstance(tracks, list) and tracks:
            insight["coordination_track_count"] = len(tracks)
        brief.setdefault("insights", {})["automation_battle_management"] = insight
        for action in battle_management.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    campaign = _derive_automation_campaign_orchestration(brief)
    if campaign:
        brief["automation_campaign_orchestration"] = campaign
        insight = {
            "status": campaign.get("status"),
            "campaign_orchestration_score": campaign.get("campaign_orchestration_score"),
        }
        window = campaign.get("campaign_window_hours")
        if isinstance(window, (float, int)):
            insight["campaign_window_hours"] = window
        tracks = campaign.get("orchestration_tracks")
        if isinstance(tracks, list) and tracks:
            insight["orchestration_track_count"] = len(tracks)
        partners = campaign.get("integration_partners")
        if isinstance(partners, list) and partners:
            insight["integration_partner_count"] = len(partners)
        brief.setdefault("insights", {})["automation_campaign_orchestration"] = insight
        for action in campaign.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    joint_ops = _derive_automation_joint_operations(brief)
    if joint_ops:
        brief["automation_joint_operations"] = joint_ops
        insight = {
            "status": joint_ops.get("status"),
            "joint_operations_score": joint_ops.get("joint_operations_score"),
        }
        window = joint_ops.get("joint_window_hours")
        if isinstance(window, (float, int)):
            insight["joint_window_hours"] = window
        tracks = joint_ops.get("joint_operation_tracks")
        if isinstance(tracks, list) and tracks:
            insight["joint_operation_track_count"] = len(tracks)
        partners = joint_ops.get("coalition_partners")
        if isinstance(partners, list) and partners:
            insight["coalition_partner_count"] = len(partners)
        channels = joint_ops.get("integration_channels")
        if isinstance(channels, list) and channels:
            insight["integration_channel_count"] = len(channels)
        support_cells = joint_ops.get("support_cells")
        if isinstance(support_cells, list) and support_cells:
            insight["support_cell_count"] = len(support_cells)
        brief.setdefault("insights", {})["automation_joint_operations"] = insight
        for action in joint_ops.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    theater_command = _derive_automation_theater_command(brief)
    if theater_command:
        brief["automation_theater_command"] = theater_command
        insight = {
            "status": theater_command.get("status"),
            "theater_command_score": theater_command.get("theater_command_score"),
        }
        window = theater_command.get("command_window_hours")
        if isinstance(window, (float, int)):
            insight["command_window_hours"] = window
        tracks = theater_command.get("command_tracks")
        if isinstance(tracks, list) and tracks:
            insight["command_track_count"] = len(tracks)
        theaters = theater_command.get("coordinating_theaters")
        if isinstance(theaters, list) and theaters:
            insight["coordinating_theater_count"] = len(theaters)
        commanders = theater_command.get("coalition_commanders")
        if isinstance(commanders, list) and commanders:
            insight["coalition_commander_count"] = len(commanders)
        brief.setdefault("insights", {})["automation_theater_command"] = insight
        for action in theater_command.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    supreme_command = _derive_automation_supreme_command(brief)
    if supreme_command:
        brief["automation_supreme_command"] = supreme_command
        insight = {
            "status": supreme_command.get("status"),
            "supreme_command_score": supreme_command.get("supreme_command_score"),
        }
        window = supreme_command.get("command_window_hours")
        if isinstance(window, (float, int)):
            insight["command_window_hours"] = window
        tracks = supreme_command.get("command_tracks")
        if isinstance(tracks, list) and tracks:
            insight["command_track_count"] = len(tracks)
        nodes = supreme_command.get("command_nodes")
        if isinstance(nodes, list) and nodes:
            insight["command_node_count"] = len(nodes)
        brief.setdefault("insights", {})["automation_supreme_command"] = insight
        for action in supreme_command.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    strategic_convergence = _derive_automation_strategic_convergence(brief)
    if strategic_convergence:
        brief["automation_strategic_convergence"] = strategic_convergence
        insight = {
            "status": strategic_convergence.get("status"),
            "strategic_convergence_score": strategic_convergence.get(
                "strategic_convergence_score"
            ),
        }
        window = strategic_convergence.get("next_convergence_window_hours")
        if isinstance(window, (float, int)):
            insight["next_convergence_window_hours"] = window
        tracks = strategic_convergence.get("cross_domain_tracks")
        if isinstance(tracks, list) and tracks:
            insight["cross_domain_track_count"] = len(tracks)
        nodes = strategic_convergence.get("national_command_nodes")
        if isinstance(nodes, list) and nodes:
            insight["national_node_count"] = len(nodes)
        partners = strategic_convergence.get("coalition_partners")
        if isinstance(partners, list) and partners:
            insight["coalition_partner_count"] = len(partners)
        brief.setdefault("insights", {})["automation_strategic_convergence"] = insight
        for action in strategic_convergence.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    force_projection = _derive_automation_force_projection(brief)
    if force_projection:
        brief["automation_force_projection"] = force_projection
        insight = {
            "status": force_projection.get("status"),
            "force_projection_score": force_projection.get("force_projection_score"),
        }
        window = force_projection.get("projection_window_hours")
        if isinstance(window, (float, int)):
            insight["projection_window_hours"] = window
        packages = force_projection.get("force_packages")
        if isinstance(packages, list) and packages:
            insight["force_package_count"] = len(packages)
        tracks = force_projection.get("projection_tracks")
        if isinstance(tracks, list) and tracks:
            insight["projection_track_count"] = len(tracks)
        channels = force_projection.get("projection_channels")
        if isinstance(channels, list) and channels:
            insight["projection_channel_count"] = len(channels)
        brief.setdefault("insights", {})["automation_force_projection"] = insight
        for action in force_projection.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    governance = _derive_operational_governance(brief)
    if governance:
        brief["operational_governance"] = governance
        insight = {
            "status": governance.get("status"),
            "score": governance.get("governance_score"),
        }
        councils = governance.get("oversight_councils")
        if isinstance(councils, list):
            insight["council_count"] = len(councils)
        gaps = governance.get("compliance_gaps")
        if isinstance(gaps, list) and gaps:
            insight["gap_count"] = len(gaps)
        review = governance.get("next_review_hours")
        if isinstance(review, (float, int)):
            insight["next_review_hours"] = review
        brief.setdefault("insights", {})["operational_governance"] = insight
        for action in governance.get("recommended_actions", []) or []:
            _append_recommendation(brief, action)

    return brief


__all__ = ["gather_intelligence_brief"]
