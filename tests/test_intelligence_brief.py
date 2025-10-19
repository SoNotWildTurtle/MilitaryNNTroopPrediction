from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Dict
from unittest import mock

import pytest

from types import ModuleType

try:  # pragma: no cover - exercised conditionally in CI environments
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - exercised when FastAPI missing
    TestClient = None  # type: ignore[assignment]

# Create a lightweight package stub so we can load intel_brief without pulling
# in all optional analysis dependencies (matplotlib, sklearn, etc.).
analysis_dir = Path(__file__).resolve().parents[1] / "app" / "analysis"
analysis_pkg = ModuleType("app.analysis")
analysis_pkg.__path__ = [str(analysis_dir)]  # type: ignore[attr-defined]
sys.modules.setdefault("app.analysis", analysis_pkg)

fake_pymongo = ModuleType("pymongo")
fake_pymongo_errors = ModuleType("pymongo.errors")
fake_pymongo_errors.PyMongoError = Exception
fake_pymongo.errors = fake_pymongo_errors  # type: ignore[attr-defined]
sys.modules.setdefault("pymongo", fake_pymongo)
sys.modules.setdefault("pymongo.errors", fake_pymongo_errors)

fake_tf = ModuleType("tensorflow")


class _KerasModel:
    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - simple stub
        pass

    def __call__(self, inputs, training=False):  # pragma: no cover - simple stub
        return inputs


class _Tensor:
    def __init__(self, value=None) -> None:
        self._value = value or []

    def numpy(self):  # pragma: no cover - simple stub
        return self

    def tolist(self):  # pragma: no cover - simple stub
        return list(self._value)


class _LSTM:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __call__(self, inputs):
        return inputs


class _Dense:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def __call__(self, inputs):
        return inputs


fake_keras_layers = ModuleType("tensorflow.keras.layers")
fake_keras_layers.LSTM = _LSTM
fake_keras_layers.Dense = _Dense


class _KerasModels(ModuleType):
    @staticmethod
    def load_model(path):  # pragma: no cover - simple stub
        return _KerasModel()


fake_keras_models = ModuleType("tensorflow.keras.models")
fake_keras_models.load_model = _KerasModels.load_model  # type: ignore[assignment]

fake_keras = ModuleType("tensorflow.keras")
fake_keras.Model = _KerasModel
fake_keras.layers = fake_keras_layers  # type: ignore[attr-defined]
fake_keras.models = fake_keras_models  # type: ignore[attr-defined]

fake_tf.keras = fake_keras  # type: ignore[attr-defined]
fake_tf.Tensor = _Tensor  # type: ignore[attr-defined]
fake_tf.constant = lambda value, dtype=None: value
fake_tf.expand_dims = lambda value, axis: value

sys.modules.setdefault("tensorflow", fake_tf)
sys.modules.setdefault("tensorflow.keras", fake_keras)
sys.modules.setdefault("tensorflow.keras.layers", fake_keras_layers)
sys.modules.setdefault("tensorflow.keras.models", fake_keras_models)


class _DummyResponse:
    def __init__(self):
        self.content = b""

    def raise_for_status(self) -> None:  # pragma: no cover - simple stub
        return None

    def json(self) -> Dict[str, str]:  # pragma: no cover - simple stub
        return {"access_token": "token"}


fake_requests = ModuleType("requests")
fake_requests.post = lambda *args, **kwargs: _DummyResponse()
fake_requests.get = lambda *args, **kwargs: _DummyResponse()
sys.modules.setdefault("requests", fake_requests)

if "app.detection" in sys.modules:
    setattr(sys.modules["app.detection"], "detect_and_tag", lambda *args, **kwargs: [])
else:
    fake_detection = ModuleType("app.detection")
    fake_detection.__path__ = []  # type: ignore[attr-defined]
    fake_detection.detect_and_tag = lambda *args, **kwargs: []
    sys.modules["app.detection"] = fake_detection

spec = importlib.util.spec_from_file_location(
    "app.analysis.intel_brief", analysis_dir / "intel_brief.py"
)
intel_brief = importlib.util.module_from_spec(spec)
sys.modules["app.analysis.intel_brief"] = intel_brief
assert spec and spec.loader
spec.loader.exec_module(intel_brief)

class DummyCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, count: int):
        self._docs = self._docs[:count]
        return self

    def __iter__(self):
        return iter(self._docs)


