"""Tests for the military campaign assessment helper."""

from datetime import datetime, timedelta, UTC
from importlib import util
import sys
from pathlib import Path

_MODULE_PATH = Path(__file__).resolve().parent.parent / "app" / "analysis" / "military_campaign.py"
_SPEC = util.spec_from_file_location("app.analysis.military_campaign", _MODULE_PATH)
military_campaign = util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader  # for mypy/static hints
sys.modules[_SPEC.name] = military_campaign
_SPEC.loader.exec_module(military_campaign)  # type: ignore[attr-defined]

assess_military_campaign = military_campaign.assess_military_campaign


def _det(label: str, *, doctrine: str = "", hours_ago: float = 0.0):
    ts = datetime.now(UTC) - timedelta(hours=hours_ago)
    return {"class_label": label, "timestamp": ts, "doctrine": doctrine}


def _pred(speed: float, confidence: float = 0.7):
    ts = datetime.now(UTC)
    return {"speed_kmh": speed, "confidence": confidence, "timestamp": ts}


def test_campaign_assessment_flags_pressure_and_logistics():
    detections = [
        _det("tank", doctrine="modern", hours_ago=3),
        _det("tank", doctrine="modern", hours_ago=2.5),
        _det("armor", doctrine="modern", hours_ago=2),
        _det("artillery", doctrine="legacy", hours_ago=1.5),
        _det("artillery", doctrine="legacy", hours_ago=1),
        _det("artillery", doctrine="legacy", hours_ago=0.5),
        _det("drone", doctrine="modern", hours_ago=0.2),
        _det("troop", doctrine="modern", hours_ago=0.1),
        _det("logistics", doctrine="modern", hours_ago=0.1),
    ]
    predictions = [_pred(24.0), _pred(21.0, 0.5)]

    result = assess_military_campaign(detections, predictions)

    assert "offensive" in result.front_pressure.lower()
    assert "Rapid" in result.tempo
    assert "logistics" in result.logistics.lower()
    assert any("counter-battery" in rec.lower() for rec in result.recommended_actions)
    assert result.metrics["counts"]["tank"] == 2
    assert result.metrics["doctrine"]["modern"] >= 1


def test_campaign_assessment_handles_sparse_data():
    detections = [_det("troop", hours_ago=1.0)]
    result = assess_military_campaign(detections, [])

    assert "Limited" in result.front_pressure
    assert "Insufficient" in result.tempo
    assert result.recommended_actions  # default action still provided
