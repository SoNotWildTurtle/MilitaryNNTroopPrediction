"""Tests for the next-gen recommendations analysis helper."""

from datetime import datetime, timedelta, timezone
import importlib.util
import pathlib
import sys
import types

import app


def _load_module() -> types.ModuleType:
    """Load ``next_gen_recommendations`` without importing heavy analysis deps."""

    analysis_path = pathlib.Path(app.__file__).resolve().parent / "analysis"
    package = types.ModuleType("app.analysis")
    package.__path__ = [str(analysis_path)]
    sys.modules.setdefault("app.analysis", package)

    spec = importlib.util.spec_from_file_location(
        "app.analysis.next_gen_recommendations",
        analysis_path / "next_gen_recommendations.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load next_gen_recommendations module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


compile_next_gen_recommendations = _load_module().compile_next_gen_recommendations


def _ts(hours_delta: float) -> str:
    base = datetime(2024, 5, 1, tzinfo=timezone.utc)
    return (base - timedelta(hours=hours_delta)).isoformat()


def test_compile_prioritises_high_confidence_classes() -> None:
    """High-confidence classes should appear in the priority list."""

    detections = [
        {"class": "troop", "confidence": 0.82, "timestamp": _ts(1)},
        {"class": "troop", "confidence": 0.79, "timestamp": _ts(1.5)},
        {"class": "troop", "confidence": 0.81, "timestamp": _ts(2)},
        {"class": "troop", "confidence": 0.77, "timestamp": _ts(2.5)},
        {"class": "troop", "confidence": 0.83, "timestamp": _ts(3)},
        {"class": "vehicle", "confidence": 0.32, "timestamp": _ts(2)},
        {"class": "vehicle", "confidence": 0.28, "timestamp": _ts(2.2)},
    ]
    predictions = [
        {
            "unit_id": "Alpha",
            "confidence": 0.8,
            "prediction": {"lat": 50.45, "lon": 30.5},
        },
        {
            "unit_id": "Bravo",
            "confidence": 0.44,
            "surety": {"overall": 0.4},
        },
    ]
    now = datetime(2024, 5, 1, 12, tzinfo=timezone.utc)
    result = compile_next_gen_recommendations(
        detections,
        predictions,
        lookback_hours=6,
        now=now,
        priority_threshold=5,
    )

    assert any("troop" in item.lower() for item in result["priority"])
    assert any("vehicle" in item.lower() for item in result["monitor"])
    assert any("vehicle" in item.lower() for item in result["data_quality"])
    assert any("alpha" in item.lower() for item in result["priority"])
    assert any("bravo" in item.lower() for item in result["data_quality"])
    assert result["focus"][0]["label"] == "troop"
    assert result["summary"]["troop"]["count"] == 5
    assert result["summary"]["vehicle"]["count"] == 2
    assert result["latest_detection"] is not None
    assert result["sensor_tasks"]
    assert result["risk_matrix"]
    assert any(entry["label"].lower() == "troop" for entry in result["risk_matrix"])
    assert result["opportunities"]


def test_compile_flags_stale_detections() -> None:
    """Old detections should trigger a stale-data reminder."""

    old_time = datetime(2024, 4, 20, tzinfo=timezone.utc)
    detections = [
        {"class": "drone", "confidence": 0.9, "timestamp": old_time.isoformat()},
    ]
    now = datetime(2024, 5, 1, tzinfo=timezone.utc)
    result = compile_next_gen_recommendations(
        detections,
        [],
        lookback_hours=24,
        now=now,
    )
    assert any("stale" in item.lower() for item in result["data_quality"])


def test_compile_handles_prediction_only_inputs() -> None:
    """Predictions alone should still produce actionable guidance."""

    predictions = [
        {"unit_id": "Charlie", "confidence": 0.78, "prediction": {"lat": 51.0, "lon": 30.9}},
        {"unit_id": "Delta", "confidence": 0.38},
    ]
    now = datetime(2024, 5, 1, tzinfo=timezone.utc)
    result = compile_next_gen_recommendations(
        [],
        predictions,
        lookback_hours=12,
        now=now,
    )
    assert any("charlie" in item.lower() for item in result["priority"])
    assert any("delta" in item.lower() for item in result["data_quality"])
    assert any(entry["label"].lower() == "charlie" for entry in result["risk_matrix"])


def test_sensor_and_intel_tasks_surface_gaps() -> None:
    """The helper should flag stale coverage and prediction-only targets."""

    detections = [
        {
            "class": "armor",
            "confidence": 0.72,
            "timestamp": _ts(10),
        },
    ]
    predictions = [
        {"class": "drone", "unit_id": "Recon-1", "confidence": 0.76},
    ]
    now = datetime(2024, 5, 1, 12, tzinfo=timezone.utc)
    result = compile_next_gen_recommendations(
        detections,
        predictions,
        lookback_hours=6,
        now=now,
        priority_threshold=3,
    )

    assert any("schedule refreshed" in item.lower() for item in result["sensor_tasks"])
    assert any("deploy sensors" in item.lower() for item in result["intel_tasks"])