class DummyCollection:
    def __init__(self, docs):
        self._docs = list(docs)

    def find(self, _query: Dict[str, Any]):
        return DummyCursor(self._docs)

    def count_documents(self, query: Dict[str, Any], limit: int | None = None) -> int:
        if query == {"timestamp": {"$exists": True}}:
            return 1 if any("timestamp" in doc for doc in self._docs) else 0
        return len(self._docs)


def test_gather_intelligence_brief_with_area_and_clusters(monkeypatch):
    monkeypatch.setattr(
        intel_brief, "_utcnow", lambda: datetime(2024, 1, 1, 2, tzinfo=UTC)
    )

    collection_map = {
        "detections": DummyCollection([
            {"_id": 1, "class": "troop", "timestamp": "2024-01-01T00:00:00"}
        ]),
        "predictions": DummyCollection([
            {"_id": 2, "area": "sector-9", "timestamp": "2024-01-01T01:00:00"}
        ]),
        "movement_clusters": DummyCollection([
            {
                "center": (30.5, 50.4),
                "count": 12,
                "avg_speed": 40,
                "timestamp": "2024-01-01T01:30:00",
            }
        ]),
    }

    def fake_get_collection(name: str):
        return collection_map[name]

    monkeypatch.setattr(intel_brief, "get_collection", fake_get_collection)
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {"detections": {"troop": {"count": 4, "avg_conf": 0.9}}})
    monkeypatch.setattr(
        intel_brief,
        "score_clusters",
        lambda clusters: [
            {
                **clusters[0],
                "threat_score": 12.5,
                "threat_level": "high",
                "nearest_site": "airport",
            }
        ],
    )

    captured_detections = {}
    captured_predictions = {}

    def fake_recent_detections(area: str, limit: int):
        captured_detections["area"] = area
        captured_detections["limit"] = limit
        return [
            {
                "_id": "det",
                "area": area,
                "timestamp": "2024-01-01T01:45:00Z",
            }
        ]

    def fake_recent_predictions(area: str, limit: int):
        captured_predictions["area"] = area
        captured_predictions["limit"] = limit
        return [
            {
                "_id": "pred",
                "area": area,
                "timestamp": "2024-01-01T01:50:00Z",
            }
        ]

    monkeypatch.setattr(intel_brief, "recent_detections", fake_recent_detections)
    monkeypatch.setattr(intel_brief, "recent_predictions", fake_recent_predictions)

    brief = intel_brief.gather_intelligence_brief(area="  sector-9  ", hours=6, activity_limit=5)

    assert brief["area"] == "sector-9"
    assert captured_detections == {"area": "sector-9", "limit": 5}
    assert captured_predictions == {"area": "sector-9", "limit": 5}
    assert brief["cluster_threats"][0]["threat_level"] == "high"
    assert any("Escalate monitoring" in rec for rec in brief.get("recommendations", []))
    assert "data_freshness" in brief
    health = brief.get("health")
    assert health is not None
    assert health["risk_level"] in {"elevated", "high", "severe"}
    assert health["confidence"] == "high"
    assert any("threat" in driver.lower() for driver in health.get("drivers", []))
    posture = brief.get("operational_posture")
    assert posture is not None
    assert posture["status"] in {"reinforce", "stabilise", "recover", "monitor"}
    assert isinstance(posture.get("focus"), str) and posture["focus"]
    assert "operational_posture" in brief.get("insights", {})
    readiness = brief.get("response_readiness")
    assert readiness is not None
    assert readiness["level"] in {"steady", "strained", "critical"}
    assert readiness.get("recommended_staffing", 0) >= 2
    assert "response_readiness" in brief.get("insights", {})
    assert any("watch rotations" in rec for rec in brief.get("recommendations", []))
    pressure = brief.get("response_pressure")
    assert pressure is not None
    assert pressure.get("status") in {
        "balanced",
        "backlog",
        "critical_backlog",
        "prediction_gap",
        "prediction_gap_watch",
        "quality_watch",
        "feedback_strain",
    }
    gaps = brief.get("intelligence_gaps")
    assert gaps is not None
    assert any(gap.get("gap") == "feedback_accuracy" for gap in gaps)

    support = brief.get("support_priorities")
    assert support is not None
    assert support.get("status") in {"monitor", "reinforce", "mobilise"}

    confidence = brief.get("intelligence_confidence")
    assert confidence is not None
    assert confidence.get("level") in {"high", "guarded", "low"}
    assert "intelligence_confidence" in brief.get("insights", {})

    outlook = brief.get("operational_outlook")
    assert outlook is not None
    assert outlook.get("status") in {
        "steady_watch",
        "stabilise",
        "heightened_watch",
        "rapid_response",
        "escalation_imminent",
    }
    assert outlook.get("severity_score") is not None
    assert "operational_outlook" in brief.get("insights", {})


