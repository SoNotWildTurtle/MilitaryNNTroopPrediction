"""FastAPI service exposing prediction endpoints and a simple web GUI."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator

from ..alerts import (
    create_rule,
    delete_rule,
    list_events,
    list_presets,
    list_rules,
    send_test,
    update_rule,
)
from ..movement_history import recent_detections, recent_predictions
from ..pipeline import realtime

app = FastAPI(title="Troop Movement Prediction API")

# Serve the static web GUI at /gui
ROOT = Path(__file__).resolve().parents[2]
app.mount("/gui", StaticFiles(directory=ROOT / "web", html=True), name="gui")


class AlertCreatePayload(BaseModel):
    name: str = Field(..., max_length=120)
    labels: List[str] = Field(default_factory=list)
    area: Optional[str] = Field(default=None, max_length=120)
    min_confidence: float = Field(default=0.5, ge=0, le=1)
    sms_recipients: List[str] = Field(default_factory=list)
    email_recipients: List[str] = Field(default_factory=list)
    active: bool = True

    @validator("labels", pre=True)
    def _ensure_labels(cls, value):  # noqa: D401 - simple normaliser
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        return [str(label).strip().lower() for label in value if str(label).strip()]

    @validator("sms_recipients", "email_recipients", pre=True)
    def _ensure_list(cls, value):  # noqa: D401
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]
        return [str(item).strip() for item in value if str(item).strip()]


class AlertUpdatePayload(BaseModel):
    name: Optional[str] = Field(default=None, max_length=120)
    labels: Optional[List[str]] = None
    area: Optional[str] = Field(default=None, max_length=120)
    min_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    sms_recipients: Optional[List[str]] = None
    email_recipients: Optional[List[str]] = None
    active: Optional[bool] = None

    @validator("labels", pre=True)
    def _ensure_labels(cls, value):  # noqa: D401
        if value is None:
            return None
        if isinstance(value, str):
            value = [value]
        return [str(label).strip().lower() for label in value if str(label).strip()]

    @validator("sms_recipients", "email_recipients", pre=True)
    def _ensure_list(cls, value):  # noqa: D401
        if value is None:
            return None
        if isinstance(value, str):
            value = [value]
        return [str(item).strip() for item in value if str(item).strip()]


@app.post("/predict/{area}")
def predict(area: str, model_path: str):
    """Run the real-time pipeline for a given area."""
    realtime.process_area(area, model_path)
    return {"status": "ok"}


@app.get("/detections/{area}")
def detections(area: str, limit: int = 10) -> List[Dict]:
    """Return recent detections for an area."""
    return recent_detections(area, limit)


@app.get("/predictions/{area}")
def predictions(area: str, limit: int = 10) -> List[Dict]:
    """Return recent trajectory predictions for an area."""
    return recent_predictions(area, limit)


@app.get("/alerts")
def get_alerts() -> List[Dict]:
    """Return configured alert rules."""

    return list_rules()


@app.get("/alerts/events")
def get_alert_events(limit: int = 50) -> List[Dict]:
    """Return recent alert trigger events."""

    return list_events(limit=limit)


@app.get("/alerts/presets")
def get_alert_presets() -> List[Dict]:
    """Expose built-in alert presets for quick configuration."""

    return list_presets()


@app.post("/alerts")
def create_alert(payload: AlertCreatePayload) -> Dict:
    """Create a new alert rule."""

    return create_rule(payload.dict())


@app.put("/alerts/{rule_id}")
def update_alert(rule_id: str, payload: AlertUpdatePayload) -> Dict:
    """Update an existing alert rule."""

    try:
        return update_rule(rule_id, payload.dict(exclude_unset=True))
    except KeyError as exc:  # pragma: no cover - runtime path
        raise HTTPException(status_code=404, detail="Alert not found") from exc


@app.delete("/alerts/{rule_id}")
def remove_alert(rule_id: str) -> Dict[str, str]:
    """Delete an alert rule."""

    if not delete_rule(rule_id):
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "deleted"}


@app.post("/alerts/{rule_id}/test")
def test_alert(rule_id: str) -> Dict[str, Any]:
    """Send a test notification for an alert rule."""

    try:
        rule = send_test(rule_id)
    except KeyError as exc:  # pragma: no cover - runtime path
        raise HTTPException(status_code=404, detail="Alert not found") from exc
    return {"status": "sent", "rule": rule}
