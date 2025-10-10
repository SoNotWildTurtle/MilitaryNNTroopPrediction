"""Tests for the theatre outlook assessment helper."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import pathlib
import sys
import types

import app


def _load_module() -> types.ModuleType:
    """Load ``theater_assessment`` without importing the full analysis package."""

    analysis_path = pathlib.Path(app.__file__).resolve().parent / "analysis"
    package = types.ModuleType("app.analysis")
    package.__path__ = [str(analysis_path)]
    sys.modules.setdefault("app.analysis", package)

    spec = importlib.util.spec_from_file_location(
        "app.analysis.theater_assessment",
        analysis_path / "theater_assessment.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load theater_assessment module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


assess_theater_outlook = _load_module().assess_theater_outlook


def _ts(hours_ago: float) -> str:
    base = datetime(2024, 5, 10, tzinfo=timezone.utc)
    return (base - timedelta(hours=hours_ago)).isoformat()


def test_northern_corridor_flagged_and_axis_highlighted() -> None:
    """Dense northern detections with NE headings should drive risk and recommendations."""

    detections = [
        {"class": "tank", "confidence": 0.74, "timestamp": _ts(1), "lat": 50.72, "lon": 30.5},
        {"class": "infantry", "confidence": 0.71, "timestamp": _ts(2), "lat": 50.69, "lon": 30.5},
        {"class": "drone", "confidence": 0.68, "timestamp": _ts(3), "lat": 50.67, "lon": 30.5},
        {"class": "artillery", "confidence": 0.66, "timestamp": _ts(5), "lat": 50.65, "lon": 30.5},
        {"class": "logistics", "confidence": 0.6, "timestamp": _ts(10), "lat": 50.6, "lon": 30.5},
    ]
    predictions = [
        {"unit_id": "Alpha", "confidence": 0.8, "heading": 40, "timestamp": _ts(0.5)},
        {"unit_id": "Bravo", "confidence": 0.72, "heading": "north-east", "timestamp": _ts(1)},
    ]

    result = assess_theater_outlook(
        "sector-north",
        detections=detections,
        predictions=predictions,
        lookback_hours=24,
    )

    assert result["risk_hotspots"], "Hotspots should be generated from dense detections"
    assert result["risk_hotspots"][0]["corridor"] == "north"
    assert any(
        "north" in rec.lower() for rec in result["recommendations"]
    ), "Recommendations should reference the dominant corridor"
    axes = [axis["axis"] for axis in result["axes_of_advance"]]
    assert "north-east" in axes
    assert result["tempo"]["assessment"] in {"surging", "rising", "steady"}


def test_empty_inputs_return_defaults() -> None:
    """No detections should return graceful defaults and guidance to collect data."""

    result = assess_theater_outlook("empty", detections=[], predictions=[], lookback_hours=24)

    assert result["timeframe"]["total_detections"] == 0
    assert result["corridors"] == []
    assert result["tempo"]["assessment"] == "no-activity"
    assert result["recommendations"]
    assert "insufficient" in result["recommendations"][0].lower()