@pytest.mark.parametrize(
    "params",
    [
        {"hours": 0, "activity_limit": 10},
        {"hours": 6, "activity_limit": 0},
    ],
)
def test_gather_intelligence_brief_validates_inputs(params):
    with pytest.raises(ValueError):
        intel_brief.gather_intelligence_brief(**params)


def test_gather_intelligence_brief_activity_summary(monkeypatch):
    monkeypatch.setattr(
        intel_brief, "_utcnow", lambda: datetime(2024, 1, 1, 1, tzinfo=UTC)
    )

    detections = [
        {"_id": idx, "timestamp": "2024-01-01T00:00:00", "class": "troop"}
        for idx in range(8)
    ]
    predictions = [
        {"_id": idx, "timestamp": "2024-01-01T00:30:00", "class": "troop"}
        for idx in range(2)
    ]

    def fake_recent_documents(name: str, **_kwargs):
        return detections if name == "detections" else predictions

    monkeypatch.setattr(intel_brief, "_recent_documents", fake_recent_documents)
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    brief = intel_brief.gather_intelligence_brief(hours=4, activity_limit=10)

    summary = brief.get("activity_summary")
    assert summary is not None
    assert summary["detections"] == 8
    assert summary["predictions"] == 2
    assert summary["tempo"] == "surge"
    assert summary["prediction_coverage"] == pytest.approx(0.25, rel=1e-3)
    assert "operational_tempo" in brief.get("insights", {})
    assert any("below 50%" in rec for rec in brief.get("recommendations", []))
    health = brief.get("health")
    assert health is not None
    assert health["risk_level"] == "high"
    assert "Coordinate immediate response" in " ".join(brief["recommendations"])
    assert "Coordinate immediate response" in " ".join(health.get("recommended_actions", []))
    assert health["confidence"] == "moderate"
    assert brief["data_freshness"]["feeds"]["detections"]["status"] == "fresh"
    posture = brief.get("operational_posture")
    assert posture is not None
    assert posture["status"] == "stabilise"
    assert posture["horizon_hours"] == pytest.approx(4.0)
    assert any("tempo" in driver.lower() for driver in posture.get("drivers", []))
    readiness = brief.get("response_readiness")
    assert readiness is not None
    assert readiness["level"] == "critical"
    assert readiness["recommended_staffing"] >= 6
    assert readiness["support_window_hours"] == pytest.approx(2.0)
    assert any("rapid response" in action.lower() for action in readiness.get("priority_actions", []))
    pressure = brief.get("response_pressure")
    assert pressure is not None
    assert pressure.get("status") in {
        "critical_backlog",
        "prediction_gap",
        "backlog",
        "feedback_strain",
        "quality_watch",
    }
    gaps = brief.get("intelligence_gaps")
    assert gaps is not None
    coverage_gap = next((gap for gap in gaps if gap.get("gap") == "prediction_coverage"), None)
    assert coverage_gap is not None
    assert coverage_gap.get("severity") == "critical"
    assert any(
        "inference" in action.lower()
        for action in [coverage_gap.get("recommended_action", "")] + brief.get("recommendations", [])
    )

    support = brief.get("support_priorities")
    assert support is not None
    assert support.get("status") in {"reinforce", "mobilise"}
    assert any(
        entry.get("team") == "Model Operations"
        for entry in support.get("priorities", [])
    )

    outlook = brief.get("operational_outlook")
    assert outlook is not None
    assert outlook.get("status") in {"rapid_response", "escalation_imminent", "heightened_watch"}
    assert outlook.get("severity_score", 0) >= 5
    assert any("tempo" in driver.lower() for driver in outlook.get("drivers", []))


