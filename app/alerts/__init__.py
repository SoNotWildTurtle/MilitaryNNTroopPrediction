"""Alert rule management and dispatch helpers."""
from __future__ import annotations

# Legacy module description retained for context.
# Alert rule storage and dispatch utilities.

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from ..config import settings
from ..utils import twilio_alerts, email_alerts

_DEFAULT_PRESETS = [
    {
        "id": "troop-surge",
        "name": "Troop surge",
        "labels": ["troop"],
        "min_confidence": 0.55,
        "description": "Notify when troop movements exceed the confidence threshold.",
    },
    {
        "id": "drone-intercept",
        "name": "Incoming drones",
        "labels": ["drone"],
        "min_confidence": 0.4,
        "description": "Alert air defense teams when drone activity is detected.",
    },
    {
        "id": "armor-patrol",
        "name": "Armour column",
        "labels": ["vehicle"],
        "min_confidence": 0.6,
        "description": "Watch for vehicle convoys indicating armour movements.",
    },
]

AlertRecord = Dict[str, Any]


def _storage_path() -> Path:
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return settings.DATA_DIR / "alert_rules.json"


def _load() -> List[AlertRecord]:
    path = _storage_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return [
                _normalize_rule(rule)
                for rule in data
                if isinstance(rule, dict)
            ]
    except json.JSONDecodeError:
        pass
    return []


def _normalize_rule(rule: AlertRecord) -> AlertRecord:
    labels = rule.get("labels") or []
    if isinstance(labels, str):
        labels = [labels]
    labels = [str(label).strip().lower() for label in labels if str(label).strip()]

    sms = rule.get("sms_recipients") or rule.get("phones") or []
    if isinstance(sms, str):
        sms = sms.split(",")
    sms = [str(num).strip() for num in sms if str(num).strip()]

    emails = rule.get("email_recipients") or rule.get("emails") or []
    if isinstance(emails, str):
        emails = emails.split(",")
    emails = [str(addr).strip() for addr in emails if str(addr).strip()]

    min_conf = rule.get("min_confidence", 0.0)
    try:
        min_conf = float(min_conf)
    except (TypeError, ValueError):
        min_conf = 0.0
    min_conf = max(0.0, min(1.0, min_conf))

    return {
        "id": str(rule.get("id") or uuid.uuid4()),
        "name": str(rule.get("name") or "Alert"),
        "labels": labels,
        "area": str(rule.get("area") or "").strip() or None,
        "min_confidence": min_conf,
        "sms_recipients": sms,
        "email_recipients": emails,
        "active": bool(rule.get("active", True)),
        "created_at": str(rule.get("created_at") or datetime.utcnow().isoformat()),
    }


def _save(rules: Sequence[AlertRecord]) -> None:
    path = _storage_path()
    path.write_text(json.dumps(list(rules), indent=2))


def list_rules() -> List[AlertRecord]:
    rules = _load()
    return sorted(rules, key=lambda item: item.get("created_at", ""))


def _events_path() -> Path:
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return settings.DATA_DIR / "alert_events.json"


def _load_events() -> List[AlertRecord]:
    path = _events_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return [event for event in data if isinstance(event, dict)]
    except json.JSONDecodeError:
        return []
    return []


def _save_events(events: Sequence[AlertRecord]) -> None:
    path = _events_path()
    path.write_text(json.dumps(list(events), indent=2))


def _record_event(rule: AlertRecord, area: str, matches: List[Dict[str, Any]]) -> None:
    events = _load_events()
    summary = {
        "id": str(uuid.uuid4()),
        "rule_id": rule.get("id"),
        "rule_name": rule.get("name"),
        "area": area,
        "timestamp": datetime.utcnow().isoformat(),
        "labels": rule.get("labels", []),
        "match_count": len(matches),
        "channels": {
            "sms": len(rule.get("sms_recipients", [])),
            "email": len(rule.get("email_recipients", [])),
        },
        "matches": [_format_detection(det) for det in matches[:5]],
    }

    events.append(summary)
    # keep the most recent 200 entries to prevent unbounded growth
    events = sorted(events, key=lambda item: item.get("timestamp", ""), reverse=True)[:200]
    _save_events(events)


def list_events(limit: int = 50) -> List[AlertRecord]:
    events = _load_events()
    events = sorted(events, key=lambda item: item.get("timestamp", ""), reverse=True)
    if limit is not None:
        return events[: max(0, limit)]
    return events


