"""Tests for the operational tactics analysis helper."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import pathlib
import sys
import types

import app


def _load_module() -> types.ModuleType:
    """Load ``operational_tactics`` without importing heavier analysis deps."""

    analysis_path = pathlib.Path(app.__file__).resolve().parent / "analysis"
    package = types.ModuleType("app.analysis")
    package.__path__ = [str(analysis_path)]
    sys.modules.setdefault("app.analysis", package)

    spec = importlib.util.spec_from_file_location(
        "app.analysis.operational_tactics",
        analysis_path / "operational_tactics.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load operational_tactics module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


assess_operational_tactics = _load_module().assess_operational_tactics


def _ts(hours_ago: float) -> str:
    return (
        datetime(2024, 5, 10, tzinfo=timezone.utc) - timedelta(hours=hours_ago)
    ).isoformat()


def test_offensive_posture_and_logistics_risk() -> None:
    """Combined armour/infantry with limited logistics should flag offensive posture and strained support."""

    detections = [
        {"class": "tank", "confidence": 0.82, "timestamp": _ts(1)},
        {"class": "armor", "confidence": 0.78, "timestamp": _ts(2)},
        {"class": "infantry", "confidence": 0.74, "timestamp": _ts(3)},
        {"class": "troop", "confidence": 0.69, "timestamp": _ts(4)},
        {"class": "drone", "confidence": 0.8, "timestamp": _ts(1.5)},
    ]
    predictions = [
        {"unit_id": "Alpha", "confidence": 0.77, "surety": {"overall": 0.68}},
    ]

    result = assess_operational_tactics(
        "sector-a",
        detections=detections,
        predictions=predictions,
        lookback_hours=12,
    )

    assert result["posture"]["posture"] == "offensive"
    assert any("Combined-arms" in text for text in result["tactic_indicators"])
    assert result["logistics"]["status"] == "strained"
    assert any("interdict" in note.lower() for note in result["logistics"]["notes"])
    pred_summary = result["movement"]["prediction_summary"]
    assert pred_summary["count"] == 1
    assert pred_summary["avg_confidence"] == round(0.77, 3)
    assert any("counter-battery" in rec.lower() for rec in result["recommendations"])


def test_reconnaissance_posture_with_drone_surge() -> None:
    """Drone-heavy detections should trigger a reconnaissance posture and dominant air picture."""

    detections = [
        {"class": "drone", "timestamp": _ts(0.5)},
        {"class": "uav", "timestamp": _ts(1)},
        {"class": "bpla", "timestamp": _ts(1.5)},
        {"class": "aircraft", "timestamp": _ts(2)},
        {"class": "drone", "timestamp": _ts(3)},
        {"class": "drone", "timestamp": _ts(4)},
    ]

    result = assess_operational_tactics(
        "sector-b",
        detections=detections,
        predictions=[],
        lookback_hours=8,
    )

    assert result["posture"]["posture"] == "reconnaissance"
    assert result["air_activity"]["assessment"] == "dominant"
    assert any("emcon" in rec.lower() for rec in result["recommendations"])
    assert any(
        "movement tracks" in rec.lower() for rec in result["recommendations"]
    ), "When no predictions exist, a data collection reminder should be emitted."