def test_gather_intelligence_brief_marks_stale_feeds(monkeypatch):
    now = datetime(2024, 5, 1, 12, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)

    old = now - timedelta(hours=6)
    stale_record = {"timestamp": old.isoformat().replace("+00:00", "Z")}

    monkeypatch.setattr(
        intel_brief,
        "_recent_documents",
        lambda name, **kwargs: [stale_record] if name == "detections" else [],
    )
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    brief = intel_brief.gather_intelligence_brief(hours=2, activity_limit=5)

    freshness = brief["data_freshness"]["feeds"]
    assert freshness["detections"]["status"] == "stale"
    assert any("stale" in rec for rec in brief.get("recommendations", []))
    health = brief.get("health")
    assert health is not None
    assert health["confidence"] == "low"
    # Ensure duplicate recommendations are not introduced when health actions repeat existing advice
    recs = brief.get("recommendations", [])
    assert len(recs) == len(set(recs))
    posture = brief.get("operational_posture")
    assert posture is not None
    assert posture["status"] == "recover"
    assert any("stale feeds" in driver.lower() for driver in posture.get("drivers", []))
    assert any("telemetry" in rec.lower() for rec in recs)
    readiness = brief.get("response_readiness")
    assert readiness is not None
    assert readiness["level"] == "critical"
    outlook = brief.get("operational_outlook")
    assert outlook is not None
    assert outlook.get("status") in {"stabilise", "rapid_response", "escalation_imminent"}
    assert any("telemetry" in driver.lower() for driver in outlook.get("drivers", []))
    assert readiness["support_window_hours"] == pytest.approx(1.0)
    assert any(
        "restore" in action.lower() for action in readiness.get("priority_actions", [])
    )
    gaps = brief.get("intelligence_gaps")
    assert gaps is not None
    stale_gap = next((gap for gap in gaps if gap.get("gap") == "detections_freshness"), None)
    assert stale_gap is not None
    assert stale_gap.get("severity") == "critical"

    support = brief.get("support_priorities")
    assert support is not None
    assert any(
        entry.get("team") == "Telemetry Operations"
        for entry in support.get("priorities", [])
    )


def test_intelligence_confidence_penalises_degraded_signals():
    brief = {
        "meta": {"feedback_accuracy": 0.48},
        "detection_quality": {
            "weighted_avg_confidence": 0.52,
            "active_class_ratio": 0.35,
        },
        "data_freshness": {
            "feeds": {
                "detections": {"status": "stale", "age_minutes": 210.0},
                "predictions": {"status": "warning", "age_minutes": 95.0},
            }
        },
        "intelligence_gaps": [
            {"gap": "prediction_coverage", "severity": "critical"},
            {"gap": "feedback_accuracy", "severity": "major"},
        ],
        "health": {"risk_level": "high", "confidence": "low"},
    }

    confidence = intel_brief._derive_intelligence_confidence(brief)
    assert confidence is not None
    assert confidence.get("level") == "low"
    assert confidence.get("status") == "recover"
    assert isinstance(confidence.get("score"), float)
    assert confidence["score"] < 60

    components = confidence.get("components")
    assert components is not None
    assert components.get("gap_summary") == {"critical": 1, "major": 1}
    telemetry = components.get("telemetry")
    assert telemetry is not None
    assert set(telemetry.get("stale_feeds", [])) == {"detections"}
    assert set(telemetry.get("warning_feeds", [])) == {"predictions"}

    drivers = " ".join(confidence.get("drivers", []))
    assert "stale" in drivers.lower()
    assert "feedback accuracy" in drivers.lower()

    actions = " ".join(confidence.get("recommended_actions", []))
    assert "telemetry" in actions.lower()
    assert "calibration" in actions.lower()


def test_response_readiness_handles_feedback_and_cluster_load(monkeypatch):
    now = datetime(2024, 3, 20, 9, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)

    fresh_record = {"timestamp": now.isoformat().replace("+00:00", "Z")}

    monkeypatch.setattr(
        intel_brief,
        "_recent_documents",
        lambda name, **kwargs: [fresh_record] if name == "detections" else [fresh_record],
    )
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        intel_brief,
        "meta_analysis",
        lambda hours: {
            "detections": {"troop": {"count": 2, "avg_conf": 0.82}},
            "feedback_accuracy": 0.55,
            "cluster_count": 32,
        },
    )

    brief = intel_brief.gather_intelligence_brief(hours=3, activity_limit=5)

    readiness = brief.get("response_readiness")
    assert readiness is not None
    assert readiness["level"] == "critical"
    assert readiness["recommended_staffing"] == 6
    assert readiness["support_window_hours"] == pytest.approx(2.0)
    actions = readiness.get("priority_actions", [])
    assert any("calibration" in action.lower() for action in actions)
    assert any("rapid response" in action.lower() for action in actions)
    recs = brief.get("recommendations", [])
    assert any("calibration" in rec.lower() for rec in recs)
    assert len(recs) == len(set(recs))
    pressure = brief.get("response_pressure")
    assert pressure is not None
    assert pressure.get("severity") >= 1
    gaps = brief.get("intelligence_gaps")
    assert gaps is not None
    accuracy_gap = next((gap for gap in gaps if gap.get("gap") == "feedback_accuracy"), None)
    assert accuracy_gap is not None
    assert accuracy_gap.get("severity") == "critical"
    cluster_gap = next((gap for gap in gaps if gap.get("gap") == "cluster_scoring"), None)
    assert cluster_gap is not None


