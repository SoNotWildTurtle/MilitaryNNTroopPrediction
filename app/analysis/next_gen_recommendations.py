"""Synthesize next-generation operational recommendations from detections.

The helper in this module blends detection statistics and short-term
predictions into a compact set of actionable suggestions.  It is purposely
heuristic so that it can operate on mock or partially populated datasets in
dev/test environments while still offering helpful guidance in production.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Tuple

from ..movement_history import recent_detections, recent_predictions


@dataclass
class _ClassStats:
    """Aggregate simple statistics for a detection class."""

    count: int = 0
    confidences: List[float] = field(default_factory=list)
    last_seen: Optional[datetime] = None

    def update(self, confidence: Optional[float], timestamp: Optional[datetime]) -> None:
        self.count += 1
        if confidence is not None:
            self.confidences.append(confidence)
        if timestamp and (self.last_seen is None or timestamp > self.last_seen):
            self.last_seen = timestamp

    @property
    def avg_confidence(self) -> Optional[float]:
        if not self.confidences:
            return None
        return mean(self.confidences)


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Best-effort conversion of assorted timestamp formats into UTC datetimes."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _safe_float(value: Any) -> Optional[float]:
    """Return a ``float`` for numeric inputs, otherwise ``None``."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _summarize_detections(
    detections: Iterable[MutableMapping[str, Any]]
) -> Dict[str, _ClassStats]:
    """Return class statistics from raw detections."""

    stats: Dict[str, _ClassStats] = {}
    for det in detections:
        label = (
            str(det.get("class") or det.get("label") or det.get("type") or "unknown")
        )
        confidence = _safe_float(det.get("confidence") or det.get("score"))
        timestamp = _parse_timestamp(
            det.get("timestamp")
            or det.get("detected_at")
            or det.get("created_at")
            or det.get("time")
        )
        stats.setdefault(label, _ClassStats()).update(confidence, timestamp)
    return stats


def _format_summary(stats: Dict[str, _ClassStats]) -> Dict[str, Dict[str, Any]]:
    """Convert internal stats into JSON-friendly payloads."""

    formatted: Dict[str, Dict[str, Any]] = {}
    for label, info in stats.items():
        formatted[label] = {
            "count": info.count,
            "avg_confidence": round(info.avg_confidence, 3) if info.avg_confidence else None,
            "last_seen": info.last_seen.isoformat() if info.last_seen else None,
        }
    return formatted


def _recency_score(recency_hours: Optional[float], lookback_hours: int) -> float:
    """Translate freshness into a 0-1 score."""

    if recency_hours is None:
        return 0.0
    if recency_hours <= 1:
        return 1.0
    if recency_hours <= max(2.0, lookback_hours / 4):
        return 0.75
    if recency_hours <= max(4.0, lookback_hours / 2):
        return 0.5
    if recency_hours <= lookback_hours:
        return 0.25
    return 0.0


def _band_for_score(score: float) -> str:
    if score >= 0.75:
        return "critical"
    if score >= 0.5:
        return "elevated"
    if score >= 0.3:
        return "watch"
    return "low"


def _aggregate_predictions(
    predictions: Iterable[MutableMapping[str, Any]]
) -> Dict[str, Tuple[float, float]]:
    """Return average + maximum confidence per predicted label."""

    aggregates: Dict[str, List[float]] = {}
    for pred in predictions:
        label = (
            pred.get("class")
            or pred.get("label")
            or pred.get("type")
            or pred.get("unit_id")
            or pred.get("target")
        )
        confidence = _safe_float(pred.get("confidence"))
        if not label or confidence is None:
            continue
        aggregates.setdefault(str(label).lower(), []).append(confidence)

    return {
        label: (sum(values) / len(values), max(values))
        for label, values in aggregates.items()
        if values
    }