def list_presets() -> List[Dict[str, Any]]:
    """Return built-in alert presets for quick configuration."""

    return list(_DEFAULT_PRESETS)


def create_rule(data: Dict[str, Any]) -> AlertRecord:
    rules = _load()
    rule = _normalize_rule({**data, "id": uuid.uuid4(), "created_at": datetime.utcnow().isoformat()})
    rules.append(rule)
    _save(rules)
    return rule


def update_rule(rule_id: str, updates: Dict[str, Any]) -> AlertRecord:
    rules = _load()
    updated = None
    new_rules: List[AlertRecord] = []
    for rule in rules:
        if rule.get("id") == rule_id:
            merged = {**rule, **updates}
            updated = _normalize_rule(merged)
            # keep original creation timestamp
            updated["created_at"] = rule.get("created_at", updated["created_at"])
            new_rules.append(updated)
        else:
            new_rules.append(rule)
    if updated is None:
        raise KeyError(rule_id)
    _save(new_rules)
    return updated


def delete_rule(rule_id: str) -> bool:
    rules = _load()
    new_rules = [rule for rule in rules if rule.get("id") != rule_id]
    if len(new_rules) == len(rules):
        return False
    _save(new_rules)
    return True


def _detection_type(detection: Dict[str, Any]) -> str:
    for key in ("class", "label", "category", "object_type", "target", "type"):
        value = detection.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().lower()
    return "unknown"


def _format_detection(detection: Dict[str, Any]) -> str:
    lat = detection.get("lat") or detection.get("latitude")
    lon = detection.get("lon") or detection.get("longitude")
    confidence = detection.get("confidence")
    parts = []
    dtype = _detection_type(detection)
    if dtype and dtype != "unknown":
        parts.append(dtype.title())
    if isinstance(confidence, (int, float)):
        parts.append(f"confidence {confidence:.2f}")
    if lat is not None and lon is not None:
        parts.append(f"@ ({lat:.3f}, {lon:.3f})")
    return " ".join(parts) if parts else "Detection match"


def evaluate_detections(area: str, detections: Iterable[Dict[str, Any]]) -> List[str]:
    """Check detections against active rules and dispatch alerts."""

    rules = list_rules()
    triggered: List[str] = []
    area_lower = area.lower()
    detections = list(detections)
    if not detections or not rules:
        return triggered

    for rule in rules:
        if not rule.get("active", True):
            continue
        rule_area = rule.get("area")
        if rule_area and rule_area.lower() != area_lower:
            continue
        labels = rule.get("labels") or []
        labels = [label.lower() for label in labels]
        matches = [
            det
            for det in detections
            if (not labels or _detection_type(det) in labels)
            and float(det.get("confidence", 0)) >= float(rule.get("min_confidence", 0))
        ]
        if not matches:
            continue

        triggered.append(rule["id"])
        _record_event(rule, area, matches)
        message_lines = [
            f"Alert: {rule['name']}",
            f"Area: {area}",
            f"Matches: {len(matches)}",
        ]
        for det in matches[:3]:
            message_lines.append(f"- {_format_detection(det)}")
        if len(matches) > 3:
            message_lines.append(f"(+{len(matches) - 3} more)")
        body = "\n".join(message_lines)
        subject = f"Operational alert: {rule['name']}"

        sms_recipients = rule.get("sms_recipients", [])
        if sms_recipients and twilio_alerts.is_configured():
            try:
                twilio_alerts.send_alert(body, sms_recipients)
            except twilio_alerts.TwilioConfigurationError as exc:  # pragma: no cover - optional dependency
                print(f"SMS alert failed: {exc}")
        elif sms_recipients:
            print("SMS alert skipped: Twilio not configured")

        email_recipients = rule.get("email_recipients", [])
        if email_recipients and email_alerts.is_configured():
            try:
                email_alerts.send_alert(subject, body, email_recipients)
            except email_alerts.EmailConfigurationError as exc:  # pragma: no cover - optional dependency
                print(f"Email alert failed: {exc}")
        elif email_recipients:
            print("Email alert skipped: SMTP not configured")

    return triggered


def send_test(rule_id: str) -> AlertRecord:
    """Send a test alert for the specified rule."""

    rules = _load()
    for rule in rules:
        if rule.get("id") == rule_id:
            dummy_detection = {
                "class": (rule.get("labels") or ["activity"])[0],
                "confidence": max(0.75, float(rule.get("min_confidence", 0.5))),
            }
            evaluate_detections(rule.get("area") or "demo", [dummy_detection])
            return rule
    raise KeyError(rule_id)