def test_operational_outlook_flags_escalation():
    brief: Dict[str, Any] = {
        "activity_summary": {"tempo": "surge", "prediction_coverage": 0.3},
        "response_readiness": {"level": "critical", "support_window_hours": 2.0},
        "operational_posture": {"status": "recover", "horizon_hours": 3.5},
        "response_pressure": {
            "status": "critical_backlog",
            "pending_predictions": 24,
            "unmatched_detections": 12,
            "estimated_clearance_hours": 6.0,
        },
        "data_freshness": {
            "feeds": {
                "detections": {"status": "stale"},
                "predictions": {"status": "warning"},
            },
            "worst_case_minutes": 180.0,
        },
        "detection_quality": {
            "weighted_avg_confidence": 0.5,
            "sparse_class_coverage": ["armor"],
        },
        "health": {"risk_level": "severe"},
        "support_priorities": {"status": "mobilise"},
        "intelligence_confidence": {"level": "low"},
        "intelligence_gaps": [
            {"gap": "prediction_coverage", "severity": "critical"}
        ],
        "cluster_threats": [
            {"threat_level": "critical", "threat_score": 18.2, "nearest_site": "rail hub"}
        ],
    }

    outlook = intel_brief._derive_operational_outlook(brief)
    assert outlook is not None
    assert outlook.get("status") in {"escalation_imminent", "rapid_response"}
    assert outlook.get("severity_score", 0) >= 12
    assert outlook.get("planning_horizon_hours") is not None
    focus = outlook.get("focus_areas", [])
    assert "Telemetry recovery" in focus
    assert "Analyst throughput" in focus
    drivers = " ".join(outlook.get("drivers", []))
    assert "backlog" in drivers.lower() or "triage" in drivers.lower()
    actions = " ".join(outlook.get("recommended_actions", []))
    assert "leadership" in actions.lower() or "rapid response" in actions.lower()


def test_detection_quality_highlights_low_confidence(monkeypatch):
    now = datetime(2024, 7, 10, 6, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)

    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])

    meta_payload = {
        "detections": {
            "troop": {"count": 3, "avg_conf": 0.6},
            "armor": {"count": 3, "avg_conf": 0.5},
            "drone": {"count": 1, "avg_conf": 0.4},
            "naval": {"count": 0, "avg_conf": 0.9},
        },
        "feedback_accuracy": 0.9,
        "cluster_count": 0,
    }
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: meta_payload)

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    quality = brief.get("detection_quality")
    assert quality is not None
    assert quality.get("total_detections") == 7
    assert quality.get("active_classes") == 3
    assert quality.get("weighted_avg_confidence") == pytest.approx(0.529, rel=1e-3)
    assert set(quality.get("low_confidence_classes", [])) == {"armor", "drone"}
    assert set(quality.get("sparse_class_coverage", [])) >= {"drone", "naval"}

    insights = brief.get("insights", {})
    assert "detection_quality" in insights
    assert insights["detection_quality"].get("weighted_avg_confidence") == pytest.approx(
        0.529, rel=1e-3
    )

    recs = brief.get("recommendations", [])
    assert any("Low detection confidence flagged" in rec for rec in recs)
    assert any("Detection coverage is sparse" in rec for rec in recs)
    assert any("Average detection confidence is degrading" in rec for rec in recs)