def compile_next_gen_recommendations(
    detections: Sequence[MutableMapping[str, Any]],
    predictions: Optional[Sequence[MutableMapping[str, Any]]] = None,
    *,
    lookback_hours: int = 24,
    priority_threshold: int = 5,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Compile priority, monitoring and data-quality recommendations.

    Parameters
    ----------
    detections:
        Iterable of detection documents that include ``class``/``label`` and
        optional ``confidence`` + timestamp metadata.
    predictions:
        Iterable of prediction dictionaries with optional ``confidence`` and
        ``surety`` payloads.  Missing or partial entries are handled
        gracefully.
    lookback_hours:
        Used to flag stale detection coverage.
    priority_threshold:
        Minimum number of solid detections before a class is escalated to the
        ``priority`` list.  Lower counts still surface in the ``monitor``
        channel.
    now:
        Optional timestamp used for stale-data checks (mainly to aid unit
        testing).  Defaults to ``datetime.now(timezone.utc)``.
    """

    current_time = now or datetime.now(timezone.utc)
    stats = _summarize_detections(detections)
    normalized_labels = {label.lower(): info for label, info in stats.items()}
    prediction_summary = _aggregate_predictions(predictions or [])

    priority: List[str] = []
    monitor: List[str] = []
    data_quality: List[str] = []
    sensor_tasks: List[str] = []
    intel_tasks: List[str] = []
    focus: List[Dict[str, Any]] = []
    risk_matrix_entries: Dict[str, Dict[str, Any]] = {}
    opportunities: List[str] = []

    latest_seen: Optional[datetime] = None
    for label, info in stats.items():
        if info.last_seen and (latest_seen is None or info.last_seen > latest_seen):
            latest_seen = info.last_seen
        avg_conf = info.avg_confidence or 0.0
        recency_hours: Optional[float] = None
        if info.last_seen:
            recency_hours = (current_time - info.last_seen).total_seconds() / 3600
        if info.count >= priority_threshold and avg_conf >= 0.6:
            priority.append(
                f"{label}: {info.count} detections averaging {avg_conf:.0%} confidence; plan immediate verification"
            )
        elif info.count:
            monitor.append(
                f"{label}: {info.count} detections at {avg_conf:.0%} confidence; keep under watch"
            )
        if recency_hours is not None and recency_hours > max(lookback_hours / 2, 3):
            sensor_tasks.append(
                f"{label}: last seen {recency_hours:.1f}h ago; schedule refreshed coverage"
            )
        elif info.count and avg_conf >= 0.6 and info.count < priority_threshold:
            sensor_tasks.append(
                f"{label}: solid confidence but only {info.count} sightings; widen sensor net"
            )
        if info.count and info.avg_confidence is not None and info.avg_confidence < 0.45:
            data_quality.append(
                f"{label}: low average confidence ({info.avg_confidence:.0%}); schedule additional sensor coverage"
            )

        status = "priority" if info.count >= priority_threshold and avg_conf >= 0.6 else (
            "monitor" if info.count else "observed"
        )
        recency_score = _recency_score(recency_hours, lookback_hours)
        pred_avg, pred_peak = prediction_summary.get(label.lower(), (0.0, 0.0))
        count_score = min(1.0, info.count / max(priority_threshold, 1))
        score = (
            0.4 * count_score
            + 0.3 * (info.avg_confidence or 0.0)
            + 0.2 * recency_score
            + 0.1 * max(pred_avg, pred_peak)
        )
        signals: List[str] = [
            f"detections: {info.count}",
            f"avg_conf: {avg_conf:.0%}" if info.avg_confidence is not None else "avg_conf: n/a",
        ]
        if recency_hours is not None:
            signals.append(f"recency: {recency_hours:.1f}h")
        if pred_peak:
            signals.append(f"forecast_peak: {pred_peak:.0%}")
        risk_matrix_entries[label.lower()] = {
            "label": label,
            "score": round(score, 3),
            "band": _band_for_score(score),
            "signals": signals,
        }
        focus.append(
            {
                "label": label,
                "count": info.count,
                "avg_confidence": round(avg_conf, 3) if info.avg_confidence is not None else None,
                "last_seen": info.last_seen.isoformat() if info.last_seen else None,
                "status": status,
                "recency_hours": recency_hours,
            }
        )

        if pred_peak >= 0.7 and (
            info.count < priority_threshold or (info.avg_confidence or 0.0) < 0.65
        ):
            opportunities.append(
                f"{label}: forecasts peaking at {pred_peak:.0%} with limited detections; coordinate cross-sensor confirmation"
            )
        elif info.count >= priority_threshold and recency_score >= 0.75 and avg_conf >= 0.65:
            opportunities.append(
                f"{label}: strong detections with fresh coverage; prepare follow-on exploitation plan"
            )

    if latest_seen is None or current_time - latest_seen > timedelta(hours=lookback_hours):
        data_quality.append(
            "Detections are stale for the requested window; trigger new collection runs"
        )

    for pred in predictions or []:
        conf = _safe_float(pred.get("confidence"))
        surety = pred.get("surety", {}).get("overall") if isinstance(pred.get("surety"), dict) else None
        subject = str(
            pred.get("unit_id")
            or pred.get("class")
            or pred.get("label")
            or pred.get("target")
            or "unit"
        )
        predicted_label = (
            str(
                pred.get("class")
                or pred.get("label")
                or pred.get("type")
                or pred.get("unit_id")
                or pred.get("target")
                or ""
            )
        ).lower()
        destination = pred.get("prediction") or pred.get("forecast") or {}
        dest_str = ""
        if isinstance(destination, dict):
            lat = destination.get("lat") or destination.get("latitude")
            lon = destination.get("lon") or destination.get("longitude")
            if lat is not None and lon is not None:
                dest_str = f" towards {lat},{lon}"
        if conf is not None:
            if conf >= 0.75:
                priority.append(
                    f"{subject}: forecast with {conf:.0%} confidence{dest_str}; stage interception assets"
                )
            elif conf >= 0.5:
                monitor.append(
                    f"{subject}: forecast at {conf:.0%} confidence{dest_str}; monitor for confirmation"
                )
            else:
                data_quality.append(
                    f"{subject}: forecast confidence {conf:.0%} is low; gather more telemetry before acting"
                )
        if predicted_label and predicted_label not in normalized_labels:
            intel_tasks.append(
                f"{subject}: prediction lacks matching detections; deploy sensors to confirm presence"
            )
            display_label = (
                pred.get("class")
                or pred.get("label")
                or pred.get("type")
                or predicted_label
            )
            pred_avg, pred_peak = prediction_summary.get(
                predicted_label, (conf or 0.0, conf or 0.0)
            )
            if predicted_label not in risk_matrix_entries:
                risk_matrix_entries[predicted_label] = {
                    "label": str(display_label),
                    "score": round(max(pred_avg, pred_peak), 3),
                    "band": _band_for_score(max(pred_avg, pred_peak)),
                    "signals": [
                        f"forecasts: {max(pred_avg, pred_peak):.0%}",
                        "detections: 0",
                    ],
                }
            if pred_peak >= 0.65:
                opportunities.append(
                    f"{subject}: high-confidence forecast without detections; align ISR to validate"
                )
        if surety is not None and surety < 0.5:
            data_quality.append(
                f"{subject}: model surety scored at {surety:.0%}; retrain or cross-check alternative predictors"
            )

    focus.sort(key=lambda entry: entry.get("count", 0), reverse=True)
    risk_matrix = sorted(
        risk_matrix_entries.values(), key=lambda entry: entry.get("score", 0), reverse=True
    )
    opportunities = sorted(dict.fromkeys(opportunities))

    return {
        "priority": priority,
        "monitor": monitor,
        "data_quality": data_quality,
        "sensor_tasks": sensor_tasks,
        "intel_tasks": intel_tasks,
        "focus": focus,
        "risk_matrix": risk_matrix,
        "opportunities": opportunities,
        "summary": _format_summary(stats),
        "latest_detection": latest_seen.isoformat() if latest_seen else None,
        "lookback_hours": lookback_hours,
    }


def gather_next_gen_recommendations(
    area: Optional[str],
    *,
    detection_limit: int = 200,
    prediction_limit: int = 50,
    lookback_hours: int = 24,
) -> Dict[str, Any]:
    """Fetch recent records and compile recommendations.

    Database access failures are downgraded into ``data_quality`` messages so the
    CLI and dashboard can still present partial insights.
    """

    detections: Sequence[MutableMapping[str, Any]] = []
    predictions: Sequence[MutableMapping[str, Any]] = []
    data_quality: List[str] = []

    if area:
        try:
            detections = recent_detections(area, limit=detection_limit)
        except Exception as exc:  # pragma: no cover - defensive against DB outages
            data_quality.append(f"Failed to load detections for {area}: {exc}")
        try:
            predictions = recent_predictions(area, limit=prediction_limit)
        except Exception as exc:  # pragma: no cover
            data_quality.append(f"Failed to load predictions for {area}: {exc}")

    compiled = compile_next_gen_recommendations(
        detections,
        predictions,
        lookback_hours=lookback_hours,
    )
    if data_quality:
        compiled["data_quality"].extend(data_quality)
    compiled["area"] = area
    return compiled


__all__ = [
    "compile_next_gen_recommendations",
    "gather_next_gen_recommendations",
]
