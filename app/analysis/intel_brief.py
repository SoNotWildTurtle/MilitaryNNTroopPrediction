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

    return brief


__all__ = ["gather_intelligence_brief"]