def test_response_pressure_flags_prediction_backlog(monkeypatch):
    now = datetime(2024, 8, 1, 12, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)

    def fake_recent_documents(name: str, **_kwargs):
        doc = {"timestamp": now.isoformat().replace("+00:00", "Z")}
        if name == "detections":
            return [doc for _ in range(2)]
        return [doc for _ in range(8)]

    monkeypatch.setattr(intel_brief, "_recent_documents", fake_recent_documents)
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        intel_brief,
        "meta_analysis",
        lambda hours: {
            "detections": {"troop": {"count": 10, "avg_conf": 0.82}},
            "feedback_accuracy": 0.8,
            "cluster_count": 4,
        },
    )

    brief = intel_brief.gather_intelligence_brief(hours=4, activity_limit=10)

    pressure = brief.get("response_pressure")
    assert pressure is not None
    assert pressure.get("status") == "critical_backlog"
    assert pressure.get("pending_predictions", 0) >= 6
    clearance = pressure.get("estimated_clearance_hours")
    assert isinstance(clearance, (float, int)) and clearance >= 6.0
    actions = pressure.get("recommended_actions", [])
    assert any("prediction queue" in action.lower() or "triage" in action.lower() for action in actions)
    recs = brief.get("recommendations", [])
    assert any("prediction queue" in rec.lower() or "triage" in rec.lower() for rec in recs)


def test_response_pressure_highlights_prediction_gap(monkeypatch):
    now = datetime(2024, 8, 2, 9, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)

    def fake_recent_documents(name: str, **_kwargs):
        doc = {"timestamp": now.isoformat().replace("+00:00", "Z")}
        if name == "detections":
            return [doc for _ in range(6)]
        return []

    monkeypatch.setattr(intel_brief, "_recent_documents", fake_recent_documents)
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        intel_brief,
        "meta_analysis",
        lambda hours: {
            "detections": {
                "troop": {"count": 6, "avg_conf": 0.55},
                "armor": {"count": 2, "avg_conf": 0.5},
            },
            "feedback_accuracy": 0.58,
            "cluster_count": 2,
        },
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=10)

    pressure = brief.get("response_pressure")
    assert pressure is not None
    assert pressure.get("status") == "prediction_gap"
    assert pressure.get("unmatched_detections", 0) >= 6
    drivers = pressure.get("drivers", [])
    assert any("modelling" in driver.lower() for driver in drivers)
    actions = pressure.get("recommended_actions", [])
    assert any("regenerate" in action.lower() or "audit" in action.lower() for action in actions)
    recs = brief.get("recommendations", [])
    assert any("prediction" in rec.lower() for rec in recs)


def test_support_priorities_mobilise_cross_functional_teams():
    brief = {
        "response_readiness": {"level": "critical", "support_window_hours": 2.5},
        "operational_posture": {"status": "recover"},
        "response_pressure": {
            "status": "critical_backlog",
            "pending_predictions": 12,
            "unmatched_detections": 5,
            "estimated_clearance_hours": 6.0,
        },
        "data_freshness": {
            "feeds": {"predictions": {"status": "stale", "age_minutes": 240.0}}
        },
        "detection_quality": {
            "weighted_avg_confidence": 0.55,
            "low_confidence_classes": ["troop"],
        },
        "intelligence_gaps": [
            {
                "gap": "feedback_accuracy",
                "severity": "critical",
                "detail": "Feedback accuracy is below 60%.",
                "recommended_action": "Schedule immediate analyst calibration.",
            }
        ],
        "health": {"risk_level": "high"},
    }

    support = intel_brief._derive_support_priorities(brief)
    assert support is not None
    assert support.get("status") == "mobilise"
    teams = set(support.get("teams", []))
    assert {"Command Liaison", "Telemetry Operations", "Analysis Cell", "Model Operations"}.issubset(teams)
    actions = " ".join(support.get("recommended_actions", []))
    assert "telemetry" in actions.lower()
    assert "analyst" in actions.lower()


@pytest.mark.skipif(TestClient is None, reason="FastAPI is not installed")
def test_intelligence_brief_endpoint(monkeypatch):
    from app.api.main import app

    client = TestClient(app)
    mock_brief = {"generated_at": "2024-01-01T00:00:00Z"}
    with mock.patch("app.api.main.gather_intelligence_brief", return_value=mock_brief) as patched:
        response = client.get("/intel/brief", params={"area": "alpha", "hours": 24, "limit": 15})
    assert response.status_code == 200
    assert response.json() == mock_brief
    patched.assert_called_once_with(area="alpha", hours=24, activity_limit=15)
@pytest.mark.skipif(TestClient is None, reason="FastAPI is not installed")
def test_intelligence_brief_endpoint_propagates_errors(monkeypatch):
    from app.api.main import app

    client = TestClient(app)
    with mock.patch(
        "app.api.main.gather_intelligence_brief", side_effect=ValueError("invalid window")
    ):
        response = client.get("/intel/brief", params={"hours": 24, "limit": 20})
    assert response.status_code == 400
    assert response.json()["detail"] == "invalid window"
