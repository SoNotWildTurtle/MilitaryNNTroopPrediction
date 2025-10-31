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

    directives = brief.get("command_directives")
    assert directives is not None
    assert directives.get("status") in {"monitor", "focus", "accelerate", "escalate"}
    assert isinstance(directives.get("directives", []), list)
    assert "command_directives" in brief.get("insights", {})

    assurance = brief.get("mission_assurance")
    assert assurance is not None
    assert assurance.get("status") in {"assured", "watch", "at_risk", "critical"}
    assert isinstance(assurance.get("assurance_score"), int)
    assert "mission_assurance" in brief.get("insights", {})
    if assurance.get("recommended_actions"):
        assert any(
            action in brief.get("recommendations", []) for action in assurance["recommended_actions"]
        )

    resilience = brief.get("operational_resilience")
    assert resilience is not None
    assert resilience.get("status") in {"resilient", "steady", "vulnerable", "critical"}
    assert isinstance(resilience.get("resilience_score"), int)
    assert "operational_resilience" in brief.get("insights", {})
    if resilience.get("recommended_actions"):
        assert any(
            action in brief.get("recommendations", [])
            for action in resilience.get("recommended_actions", [])
        )

    continuity = brief.get("operational_continuity")
    assert continuity is not None
    assert continuity.get("status") in {"sustained", "watch", "strained", "critical"}
    assert isinstance(continuity.get("continuity_score"), int)
    assert "operational_continuity" in brief.get("insights", {})
    if continuity.get("recommended_actions"):
        assert any(
            action in brief.get("recommendations", [])
            for action in continuity.get("recommended_actions", [])
        )

    escalation = brief.get("escalation_readiness")
    assert escalation is not None
    assert escalation.get("status") in {"standby", "monitor", "prepare", "escalate"}
    assert isinstance(escalation.get("readiness_score"), int)
    assert "escalation_readiness" in brief.get("insights", {})
    pathways = escalation.get("escalation_pathways")
    if pathways:
        assert isinstance(pathways, list)
    if escalation.get("recommended_actions"):
        assert any(
            action in brief.get("recommendations", [])
            for action in escalation.get("recommended_actions", [])
        )


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

    directives = brief.get("command_directives")
    assert directives is not None
    assert directives.get("status") in {"focus", "accelerate", "escalate"}
    counts = directives.get("directive_counts", {})
    assert counts.get("immediate", 0) >= 1
    assert any(
        "rapid response" in entry.get("action", "").lower()
        or "prediction" in entry.get("action", "").lower()
        for entry in directives.get("directives", [])
    )

    alignment = brief.get("command_alignment")
    assert alignment is not None
    assert alignment.get("status") in {"aligned", "watch", "at_risk", "misaligned"}
    assert isinstance(alignment.get("alignment_score"), int)
    assert alignment["alignment_score"] <= 100
    assert "command_alignment" in brief.get("insights", {})
    if alignment.get("coordination_gaps"):
        insight = brief["insights"]["command_alignment"]
        assert insight.get("coordination_gaps") == len(alignment["coordination_gaps"])


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


def test_command_directives_prioritise_immediate_actions():
    brief: Dict[str, Any] = {
        "operational_outlook": {
            "status": "rapid_response",
            "severity_score": 9,
            "focus_areas": ["Telemetry recovery", "Analyst throughput"],
            "planning_horizon_hours": 2.5,
            "recommended_actions": [
                "Maintain a rapid response posture and pre-stage reinforcement assets for the next few hours."
            ],
        },
        "operational_posture": {
            "status": "recover",
            "focus": "Restore telemetry coverage for stale feeds to regain confidence.",
            "horizon_hours": 3.0,
        },
        "response_readiness": {
            "level": "critical",
            "support_window_hours": 2.0,
            "priority_actions": ["Stage rapid response teams and leadership liaisons."],
        },
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 4.0,
            "recommended_actions": ["Deploy surge analysts to clear the prediction backlog."],
        },
        "support_priorities": {
            "status": "mobilise",
            "priorities": [
                {
                    "team": "Telemetry Operations",
                    "urgency": "immediate",
                    "reason": "Telemetry feed is stale and requires recovery support.",
                    "support_window_hours": 1.0,
                },
                {
                    "team": "Analysis Cell",
                    "urgency": "next_shift",
                    "reason": "Analyst backlog is forming as predictions outpace detections.",
                },
            ],
            "teams": ["Telemetry Operations", "Analysis Cell"],
            "recommended_actions": [
                "Notify command staff and mobilise reserve teams to restore readiness.",
            ],
        },
        "intelligence_confidence": {
            "level": "low",
            "recommended_actions": [
                "Launch a telemetry validation sprint to rebuild intelligence confidence."
            ],
        },
        "intelligence_gaps": [
            {
                "gap": "predictions_freshness",
                "severity": "critical",
                "detail": "Predictions feed is stale.",
                "recommended_action": "Restore predictions feed immediately.",
            },
            {
                "gap": "feedback_accuracy",
                "severity": "major",
                "detail": "Feedback accuracy is trending down.",
                "recommended_action": "Schedule analyst calibration block.",
            },
        ],
        "health": {
            "risk_level": "high",
            "recommended_actions": ["Coordinate immediate response options with the duty officer."],
        },
        "recommendations": [
            "Notify command staff and mobilise reserve teams to restore readiness.",
            "Deploy surge analysts to clear the prediction backlog.",
        ],
    }

    directives = intel_brief._derive_command_directives(brief)
    assert directives is not None
    assert directives.get("status") in {"accelerate", "escalate"}
    assert directives.get("planning_window_hours") == pytest.approx(1.0, rel=1e-3)
    immediate = [entry for entry in directives.get("directives", []) if entry.get("priority") == "immediate"]
    assert immediate
    assert any("telemetry" in entry.get("action", "").lower() for entry in immediate)
    counts = directives.get("directive_counts", {})
    assert counts.get("immediate", 0) >= len(immediate)
    teams = directives.get("coordination_teams", [])
    assert "Telemetry Operations" in teams and "Analysis Cell" in teams


def test_communication_plan_escalates_for_crisis():
    brief: Dict[str, Any] = {
        "command_directives": {
            "severity": 24,
            "status": "escalate",
            "drivers": ["Multiple crisis directives require leadership steering."],
            "focus_areas": ["Telemetry recovery", "Backlog relief"],
            "planning_window_hours": 1.5,
        },
        "operational_posture": {"status": "recover"},
        "response_readiness": {"level": "critical"},
        "response_pressure": {"severity": 2, "status": "critical_backlog"},
        "support_priorities": {"status": "mobilise"},
        "intelligence_confidence": {"level": "low"},
        "health": {"risk_level": "severe"},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "stale"},
                "predictions": {"status": "warning"},
            }
        },
        "intelligence_gaps": [{"severity": "critical"}],
        "cluster_threats": [
            {
                "threat_level": "critical",
                "threat_score": 18.5,
                "nearest_site": "rail hub",
            }
        ],
        "recommendations": ["Notify command staff immediately."],
        "errors": ["Threat scoring experienced a brief outage."],
    }

    plan = intel_brief._derive_communication_plan(brief)
    assert plan is not None
    assert plan.get("status") == "escalated"
    cadence = plan.get("update_cadence_minutes")
    assert isinstance(cadence, int) and cadence <= 45
    audiences = plan.get("audiences", [])
    assert any(entry.get("audience") == "Command Leadership" for entry in audiences)
    assert any("telemetry" in message.lower() for message in plan.get("key_messages", []))
    assert any("situation report" in action.lower() for action in plan.get("recommended_actions", []))


def test_contingency_plans_escalate_for_crisis_signals():
    brief: Dict[str, Any] = {
        "operational_outlook": {
            "status": "escalation_imminent",
            "severity_score": 22,
            "drivers": ["Tempo surge", "Backlog severity"],
        },
        "command_directives": {
            "status": "escalate",
            "severity": 18,
            "coordination_teams": ["Command Liaison", "Telemetry Operations"],
        },
        "operational_posture": {"status": "recover"},
        "response_readiness": {"level": "critical", "support_window_hours": 1.5},
        "response_pressure": {
            "status": "critical_backlog",
            "severity": 3,
            "estimated_clearance_hours": 2.0,
        },
        "support_priorities": {"status": "mobilise", "teams": ["Incident Management"]},
        "intelligence_confidence": {"level": "low"},
        "health": {"risk_level": "severe"},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "stale", "age_minutes": 90},
                "predictions": {"status": "warning", "age_minutes": 45},
            }
        },
        "intelligence_gaps": [
            {
                "gap": "prediction_coverage",
                "severity": "critical",
                "detail": "Prediction coverage is below 40%.",
                "recommended_action": "Restore inference pipeline throughput immediately.",
            }
        ],
        "detection_quality": {"weighted_avg_confidence": 0.45},
        "communication_plan": {"status": "crisis", "update_cadence_minutes": 30},
    }

    plans = intel_brief._derive_contingency_plans(brief)
    assert plans is not None
    assert plans.get("status") == "activate"
    assert plans.get("severity") >= 20
    scenarios = plans.get("scenarios", [])
    assert any("Escalation" in scenario.get("name", "") for scenario in scenarios)
    assert any("Command Liaison" in scenario.get("owners", []) for scenario in scenarios)
    assert any(
        "restore inference" in action.lower()
        for action in plans.get("recommended_actions", []) or []
    )
    assert plans.get("watch_items")


def test_resource_sustainment_surges_for_multifaceted_strain():
    brief: Dict[str, Any] = {
        "response_readiness": {
            "level": "critical",
            "support_window_hours": 2.0,
            "recommended_staffing": 6,
        },
        "response_pressure": {
            "status": "critical_backlog",
            "pending_predictions": 14,
            "unmatched_detections": 9,
            "estimated_clearance_hours": 5.0,
        },
        "support_priorities": {
            "status": "mobilise",
            "priorities": [
                {
                    "team": "Telemetry Operations",
                    "urgency": "immediate",
                    "reason": "Predictions feed is stale",
                    "support_window_hours": 1.5,
                }
            ],
        },
        "data_freshness": {
            "feeds": {
                "predictions": {"status": "stale", "age_minutes": 180.0}
            }
        },
        "intelligence_gaps": [
            {
                "gap": "prediction_coverage",
                "severity": "critical",
                "detail": "Prediction coverage is critically low.",
                "recommended_action": "Restore inference throughput immediately.",
            }
        ],
        "operational_outlook": {
            "status": "rapid_response",
            "severity_score": 18,
            "planning_horizon_hours": 4.0,
        },
        "command_directives": {
            "severity": 15,
            "planning_window_hours": 3.0,
        },
        "contingency_plans": {"status": "activate"},
        "communication_plan": {"status": "escalated", "update_cadence_minutes": 45},
        "health": {"risk_level": "severe"},
        "detection_quality": {"weighted_avg_confidence": 0.5},
        "meta": {"feedback_accuracy": 0.55},
        "activity_summary": {"tempo": "surge"},
    }

    sustainment = intel_brief._derive_resource_sustainment(brief)
    assert sustainment is not None
    assert sustainment.get("status") in {"surge", "accelerate"}
    assert sustainment.get("severity", 0) >= 18

    needs = sustainment.get("resource_needs", [])
    assert {"Surge analyst coverage", "Backlog triage cell", "predictions telemetry recovery"}.issubset(
        set(needs)
    )

    actions = " ".join(sustainment.get("recommended_actions", []))
    assert "surge analysts" in actions.lower()
    assert "telemetry" in actions.lower()

    allocation = sustainment.get("allocation_plan", [])
    assert any(entry.get("resource") == "Analyst surge team" for entry in allocation)
    assert any(entry.get("resource") == "Telemetry engineering" for entry in allocation)

    window = sustainment.get("resupply_window_hours")
    assert isinstance(window, (float, int)) and window <= 2.0


def test_frontline_support_mobilises_cross_domain_resupply():
    brief: Dict[str, Any] = {
        "resource_sustainment": {
            "status": "surge",
            "resource_needs": [
                "Artillery ammunition surge",
                "FPV drone kit replenishment",
            ],
            "recommended_actions": [
                "Deploy logistics convoy to Donetsk axis.",
            ],
            "allocation_plan": [
                {
                    "resource": "155mm battery resupply",
                    "priority": "immediate",
                    "focus": "3rd Assault Brigade",
                    "quantity": 4,
                    "window_hours": 5.0,
                },
                {
                    "resource": "FPV drone kits",
                    "priority": "next_shift",
                    "focus": "60th Mechanised",
                    "quantity": 6,
                    "window_hours": 7.5,
                },
            ],
        },
        "support_priorities": {
            "status": "mobilise",
            "recommended_actions": [
                "Coordinate cross-border ammunition lift.",
            ],
            "priorities": [
                {
                    "name": "3rd Assault Brigade",
                    "focus": "Donetsk fires corridor",
                    "support_window_hours": 4.5,
                },
                {
                    "name": "60th Mechanised Brigade",
                    "support_window_hours": 7.0,
                },
            ],
        },
        "response_readiness": {
            "level": "critical",
            "support_window_hours": 4.0,
            "priority_actions": ["Add night shift coverage"],
        },
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 6.0,
        },
        "operational_continuity": {
            "status": "constrained",
            "continuity_score": 52,
        },
        "operational_resilience": {
            "status": "fragile",
            "resilience_score": 58,
        },
        "operational_recovery": {"status": "recover"},
        "operational_outlook": {"severity": 72},
        "operational_risks": {"severity_score": 82},
        "mission_assurance": {"status": "strained"},
        "command_alignment": {"alignment_score": 54},
        "operational_transformation": {"transformation_score": 58},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "warning"},
                "predictions": {"status": "stale"},
            }
        },
        "detection_quality": {"weighted_avg_confidence": 0.58},
        "intelligence_gaps": [
            {"severity": "critical", "description": "FPV supply gap"}
        ],
        "meta": {"detections": {"troop": {"count": 1}}},
        "activity_summary": {"tempo": "surge"},
    }

    frontline = intel_brief._derive_frontline_support(brief)
    assert frontline is not None
    assert frontline.get("status") in {"critical", "mobilise"}

    score = frontline.get("support_score")
    assert isinstance(score, (int, float)) and score < 80

    units = frontline.get("priority_units", [])
    assert "3rd Assault Brigade" in units

    brigade_support = frontline.get("brigade_support", [])
    assert any(entry.get("unit") == "3rd Assault Brigade" for entry in brigade_support)

    notes = frontline.get("ukrainian_operator_notes", [])
    assert notes and any("Забезпечте" in note or "Використовуйте" in note for note in notes)

    actions = " ".join(frontline.get("recommended_actions", []))
    assert "Ukrainian Joint Forces" in actions

    window = frontline.get("coordination_window_hours")
    assert isinstance(window, (float, int)) and window <= 4.5


def test_automation_playbook_demands_manual_override_under_crisis():
    brief: Dict[str, Any] = {
        "command_directives": {
            "status": "escalate",
            "severity": 22,
            "directives": [
                {
                    "action": "Authorize surge logistics automation",
                    "priority": "immediate",
                    "team": "Automation Cell",
                    "window_hours": 2.5,
                },
                {
                    "action": "Sync command dashboards",
                    "priority": "next_shift",
                    "team": "Joint Staff",
                    "window_hours": 6.0,
                },
            ],
            "planning_window_hours": 3.0,
        },
        "communication_plan": {
            "status": "crisis",
            "audience_cadence": [
                {
                    "audience": "Joint Staff",
                    "cadence_hours": 2.0,
                    "mode": "manual",
                },
                {
                    "audience": "Brigade Liaisons",
                    "cadence_hours": 3.5,
                },
            ],
        },
        "operational_governance": {"status": "degraded"},
        "resource_sustainment": {"status": "surge"},
        "frontline_support": {"status": "critical"},
        "response_readiness": {
            "level": "critical",
            "support_window_hours": 2.0,
        },
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 7.0,
        },
        "support_priorities": {
            "status": "mobilise",
            "priorities": [
                {
                    "name": "Fires Support Team",
                    "reason": "Restore ammunition telemetry",
                    "support_window_hours": 5.0,
                }
            ],
        },
        "operational_resilience": {"status": "fragile"},
        "operational_continuity": {"status": "constrained"},
        "operational_recovery": {"status": "recover"},
        "mission_assurance": {"status": "strained"},
        "operational_transformation": {"transformation_score": 50},
        "command_alignment": {"alignment_score": 52},
        "intelligence_confidence": {"level": "low"},
        "detection_quality": {"weighted_avg_confidence": 0.55},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "warning"},
                "predictions": {"status": "stale"},
            }
        },
        "operational_risks": {"severity_score": 84},
        "intelligence_gaps": [
            {
                "severity": "critical",
                "description": "Telemetry automation gap",
            }
        ],
        "meta": {"detections": {"troop": {"count": 1}}},
    }

    automation = intel_brief._derive_automation_playbook(brief)
    assert automation is not None
    assert automation.get("status") == "manual_override"
    assert automation.get("automation_score") < 60
    assert any("Command directives" in trigger for trigger in automation.get("triggers", []))
    assert any(task.get("mode") == "guided" for task in automation.get("automation_tasks", []))
    assert automation.get("automation_window_hours") == pytest.approx(2.0, rel=1e-3)
    prompts = automation.get("ukrainian_operator_prompts", [])
    assert prompts and any("Перевіряйте" in prompt for prompt in prompts)
    actions = " ".join(automation.get("recommended_actions", []))
    assert "automation health" in actions.lower()


def test_automation_playbook_tracks_guided_workflows_when_stable():
    brief: Dict[str, Any] = {
        "command_directives": {
            "status": "synchronise",
            "severity": 6,
            "directives": [
                {
                    "action": "Publish daily automation bulletin",
                    "priority": "next_shift",
                    "team": "Automation Cell",
                    "window_hours": 12.0,
                }
            ],
            "planning_window_hours": 12.0,
        },
        "communication_plan": {
            "status": "stabilise",
            "audience_cadence": [
                {"audience": "Joint Staff", "cadence_hours": 6.0},
                {"audience": "Brigade Liaisons", "cadence_hours": 8.0},
            ],
        },
        "operational_governance": {"status": "steady"},
        "resource_sustainment": {"status": "steady"},
        "frontline_support": {"status": "steady"},
        "response_readiness": {"level": "watch", "support_window_hours": 9.0},
        "response_pressure": {"status": "prediction_gap_watch", "estimated_clearance_hours": 10.0},
        "support_priorities": {
            "status": "watch",
            "priorities": [
                {"name": "Ops Cell", "support_window_hours": 9.0, "focus": "Telemetry"}
            ],
        },
        "operational_resilience": {"status": "stable"},
        "operational_continuity": {"status": "stable"},
        "operational_transformation": {"transformation_score": 80},
        "command_alignment": {"alignment_score": 82},
        "intelligence_confidence": {"level": "moderate"},
        "detection_quality": {"weighted_avg_confidence": 0.7},
        "data_freshness": {"feeds": {"detections": {"status": "fresh"}}},
        "operational_risks": {"severity_score": 52},
        "intelligence_gaps": [],
        "meta": {"detections": {"troop": {"count": 4}}},
    }

    automation = intel_brief._derive_automation_playbook(brief)
    assert automation is not None
    assert automation.get("status") in {"autonomous", "tune"}
    assert automation.get("automation_score") >= 70
    assert automation.get("automation_window_hours") == pytest.approx(6.0, rel=1e-3)
    tasks = automation.get("automation_tasks", [])
    assert any(task.get("mode") == "automated" for task in tasks)
    tracks = automation.get("automation_tracks", [])
    assert tracks and any("Comms" in track or "Support" in track for track in tracks)
    drivers = automation.get("drivers", [])
    assert any("alignment" in driver.lower() or "automation" in driver.lower() for driver in drivers)


def test_automation_guardrails_lockdown_when_critical_signals():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "manual_override",
            "automation_score": 52,
            "blockers": ["Telemetry confidence is guarded and slowing automation."],
            "automation_tasks": [
                {
                    "task": "Auto-dispatch resupply alerts",
                    "mode": "guided",
                    "owner": "Automation Cell",
                    "window_hours": 1.5,
                }
            ],
            "monitoring_channels": ["Automation Ops Room"],
            "recommended_actions": ["Document automation overrides after each shift."],
        },
        "frontline_support": {"status": "mobilise"},
        "response_readiness": {"level": "critical", "support_window_hours": 2.0},
        "response_pressure": {"status": "critical_backlog", "estimated_clearance_hours": 7.0},
        "operational_governance": {"governance_score": 54, "next_review_hours": 5.0},
        "mission_assurance": {"assurance_score": 52},
        "operational_resilience": {"resilience_score": 55},
        "operational_continuity": {"continuity_score": 50},
        "operational_recovery": {"recovery_score": 48},
        "operational_transformation": {"transformation_score": 52},
        "resource_sustainment": {"status": "surge"},
        "support_priorities": {"status": "mobilise"},
        "command_alignment": {"status": "drift", "recommended_actions": ["Sync alignment"]},
        "command_directives": {"status": "escalate"},
        "communication_plan": {"status": "crisis"},
        "operational_outlook": {"status": "heightened_watch"},
        "intelligence_confidence": {"level": "low"},
        "detection_quality": {"weighted_avg_confidence": 0.55},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "warning", "age_minutes": 90},
                "predictions": {"status": "stale", "age_minutes": 150},
            }
        },
        "intelligence_gaps": [
            {"severity": "critical", "description": "Telemetry automation gap"},
            {"severity": "major", "description": "Feedback sync"},
        ],
        "operational_risks": {"severity_score": 84},
        "meta": {"feedback_accuracy": 0.5},
    }

    guardrails = intel_brief._derive_automation_guardrails(brief)
    assert guardrails is not None
    assert guardrails.get("status") == "locked_down"
    assert guardrails.get("autonomy_score") < 65
    guardrail_notes = " ".join(guardrails.get("guardrails", []))
    assert "dual approvals" in guardrail_notes.lower()
    checklist = " ".join(guardrails.get("ukrainian_checklist", []))
    assert "журнал" in checklist.lower()
    monitoring = guardrails.get("monitoring_channels", [])
    assert any("Automation Ops Room" in channel for channel in monitoring)
    actions = " ".join(guardrails.get("recommended_actions", []))
    assert "automation officer" in actions.lower()


def test_automation_guardrails_support_autonomous_mode_when_stable():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "autonomous",
            "automation_score": 88,
            "automation_tasks": [
                {
                    "task": "Publish shift summary",
                    "mode": "automated",
                    "owner": "Automation Cell",
                    "window_hours": 2.0,
                },
                {
                    "task": "Sync logistics queue",
                    "mode": "guided",
                    "window_hours": 6.0,
                },
            ],
            "monitoring_channels": ["Automation Ops Room"],
            "drivers": ["Alignment cadence supports automation"],
        },
        "frontline_support": {"status": "steady"},
        "response_readiness": {"level": "steady", "support_window_hours": 6.0},
        "response_pressure": {"status": "watch", "estimated_clearance_hours": 9.0},
        "operational_governance": {"governance_score": 82, "next_review_hours": 12.0},
        "mission_assurance": {"assurance_score": 78},
        "operational_resilience": {"resilience_score": 80},
        "operational_continuity": {"continuity_score": 76},
        "operational_recovery": {"recovery_score": 74},
        "operational_transformation": {"transformation_score": 82},
        "resource_sustainment": {"status": "steady"},
        "support_priorities": {"status": "watch"},
        "command_alignment": {"status": "steady"},
        "command_directives": {"status": "coordinate"},
        "communication_plan": {"status": "focused"},
        "operational_outlook": {"status": "steady"},
        "intelligence_confidence": {"level": "moderate"},
        "detection_quality": {"weighted_avg_confidence": 0.72},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "fresh", "age_minutes": 15},
                "predictions": {"status": "fresh", "age_minutes": 20},
            }
        },
        "intelligence_gaps": [],
        "operational_risks": {"severity_score": 52},
        "meta": {"feedback_accuracy": 0.82},
    }

    guardrails = intel_brief._derive_automation_guardrails(brief)
    assert guardrails is not None
    assert guardrails.get("status") in {"autonomous", "pilot"}
    assert guardrails.get("autonomy_score") >= 80
    review = guardrails.get("next_review_hours")
    assert isinstance(review, (int, float)) and review <= 2.0
    candidates = guardrails.get("automation_candidates", [])
    assert any("Publish shift summary" in candidate for candidate in candidates)
    checklist = guardrails.get("ukrainian_checklist", [])
    assert checklist and any("Перевірте" in item or "Зафіксуйте" in item for item in checklist)


def test_automation_mission_control_requires_manual_control_under_guardrail_locks():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "manual_override",
            "automation_score": 58,
            "automation_window_hours": 1.5,
            "automation_tracks": ["Resupply auto-dispatch"],
            "recommended_actions": ["Document manual approvals for every automation batch."],
            "monitoring_channels": ["Automation Ops Room"],
        },
        "automation_guardrails": {
            "status": "locked_down",
            "autonomy_score": 52,
            "next_review_hours": 1.0,
            "guardrails": ["Dual officer approval required for automation runs."],
            "monitoring_channels": ["Mission Control Net"],
            "safety_checks": ["Review every automated dispatch with analyst oversight."],
            "ukrainian_checklist": ["Занесіть усі оверрайди до журналу автоматизації."],
            "recommended_actions": ["Alert Ukrainian duty officer before launching automation."],
        },
        "response_readiness": {"level": "critical", "support_window_hours": 1.0},
        "response_pressure": {"status": "critical_backlog", "estimated_clearance_hours": 7.5},
        "frontline_support": {"status": "mobilise"},
        "operational_governance": {"governance_score": 55},
        "mission_assurance": {"assurance_score": 54},
        "operational_resilience": {"resilience_score": 52},
        "operational_continuity": {"continuity_score": 53},
        "operational_recovery": {"recovery_score": 50},
        "operational_transformation": {"transformation_score": 50},
        "support_priorities": {"status": "mobilise"},
        "resource_sustainment": {"status": "surge"},
        "command_alignment": {"status": "misaligned", "recommended_actions": ["Sync automation with command priorities."]},
        "command_directives": {"status": "crisis"},
        "communication_plan": {"status": "crisis"},
        "operational_outlook": {"status": "heightened"},
        "escalation_readiness": {"status": "review", "next_review_hours": 2.5},
        "intelligence_confidence": {"level": "low"},
        "detection_quality": {"weighted_avg_confidence": 0.55},
        "meta": {"feedback_accuracy": 0.6},
    }

    mission_control = intel_brief._derive_automation_mission_control(brief)
    assert mission_control is not None
    assert mission_control.get("status") == "manual_control"
    assert mission_control.get("supervision_level") == "manual_control"
    assert mission_control.get("mission_control_score") < 65
    channels = mission_control.get("mission_channels", [])
    assert any("Automation Ops Room" in channel for channel in channels)
    prompts = " ".join(mission_control.get("ukrainian_operator_prompts", []))
    assert "журнал" in prompts.lower()
    actions = " ".join(mission_control.get("recommended_actions", []))
    assert "duty" in actions.lower() or "чергов" in actions.lower()


def test_automation_mission_control_supports_mission_ready_operations():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "autonomous",
            "automation_score": 88,
            "automation_window_hours": 5.5,
            "automation_tracks": ["Shift briefing automation", "ISR sync"],
            "drivers": ["Alignment cadence steady", "Telemetry confidence strong"],
            "monitoring_channels": ["Automation Ops Room"],
            "recommended_actions": ["Archive automation audit logs daily."],
        },
        "automation_guardrails": {
            "status": "autonomous",
            "autonomy_score": 86,
            "next_review_hours": 6.0,
            "guardrails": ["Log overrides to mission control journal."],
            "monitoring_channels": ["Mission Control Net"],
            "recommended_actions": ["Share guardrail summary during morning sync."],
        },
        "response_readiness": {"level": "steady", "support_window_hours": 8.0},
        "response_pressure": {"status": "steady", "estimated_clearance_hours": 4.0},
        "frontline_support": {"status": "steady"},
        "operational_governance": {"governance_score": 82},
        "mission_assurance": {"assurance_score": 80},
        "operational_resilience": {"resilience_score": 84},
        "operational_continuity": {"continuity_score": 80},
        "operational_recovery": {"recovery_score": 78},
        "operational_transformation": {"transformation_score": 82},
        "support_priorities": {"status": "steady"},
        "resource_sustainment": {"status": "steady"},
        "command_alignment": {"status": "steady"},
        "command_directives": {"status": "coordinate"},
        "communication_plan": {"status": "focused"},
        "operational_outlook": {"status": "steady"},
        "escalation_readiness": {"status": "steady", "next_review_hours": 10.0},
        "intelligence_confidence": {"level": "high"},
        "detection_quality": {"weighted_avg_confidence": 0.82},
        "meta": {"feedback_accuracy": 0.88},
    }

    mission_control = intel_brief._derive_automation_mission_control(brief)
    assert mission_control is not None
    assert mission_control.get("status") in {"mission_ready", "supervised"}
    assert mission_control.get("mission_control_score") >= 80
    assert mission_control.get("supervision_level") in {"mission_ready", "supervised"}
    next_sync = mission_control.get("next_sync_hours")
    assert isinstance(next_sync, (int, float)) and next_sync > 0
    focus = mission_control.get("control_focus", [])
    assert focus and any("alignment" in item.lower() or "telemetry" in item.lower() for item in focus)
    actions = mission_control.get("recommended_actions", [])
    assert any("Archive" in action or "sync" in action.lower() for action in actions)


def test_operational_risk_register_escalates_compound_signals():
    brief: Dict[str, Any] = {
        "response_readiness": {
            "level": "critical",
            "support_window_hours": 2.0,
            "drivers": ["Readiness degraded"],
            "priority_actions": ["Mobilise reserve analysts to restore readiness coverage."],
        },
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 3.5,
            "drivers": ["Prediction backlog exceeds analyst throughput."],
            "recommended_actions": ["Deploy surge analysts to triage queued predictions immediately."],
        },
        "intelligence_confidence": {
            "level": "low",
            "drivers": ["Feedback drift"],
            "recommended_actions": ["Audit telemetry pipelines with the analyst enablement team."],
        },
        "health": {
            "risk_level": "high",
            "drivers": ["Telemetry and workload strain"],
            "recommended_actions": ["Convene cross-functional leadership to manage the elevated risk."],
        },
        "operational_outlook": {
            "status": "rapid_response",
            "severity_score": 14,
            "planning_horizon_hours": 4.0,
            "focus_areas": ["Telemetry recovery"],
            "recommended_actions": ["Stage contingency resources to match the rapid response outlook."],
        },
        "command_directives": {
            "severity": 16,
            "status": "accelerate",
            "drivers": ["Leadership tasks growing"],
            "recommended_actions": ["Hold an immediate leadership briefing on surge posture."],
            "planning_window_hours": 5.0,
        },
        "resource_sustainment": {
            "status": "surge",
            "resupply_window_hours": 3.0,
            "drivers": ["Telemetry repairs"],
            "recommended_actions": ["Stage logistics teams to support telemetry recovery."],
        },
        "communication_plan": {
            "status": "escalated",
            "update_cadence_minutes": 30,
            "drivers": ["Leadership updates"],
            "recommended_actions": ["Issue hourly updates to command leadership."],
        },
        "data_freshness": {
            "feeds": {"detections": {"status": "stale", "age_minutes": 90}}
        },
        "intelligence_gaps": [
            {
                "gap": "prediction_coverage",
                "severity": "critical",
                "detail": "Prediction coverage below 40%.",
                "recommended_action": "Escalate to modelling for immediate retraining.",
            }
        ],
        "contingency_plans": {
            "status": "activate",
            "activation_window_hours": 1.5,
            "drivers": ["Telemetry outage scenarios"],
            "recommended_actions": ["Stand contingency team for telemetry outage playbooks."],
        },
        "support_priorities": {
            "status": "mobilise",
            "recommended_actions": ["Coordinate mobilisation tasks across highlighted support teams."],
            "priorities": [
                {"team": "Telemetry Operations", "support_window_hours": 1.0}
            ],
        },
        "detection_quality": {"weighted_avg_confidence": 0.5},
    }

    register = intel_brief._derive_operational_risk_register(brief)
    assert register is not None
    assert register.get("status") in {"critical", "escalated"}
    assert register.get("risk_count", 0) >= 5
    assert register.get("severity_score", 0) >= 12
    names = {entry.get("name") for entry in register.get("risks", []) if isinstance(entry, dict)}
    assert "Response readiness" in names
    assert "Analyst response pressure" in names
    assert "Command directives" in names
    assert register.get("recommended_actions")
    assert register.get("drivers")
    assert register.get("next_review_hours") is not None


def test_command_alignment_flags_alignment_gaps():
    brief: Dict[str, Any] = {
        "command_directives": {
            "severity": 22,
            "status": "escalate",
            "focus_areas": ["Telemetry restoration"],
            "coordination_teams": ["Telemetry Ops", "Command"],
            "recommended_actions": ["Hold a crisis stand-up for telemetry recovery."],
            "planning_window_hours": 2.0,
        },
        "communication_plan": {
            "status": "escalated",
            "update_cadence_minutes": 30,
            "recommended_actions": ["Issue hourly updates to command stakeholders."],
            "audiences": [
                {"audience": "Command", "focus": "Telemetry recovery", "cadence_minutes": 30}
            ],
        },
        "resource_sustainment": {
            "status": "surge",
            "resupply_window_hours": 1.5,
            "resource_needs": ["Surge staffing"],
            "recommended_actions": ["Mobilise logistics support for surge coverage."],
        },
        "operational_risks": {
            "status": "critical",
            "severity_score": 22,
            "focus_areas": ["Telemetry"],
            "recommended_actions": ["Escalate critical telemetry risk to leadership."],
            "risks": [{"name": "Telemetry outage", "severity": 4}],
            "next_review_hours": 2.5,
        },
        "response_readiness": {
            "level": "critical",
            "support_window_hours": 1.0,
            "priority_actions": ["Mobilise reserve analysts to stabilise readiness."],
        },
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 2.0,
            "recommended_actions": ["Clear the prediction backlog with surge analysts."],
        },
        "support_priorities": {
            "status": "mobilise",
            "recommended_actions": ["Mobilise support squads to cover telemetry tasks."],
            "priorities": [
                {"team": "Telemetry Ops", "reason": "Restore sensors", "support_window_hours": 1.25}
            ],
        },
        "operational_outlook": {
            "severity_score": 10,
            "focus_areas": ["Telemetry remediation"],
            "recommended_actions": ["Align all teams on the telemetry remediation horizon."],
            "planning_horizon_hours": 6.0,
        },
        "operational_posture": {"status": "recover", "focus": "Telemetry", "horizon_hours": 4.0},
        "intelligence_confidence": {
            "level": "guarded",
            "recommended_actions": ["Validate telemetry sources with engineering teams."],
        },
        "health": {
            "risk_level": "high",
            "drivers": ["Telemetry risk"],
            "recommended_actions": ["Coordinate leadership mitigation for telemetry risk."],
        },
        "contingency_plans": {
            "status": "activate",
            "activation_window_hours": 3.0,
            "scenarios": [{"name": "Telemetry fallback"}],
            "recommended_actions": ["Activate telemetry fallback scenario owners."],
        },
        "intelligence_gaps": [
            {"gap": "prediction_coverage", "severity": "critical", "detail": "Coverage below 40%"}
        ],
    }

    alignment = intel_brief._derive_command_alignment(brief)
    assert alignment is not None
    assert alignment.get("status") in {"at_risk", "misaligned"}
    assert alignment.get("alignment_score", 100) < 70
    assert alignment.get("coordination_gaps")
    assert any("Telemetry" in area for area in alignment.get("focus_areas", []))
    actions = " ".join(alignment.get("recommended_actions", []))
    assert "surge" in actions.lower()
    assert alignment.get("next_sync_hours") is not None


def test_mission_assurance_compiles_blockers_and_actions():
    brief: Dict[str, Any] = {
        "response_readiness": {
            "level": "critical",
            "support_window_hours": 2.0,
            "priority_actions": ["Stage rapid response teams."],
            "drivers": ["Telemetry outage impact"],
        },
        "command_alignment": {
            "status": "misaligned",
            "alignment_score": 42,
            "coordination_gaps": ["Telemetry restoration ownership"],
            "recommended_actions": ["Run a cross-team recovery stand-up."],
            "focus_areas": ["Telemetry"],
            "next_sync_hours": 1.25,
        },
        "resource_sustainment": {
            "status": "surge",
            "resupply_window_hours": 1.5,
            "resource_needs": ["Surge staffing"],
            "recommended_actions": ["Deploy reserve sustainment teams."],
        },
        "operational_risks": {
            "severity_score": 20,
            "focus_areas": ["Telemetry"],
            "recommended_actions": ["Escalate telemetry risk to leadership."],
            "next_review_hours": 3.0,
        },
        "contingency_plans": {
            "status": "activate",
            "activation_window_hours": 2.5,
            "drivers": ["Telemetry outage scenarios"],
            "scenarios": [{"name": "Telemetry fallback"}],
            "recommended_actions": ["Activate telemetry fallback scenario owners."],
        },
        "communication_plan": {
            "status": "escalated",
            "update_cadence_minutes": 45,
            "recommended_actions": ["Issue hourly command updates."],
            "audiences": [
                {"audience": "Command", "focus": "Telemetry outage", "cadence_minutes": 45}
            ],
        },
        "command_directives": {
            "status": "escalate",
            "severity": 20,
            "focus_areas": ["Telemetry remediation"],
            "coordination_teams": ["Command"],
            "planning_window_hours": 4.0,
            "recommended_actions": ["Confirm telemetry remediation lead."],
        },
        "operational_outlook": {
            "severity_score": 14,
            "focus_areas": ["Telemetry recovery"],
            "recommended_actions": ["Hold near-term recovery planning."],
            "planning_horizon_hours": 6.0,
            "drivers": ["Threat posture"],
        },
        "operational_posture": {
            "status": "recover",
            "focus": "Telemetry",
            "horizon_hours": 5.0,
        },
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 3.0,
            "recommended_actions": ["Clear the analyst backlog with surge support."],
            "drivers": ["Prediction backlog"],
        },
        "support_priorities": {
            "status": "mobilise",
            "recommended_actions": ["Mobilise support squads to cover telemetry tasks."],
            "priorities": [
                {
                    "team": "Telemetry Ops",
                    "reason": "Restore sensors",
                    "support_window_hours": 2.0,
                }
            ],
        },
        "intelligence_confidence": {
            "level": "low",
            "recommended_actions": ["Validate telemetry sources."],
            "drivers": ["Feedback accuracy drift"],
        },
        "health": {
            "risk_level": "severe",
            "recommended_actions": ["Coordinate leadership mitigation for telemetry risk."],
            "drivers": ["Telemetry dependency"],
        },
        "intelligence_gaps": [
            {"gap": "prediction_coverage", "severity": "critical", "detail": "Coverage below 40%"}
        ],
        "data_freshness": {
            "feeds": {"detections": {"status": "stale"}},
        },
    }

    assurance = intel_brief._derive_mission_assurance(brief)
    assert assurance is not None
    assert assurance.get("status") in {"critical", "at_risk"}
    assert assurance.get("assurance_score", 100) < 75
    assert assurance.get("blockers")
    assert any("telemetry" in blocker.lower() for blocker in assurance.get("blockers", []))
    assert assurance.get("dependency_windows")
    assert assurance.get("next_checkpoint_hours") is not None
    assert assurance.get("recommended_actions")
    assert any("telemetry" in focus.lower() for focus in assurance.get("focus_areas", []))


def test_operational_resilience_penalises_stale_feeds_and_pressure():
    brief: Dict[str, Any] = {
        "mission_assurance": {
            "status": "at_risk",
            "recommended_actions": ["Stabilise assurance drivers."],
            "next_checkpoint_hours": 1.25,
        },
        "response_readiness": {
            "level": "critical",
            "priority_actions": ["Surge rapid response analysts."],
            "support_window_hours": 1.5,
            "drivers": ["Telemetry outage"],
        },
        "resource_sustainment": {
            "status": "surge",
            "resupply_window_hours": 2.0,
            "recommended_actions": ["Deploy reserve sustainment crews."],
            "resource_needs": ["Fuel pods"],
        },
        "operational_risks": {
            "severity_score": 18,
            "recommended_actions": ["Escalate operational risk review."],
            "focus_areas": ["Telemetry"],
        },
        "contingency_plans": {
            "status": "activate",
            "activation_window_hours": 4.0,
            "scenarios": [{"name": "Telemetry fallback"}],
            "recommended_actions": ["Activate telemetry fallback controllers."],
        },
        "communication_plan": {
            "status": "crisis",
            "recommended_actions": ["Issue crisis broadcast."],
            "key_messages": ["Telemetry offline"],
            "audiences": [{"focus": "Command"}],
        },
        "command_alignment": {
            "status": "misaligned",
            "recommended_actions": ["Run emergency alignment stand-up."],
            "drivers": ["Telemetry ownership"],
            "focus_areas": ["Telemetry"],
            "next_sync_hours": 1.0,
            "coordination_gaps": ["Telemetry ownership unclear"],
        },
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 2.5,
            "recommended_actions": ["Clear analyst backlog immediately."],
        },
        "support_priorities": {
            "status": "mobilise",
            "recommended_actions": ["Mobilise telemetry support teams."],
            "priorities": [
                {"team": "Telemetry Ops", "support_window_hours": 1.25},
            ],
        },
        "data_freshness": {"feeds": {"detections": {"status": "stale"}}},
        "intelligence_confidence": {
            "level": "low",
            "recommended_actions": ["Validate degraded telemetry inputs."],
            "drivers": ["Telemetry outage"],
        },
        "intelligence_gaps": [
            {"gap": "telemetry", "severity": "critical", "detail": "Telemetry offline"}
        ],
        "operational_outlook": {
            "status": "rapid_response",
            "recommended_actions": ["Trigger rapid response cells."],
            "drivers": ["Telemetry outage"],
            "planning_horizon_hours": 6.0,
        },
    }

    resilience = intel_brief._derive_operational_resilience(brief)
    assert resilience is not None
    assert resilience.get("status") in {"vulnerable", "critical"}
    assert resilience.get("resilience_score", 100) < 70
    assert any("stale" in spot.lower() for spot in resilience.get("weak_spots", []))
    assert any("telemetry" in driver.lower() for driver in resilience.get("drivers", []))
    actions = resilience.get("recommended_actions") or []
    assert any("validate" in action.lower() for action in actions)
    assert resilience.get("stability_window_hours") == pytest.approx(1.0)


def test_operational_resilience_highlights_reinforcing_signals():
    brief: Dict[str, Any] = {
        "mission_assurance": {
            "status": "assured",
            "recommended_actions": ["Maintain assurance cadence."],
            "drivers": ["Coordinated leadership"],
            "focus_areas": ["Joint operations"],
            "next_checkpoint_hours": 4.0,
        },
        "response_readiness": {
            "level": "steady",
            "priority_actions": ["Rotate on-call analysts."],
            "support_window_hours": 6.0,
            "drivers": ["Balanced staffing"],
        },
        "resource_sustainment": {
            "status": "monitor",
            "recommended_actions": ["Maintain sustainment posture."],
            "resupply_window_hours": 8.0,
        },
        "operational_risks": {
            "severity_score": 2,
            "recommended_actions": ["Track low-risk watchlist."],
            "focus_areas": ["Training"],
            "next_review_hours": 10.0,
        },
        "contingency_plans": {
            "status": "watch",
            "scenarios": [{"name": "Weather fallback"}],
            "recommended_actions": ["Review weather fallback owners."],
        },
        "communication_plan": {
            "status": "routine",
            "recommended_actions": ["Share weekly alignment brief."],
            "audiences": [{"focus": "Command"}],
        },
        "command_alignment": {
            "status": "aligned",
            "recommended_actions": ["Sustain cross-team sync cadence."],
            "drivers": ["Shared metrics"],
            "focus_areas": ["Joint operations"],
            "next_sync_hours": 12.0,
        },
        "response_pressure": {
            "status": "balanced",
            "recommended_actions": ["Maintain throughput pacing."],
            "estimated_clearance_hours": 5.0,
        },
        "support_priorities": {
            "status": "monitor",
            "recommended_actions": ["Monitor support queue."],
            "priorities": [
                {"team": "Support", "support_window_hours": 7.0},
            ],
        },
        "data_freshness": {"feeds": {"detections": {"status": "fresh"}}},
        "intelligence_confidence": {
            "level": "high",
            "recommended_actions": ["Celebrate telemetry wins."],
            "drivers": ["Accurate feedback"],
        },
        "operational_outlook": {
            "status": "stabilise",
            "recommended_actions": ["Hold stabilisation posture."],
            "drivers": ["Balanced indicators"],
            "planning_horizon_hours": 24.0,
        },
    }

    resilience = intel_brief._derive_operational_resilience(brief)
    assert resilience is not None
    assert resilience.get("status") in {"resilient", "steady"}
    assert resilience.get("resilience_score", 0) >= 70
    reinforcing = resilience.get("reinforcing_factors") or []
    assert any("assurance" in factor.lower() for factor in reinforcing)
    assert not resilience.get("weak_spots")
    assert resilience.get("stability_window_hours") == pytest.approx(4.0)
    assert any(
        action in resilience.get("recommended_actions", [])
        for action in ["Maintain assurance cadence.", "Rotate on-call analysts."]
    )


def test_operational_continuity_penalises_compounded_degradation():
    brief: Dict[str, Any] = {
        "mission_assurance": {
            "status": "critical",
            "recommended_actions": ["Stabilise mission dependencies."],
            "drivers": ["Telemetry outage"],
            "focus_areas": ["Telemetry"],
            "blockers": ["Telemetry offline"],
            "next_checkpoint_hours": 2.5,
        },
        "operational_resilience": {
            "status": "vulnerable",
            "recommended_actions": ["Rebuild resilience posture."],
            "drivers": ["Telemetry"],
            "weak_spots": ["Telemetry intake offline"],
            "reinforcing_factors": ["Command focus"],
            "stability_window_hours": 1.5,
        },
        "resource_sustainment": {
            "status": "surge",
            "resource_needs": ["Fuel pods"],
            "recommended_actions": ["Deploy reserve logistics teams."],
            "resupply_window_hours": 3.0,
        },
        "operational_risks": {
            "severity_score": 18,
            "recommended_actions": ["Escalate operational risk review."],
            "focus_areas": ["Telemetry"],
            "next_review_hours": 4.0,
        },
        "contingency_plans": {
            "status": "activate",
            "watch_items": ["Fallback sensors"],
            "recommended_actions": ["Activate telemetry fallback."],
            "activation_window_hours": 2.0,
            "scenarios": [{"name": "Telemetry fallback"}],
        },
        "communication_plan": {
            "status": "crisis",
            "recommended_actions": ["Issue crisis broadcast."],
            "key_messages": ["Telemetry offline"],
            "audiences": [{"focus": "Command"}],
            "update_cadence_minutes": 45,
        },
        "command_directives": {
            "status": "escalate",
            "severity": 20,
            "focus_areas": ["Telemetry recovery"],
            "coordination_teams": ["Command"],
            "recommended_actions": ["Deploy crisis command cell."],
            "planning_window_hours": 3.0,
        },
        "command_alignment": {
            "status": "misaligned",
            "recommended_actions": ["Run emergency alignment huddle."],
            "drivers": ["Telemetry ownership"],
            "focus_areas": ["Telemetry"],
            "coordination_gaps": ["Telemetry owner unclear"],
            "next_sync_hours": 1.5,
        },
        "support_priorities": {
            "status": "mobilise",
            "recommended_actions": ["Mobilise telemetry support teams."],
            "priorities": [
                {
                    "team": "Telemetry Ops",
                    "reason": "Restore sensors",
                    "support_window_hours": 2.0,
                }
            ],
        },
        "response_readiness": {
            "level": "critical",
            "priority_actions": ["Surge rapid response analysts."],
            "support_window_hours": 1.0,
            "drivers": ["Telemetry outage"],
        },
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 2.5,
            "recommended_actions": ["Clear telemetry review backlog."],
            "drivers": ["Telemetry review backlog"],
        },
        "intelligence_confidence": {
            "level": "low",
            "recommended_actions": ["Validate degraded telemetry inputs."],
            "drivers": ["Telemetry signal loss"],
        },
        "data_freshness": {"feeds": {"detections": {"status": "stale"}}},
        "operational_outlook": {
            "status": "escalation_imminent",
            "recommended_actions": ["Prepare escalation contingency."],
            "drivers": ["Telemetry outage"],
            "planning_horizon_hours": 6.0,
        },
    }

    continuity = intel_brief._derive_operational_continuity(brief)
    assert continuity is not None
    assert continuity.get("status") == "critical"
    assert continuity.get("continuity_score", 100) < 60
    constraints = continuity.get("primary_constraints", [])
    assert any("restore" in item.lower() for item in constraints)
    watch_items = continuity.get("watch_items", [])
    assert any("telemetry intake" in item.lower() for item in watch_items)
    actions = continuity.get("recommended_actions", [])
    assert any("stabilise" in action.lower() for action in actions)


def test_operational_continuity_highlights_stability_and_horizon():
    brief: Dict[str, Any] = {
        "mission_assurance": {
            "status": "assured",
            "recommended_actions": ["Maintain mission cadence."],
            "drivers": ["Coordinated response"],
            "focus_areas": ["Logistics"],
            "next_checkpoint_hours": 6.0,
        },
        "operational_resilience": {
            "status": "resilient",
            "recommended_actions": ["Document resilience best practices."],
            "drivers": ["Redundant telemetry"],
            "reinforcing_factors": ["Redundant telemetry"],
            "stability_window_hours": 12.0,
        },
        "resource_sustainment": {
            "status": "monitor",
            "recommended_actions": ["Continue sustainment monitoring."],
            "resupply_window_hours": 10.0,
        },
        "operational_risks": {
            "severity_score": 2,
            "recommended_actions": ["Maintain low-risk watch."],
            "focus_areas": ["Training"],
            "next_review_hours": 24.0,
        },
        "contingency_plans": {
            "status": "watch",
            "recommended_actions": ["Review contingency watchlist."],
            "watch_items": ["Weather backup"],
            "scenarios": [{"name": "Weather backup"}],
        },
        "communication_plan": {
            "status": "routine",
            "recommended_actions": ["Send weekly alignment digest."],
            "audiences": [{"focus": "Command"}],
            "update_cadence_minutes": 120,
        },
        "command_directives": {
            "status": "monitor",
            "recommended_actions": ["Monitor directive queue."],
            "planning_window_hours": 8.0,
        },
        "command_alignment": {
            "status": "aligned",
            "recommended_actions": ["Sustain alignment cadence."],
            "drivers": ["Shared objectives"],
            "focus_areas": ["Logistics"],
            "next_sync_hours": 12.0,
        },
        "support_priorities": {
            "status": "monitor",
            "recommended_actions": ["Maintain support monitoring."],
            "priorities": [
                {"team": "Logistics", "reason": "Standing watch", "support_window_hours": 9.0}
            ],
        },
        "response_readiness": {
            "level": "steady",
            "priority_actions": ["Rotate analysts."],
            "support_window_hours": 6.0,
            "drivers": ["Balanced staffing"],
        },
        "response_pressure": {
            "status": "balanced",
            "recommended_actions": ["Maintain throughput."],
            "estimated_clearance_hours": 4.0,
        },
        "intelligence_confidence": {
            "level": "high",
            "recommended_actions": ["Share telemetry confidence summary."],
            "drivers": ["Accurate feedback"],
        },
        "data_freshness": {"feeds": {"detections": {"status": "fresh"}}},
        "operational_outlook": {
            "status": "steady_watch",
            "recommended_actions": ["Maintain outlook watch."],
            "drivers": ["Stable environment"],
            "planning_horizon_hours": 16.0,
        },
    }

    continuity = intel_brief._derive_operational_continuity(brief)
    assert continuity is not None
    assert continuity.get("status") in {"sustained", "watch"}
    assert continuity.get("continuity_score", 0) >= 80
    assert continuity.get("continuity_horizon_hours") == pytest.approx(2.0)
    stability = continuity.get("stability_factors", [])
    assert any("steady" in item.lower() for item in stability)
    watch_items = continuity.get("watch_items", [])
    assert any("weather" in item.lower() for item in watch_items)
    drivers = continuity.get("drivers", [])
    assert any("objectives" in driver.lower() for driver in drivers)


def test_escalation_matrix_flags_critical_conditions():
    brief = {
        "command_directives": {
            "severity": 24,
            "directives": [
                {"action": "Launch crisis cell", "priority": "immediate", "context": "Ops"}
            ],
        },
        "operational_continuity": {
            "status": "critical",
            "recommended_actions": ["Restore power redundancy"],
            "drivers": ["Power grid"],
            "primary_constraints": ["Generator capacity"],
            "continuity_horizon_hours": 1.5,
        },
        "operational_resilience": {
            "status": "critical",
            "recommended_actions": ["Request allied support"],
            "drivers": ["Field logistics"],
            "stability_window_hours": 0.5,
        },
        "mission_assurance": {
            "status": "critical",
            "blockers": ["Signal unit offline"],
            "focus_areas": ["Command alignment"],
            "recommended_actions": ["Escalate command recovery"],
        },
        "response_readiness": {
            "level": "critical",
            "priority_actions": ["Recall reserve analysts"],
            "drivers": ["Staff shortage"],
            "support_window_hours": 2,
        },
        "response_pressure": {
            "status": "critical_backlog",
            "recommended_actions": ["Activate surge roster"],
            "estimated_clearance_hours": 6,
        },
        "support_priorities": {
            "status": "mobilise",
            "recommended_actions": ["Deploy field tech teams"],
            "priorities": [{"reason": "Rewire comms", "support_window_hours": 3}],
        },
        "contingency_plans": {
            "status": "activate",
            "recommended_actions": ["Stand up continuity site"],
            "watch_items": ["Storm front"],
            "activation_window_hours": 4,
        },
        "communication_plan": {
            "status": "escalated",
            "recommended_actions": ["Issue crisis bulletin"],
            "key_messages": ["Critical outage"],
        },
        "resource_sustainment": {
            "status": "surge",
            "recommended_actions": ["Fly spare parts"],
            "resupply_window_hours": 5,
            "allocation_plan": [{"team": "Logistics"}],
        },
        "operational_risks": {
            "severity_score": 20,
            "recommended_actions": ["Coordinate joint response"],
            "risks": [{"detail": "Ops centre inaccessible"}],
            "next_review_hours": 7,
        },
        "intelligence_gaps": [
            {
                "severity": "critical",
                "detail": "Prediction coverage loss",
                "recommended_action": "Retrain local model",
            }
        ],
        "data_freshness": {"feeds": {"detections": {"status": "stale"}}},
        "intelligence_confidence": {
            "level": "low",
            "recommended_actions": ["Audit telemetry"],
            "drivers": ["Feedback variance"],
        },
        "operational_outlook": {
            "status": "escalation_imminent",
            "recommended_actions": ["Notify theatre command"],
            "focus_areas": ["Northern corridor"],
            "planning_horizon_hours": 3,
        },
        "command_alignment": {
            "status": "misaligned",
            "recommended_actions": ["Schedule joint brief"],
            "coordination_gaps": ["Ops vs comms"],
            "next_sync_hours": 4,
        },
    }

    matrix = intel_brief._derive_escalation_matrix(brief)

    assert matrix is not None
    assert matrix.get("status") == "escalate"
    assert matrix.get("readiness_score", 100) < 50
    assert any(
        "critical intelligence gap" in signal.lower()
        for signal in matrix.get("escalation_signals", [])
    )
    assert any("crisis" in action.lower() for action in matrix.get("recommended_actions", []))


def test_escalation_matrix_recognises_stable_conditions():
    brief = {
        "command_directives": {
            "severity": 4,
            "directives": [
                {"action": "Maintain situational overview", "priority": "monitor"}
            ],
        },
        "operational_continuity": {
            "status": "sustained",
            "continuity_horizon_hours": 12,
            "drivers": ["Balanced logistics"],
        },
        "operational_resilience": {
            "status": "resilient",
            "stability_window_hours": 8,
            "drivers": ["Support readiness"],
        },
        "mission_assurance": {"status": "assured"},
        "response_readiness": {
            "level": "steady",
            "support_window_hours": 6,
        },
        "response_pressure": {"status": "balanced"},
        "support_priorities": {"status": "monitor"},
        "communication_plan": {"status": "routine"},
        "resource_sustainment": {"status": "monitor"},
        "operational_risks": {"severity_score": 2},
        "intelligence_gaps": [],
        "data_freshness": {"feeds": {"detections": {"status": "fresh"}}},
        "intelligence_confidence": {"level": "high"},
        "operational_outlook": {
            "status": "steady_watch",
            "planning_horizon_hours": 10,
            "focus_areas": ["Northern corridor"],
        },
        "command_alignment": {"status": "aligned"},
    }

    matrix = intel_brief._derive_escalation_matrix(brief)

    assert matrix is not None
    assert matrix.get("status") in {"standby", "monitor"}
    assert matrix.get("readiness_score", 0) >= 70
    assert matrix.get("stability_factors")
    assert matrix.get("escalation_pathways")


def test_operational_recovery_builds_tracks_and_dependencies():
    brief = {
        "operational_continuity": {
            "status": "strained",
            "continuity_score": 62,
            "primary_constraints": ["Telemetry backlog"],
            "recommended_actions": ["Stabilise telemetry feeds"],
            "drivers": ["Data latency"],
            "continuity_horizon_hours": 12,
            "watch_items": ["Support coverage at risk"],
        },
        "operational_resilience": {
            "status": "vulnerable",
            "resilience_score": 58,
            "recommended_actions": ["Patch resilience weak spots"],
            "weak_spots": ["Aging sensors"],
            "reinforcing_factors": ["Dedicated crews"],
            "stability_window_hours": 6,
        },
        "mission_assurance": {
            "status": "at_risk",
            "assurance_score": 61,
            "recommended_actions": ["Resolve assurance blockers"],
            "drivers": ["Command alignment"],
            "focus_areas": ["Telemetry recovery"],
            "blockers": ["Pending directive approval"],
            "next_checkpoint_hours": 8,
        },
        "resource_sustainment": {
            "status": "accelerate",
            "resource_needs": ["Telemetry engineers", "Analyst surge team"],
            "recommended_actions": ["Stage reserve crews"],
            "allocation_plan": [{"resource": "Analyst team", "focus": "Night shift"}],
            "resupply_window_hours": 10,
        },
        "command_alignment": {
            "status": "at_risk",
            "recommended_actions": ["Schedule alignment huddle"],
            "drivers": ["Leadership sync"],
            "focus_areas": ["Command synchronisation"],
            "coordination_gaps": ["Comms vs support cadence"],
            "next_sync_hours": 5,
        },
        "command_directives": {
            "status": "accelerate",
            "recommended_actions": ["Issue recovery directive"],
            "coordination_teams": ["Command Liaison"],
            "focus_areas": ["Telemetry restart"],
            "planning_window_hours": 9,
        },
        "support_priorities": {
            "status": "reinforce",
            "recommended_actions": ["Mobilise telemetry support"],
            "priorities": [
                {
                    "team": "Telemetry Operations",
                    "reason": "Backfill outages",
                    "support_window_hours": 4,
                }
            ],
        },
        "response_readiness": {
            "level": "strained",
            "priority_actions": ["Sustain 24/7 triage"],
            "drivers": ["Staff attrition"],
            "support_window_hours": 6,
        },
        "response_pressure": {
            "status": "critical_backlog",
            "recommended_actions": ["Surge review crew"],
            "drivers": ["Prediction backlog"],
            "estimated_clearance_hours": 7,
        },
        "escalation_readiness": {
            "status": "prepare",
            "recommended_actions": ["Confirm escalation script"],
            "escalation_pathways": [{"name": "Crisis briefing", "priority": "immediate"}],
            "drivers": ["Telemetry gap"],
            "stability_factors": ["Rehearsed playbooks"],
            "next_review_hours": 3,
        },
        "operational_outlook": {
            "status": "rapid_response",
            "recommended_actions": ["Brief leadership on recovery"],
            "drivers": ["Tempo surge"],
            "focus_areas": ["Northern sector"],
            "planning_horizon_hours": 4,
        },
        "operational_risks": {
            "severity_score": 14,
            "recommended_actions": ["Track recovery risk register"],
            "focus_areas": ["Telemetry gap"],
            "next_review_hours": 11,
        },
        "contingency_plans": {
            "status": "ready",
            "recommended_actions": ["Prepare contingency rota"],
            "scenarios": [{"name": "Telemetry outage"}],
            "watch_items": ["Fallback to manual logging"],
            "activation_window_hours": 6,
        },
        "communication_plan": {
            "status": "reinforce",
            "recommended_actions": ["Push recovery updates"],
            "key_messages": ["Telemetry recovery underway"],
            "audiences": [{"focus": "Executive leadership"}],
            "update_cadence_minutes": 90,
        },
        "intelligence_confidence": {
            "level": "guarded",
            "recommended_actions": ["Validate telemetry inputs"],
            "drivers": ["Feedback variance"],
        },
        "data_freshness": {
            "feeds": {
                "predictions": {"status": "stale"},
                "detections": {"status": "warning"},
                "clusters": {"status": "fresh"},
            }
        },
        "intelligence_gaps": [
            {
                "gap": "feedback_accuracy",
                "severity": "major",
                "detail": "Feedback accuracy below target",
            }
        ],
    }

    recovery = intel_brief._derive_operational_recovery(brief)

    assert recovery is not None
    assert recovery.get("status") in {"stabilise", "recover", "rebuild", "sustain"}
    assert recovery.get("recovery_phase") in {"stabilisation", "recovery", "reconstitution", "stability"}
    dependencies = recovery.get("critical_dependencies", [])
    assert any("telemetry" in dep.lower() for dep in dependencies)
    tracks = recovery.get("recovery_tracks", [])
    assert isinstance(tracks, list) and len(tracks) >= 2
    actions = " ".join(recovery.get("recommended_actions", []))
    assert "recovery" in actions.lower()
    assert recovery.get("stabilisation_actions")


def test_operational_transformation_compiles_tracks_and_actions():
    brief = {
        "operational_recovery": {
            "status": "recover",
            "recovery_score": 62,
            "recovery_phase": "recovery",
            "critical_dependencies": ["Telemetry pipeline"],
            "stabilisation_actions": ["Stage telemetry restart crew"],
            "recommended_actions": ["Complete telemetry hardening"],
            "momentum_factors": ["Leadership oversight engaged"],
            "insight_drivers": ["Telemetry gap"],
            "recovery_tracks": [
                {
                    "name": "Continuity stabilisation",
                    "status": "recover",
                    "owner": "Operations",
                    "focus": "Telemetry services",
                    "actions": ["Bring sensors online"],
                }
            ],
            "watch_items": ["Manual logging gap"],
            "recovery_window_hours": 6,
        },
        "operational_continuity": {
            "status": "strained",
            "primary_constraints": ["Sensor backlog"],
            "recommended_actions": ["Expand manual verification"],
            "watch_items": ["Support coverage at risk"],
            "drivers": ["Data latency"],
            "continuity_horizon_hours": 12,
        },
        "operational_resilience": {
            "status": "vulnerable",
            "resilience_score": 58,
            "recommended_actions": ["Audit failover capacity"],
            "reinforcing_factors": ["Dedicated crews"],
            "weak_spots": ["Aging sensors"],
            "stability_window_hours": 8,
        },
        "mission_assurance": {
            "status": "at_risk",
            "recommended_actions": ["Confirm mission-critical approvals"],
            "focus_areas": ["Telemetry restart"],
            "drivers": ["Pending directive"],
            "blockers": ["Approval backlog"],
            "next_checkpoint_hours": 5,
        },
        "resource_sustainment": {
            "status": "accelerate",
            "resource_needs": ["Telemetry engineers"],
            "recommended_actions": ["Backfill telemetry"],
            "allocation_plan": [
                {
                    "resource": "Telemetry team",
                    "focus": "Recovery shift",
                    "owner": "Support",
                    "action": "Stage overnight coverage",
                }
            ],
            "resupply_window_hours": 10,
        },
        "command_alignment": {
            "status": "accelerate",
            "coordination_gaps": ["Support vs comms cadence"],
            "recommended_actions": ["Schedule alignment huddle"],
            "focus_areas": ["Command sync"],
            "next_sync_hours": 4,
        },
        "command_directives": {
            "status": "accelerate",
            "severity": 14,
            "recommended_actions": ["Issue recovery directive"],
            "focus_areas": ["Telemetry restoration"],
            "coordination_teams": ["Command Liaison"],
            "planning_window_hours": 3,
        },
        "support_priorities": {
            "status": "mobilise",
            "recommended_actions": ["Mobilise telemetry support"],
            "priorities": [
                {
                    "team": "Telemetry Ops",
                    "reason": "Sensor outages",
                    "support_window_hours": 3,
                    "follow_up": "Stage reserve crew",
                }
            ],
        },
        "response_readiness": {
            "level": "strained",
            "priority_actions": ["Sustain 24/7 triage"],
            "drivers": ["Staff attrition"],
            "support_window_hours": 6,
        },
        "response_pressure": {
            "status": "critical_backlog",
            "recommended_actions": ["Surge review crew"],
            "drivers": ["Prediction backlog"],
            "estimated_clearance_hours": 7,
        },
        "operational_outlook": {
            "status": "rapid_response",
            "severity_score": 12,
            "focus_areas": ["Northern sector"],
            "recommended_actions": ["Plan next-phase recovery"],
            "drivers": ["Tempo surge"],
            "planning_horizon_hours": 9,
        },
        "operational_risks": {
            "status": "escalated",
            "severity_score": 15,
            "recommended_actions": ["Mitigate telemetry risk"],
            "focus_areas": ["Telemetry gap"],
            "risks": [{"name": "Telemetry gap", "detail": "Sensor outage", "severity": 4}],
            "next_review_hours": 8,
        },
        "communication_plan": {
            "status": "heightened",
            "recommended_actions": ["Push recovery updates"],
            "key_messages": ["Telemetry recovery underway"],
            "audiences": [{"focus": "Leadership"}],
            "update_cadence_minutes": 90,
        },
        "contingency_plans": {
            "status": "prepare",
            "recommended_actions": ["Activate fallback plan"],
            "scenarios": [{"name": "Telemetry outage"}],
            "watch_items": ["Fallback to manual logging"],
            "activation_window_hours": 5,
        },
        "intelligence_confidence": {
            "level": "guarded",
            "drivers": ["Feedback variance"],
            "recommended_actions": ["Validate telemetry inputs"],
        },
        "health": {
            "risk_level": "high",
            "recommended_actions": ["Stabilise telemetry backlog"],
            "reinforcing_factors": ["Ops-support partnership"],
        },
    }

    transformation = intel_brief._derive_operational_transformation(brief)

    assert transformation is not None
    assert transformation.get("status") in {"advancing", "progressing", "watch", "intervene"}
    assert transformation.get("maturity_stage") in {
        "optimisation",
        "integration",
        "recovery_bridge",
        "stabilisation",
        "reset",
    }
    assert transformation.get("focus_tracks")
    assert any("telemetry" in item.lower() for item in transformation.get("constraints", []))
    assert any("telemetry" in item.lower() for item in transformation.get("recommended_actions", []))
    assert transformation.get("quick_wins")
    assert transformation.get("long_horizon_initiatives")
    assert transformation.get("watch_indicators")


def test_operational_governance_scores_alignment_and_risks():
    brief = {
        "operational_transformation": {
            "status": "progressing",
            "transformation_score": 72,
            "transformation_focus": ["Telemetry recovery"],
            "recommended_actions": ["Align command cell"],
            "constraints": ["Data gap"],
            "next_review_hours": 6.0,
            "enablers": ["Telemetry recovery"],
        },
        "operational_recovery": {
            "status": "recover",
            "recovery_score": 60,
            "recommended_actions": ["Stabilise telemetry"],
            "insight_drivers": ["Telemetry backlog"],
            "critical_dependencies": ["Sensor ingest"],
            "watch_items": ["Cluster sync"],
            "recovery_window_hours": 10.0,
        },
        "operational_continuity": {
            "status": "constrained",
            "continuity_score": 58,
            "primary_constraints": ["Telemetry throughput"],
            "recommended_actions": ["Expand pipeline"],
            "continuity_horizon_hours": 12.0,
        },
        "operational_resilience": {
            "status": "fragile",
            "resilience_score": 52,
            "weak_spots": ["Telemetry operators"],
            "recommended_actions": ["Hardening plan"],
            "stability_window_hours": 9.0,
        },
        "mission_assurance": {
            "status": "strained",
            "assurance_score": 57,
            "blockers": ["Telemetry outages"],
            "recommended_actions": ["Command review"],
            "drivers": ["Telemetry risk"],
            "next_checkpoint_hours": 4.0,
        },
        "resource_sustainment": {
            "status": "reinforce",
            "resource_needs": [
                {"name": "Telemetry crew", "support_window_hours": 8.0},
            ],
            "recommended_actions": ["Mobilise telemetry"],
        },
        "command_alignment": {
            "status": "accelerate",
            "alignment_score": 62,
            "focus_areas": ["Telemetry recovery"],
            "drivers": ["Gaps"],
            "coordination_gaps": ["Telemetry/ops"],
            "recommended_actions": ["Sync ops"],
            "next_sync_hours": 3.0,
        },
        "command_directives": {
            "status": "accelerate",
            "focus_areas": ["Telemetry"],
            "drivers": ["Leadership push"],
            "recommended_actions": ["Issue directive"],
            "planning_window_hours": 2.0,
        },
        "communication_plan": {
            "status": "heightened",
            "key_messages": ["Telemetry status"],
            "recommended_actions": ["Brief leadership"],
            "audiences": [{"audience": "Command", "cadence_hours": 6.0}],
        },
        "operational_risks": {
            "severity_score": 82,
            "risk_count": 2,
            "risks": [
                {
                    "name": "Telemetry",
                    "severity": 4,
                    "status": "critical",
                    "review_window_hours": 5.0,
                }
            ],
            "recommended_actions": ["Review risk"],
        },
        "support_priorities": {
            "status": "mobilise",
            "drivers": ["Telemetry"],
            "recommended_actions": ["Deploy ops"],
            "priorities": [
                {"name": "Telemetry", "support_window_hours": 7.0},
            ],
        },
        "response_readiness": {
            "level": "critical",
            "drivers": ["Coverage dip"],
            "priority_actions": ["Add analysts"],
            "support_window_hours": 5.0,
        },
        "response_pressure": {
            "status": "critical_backlog",
            "drivers": ["Queue"],
            "recommended_actions": ["Triage backlog"],
            "estimated_clearance_hours": 11.0,
        },
        "contingency_plans": {
            "status": "prepare",
            "scenarios": [{"name": "Telemetry fail", "review_window_hours": 9.0}],
            "recommended_actions": ["Spin up backup"],
        },
        "operational_outlook": {
            "status": "escalation_imminent",
            "severity": 80,
            "focus_areas": ["Telemetry"],
            "drivers": ["Risk"],
            "recommended_actions": ["Escalate"],
            "planning_horizon_hours": 6.0,
        },
        "escalation_readiness": {
            "status": "accelerate",
            "focus_areas": ["Telemetry"],
            "drivers": ["Signals"],
            "recommended_actions": ["Prep escalation"],
            "next_review_hours": 4.0,
        },
    }

    governance = intel_brief._derive_operational_governance(brief)

    assert governance is not None
    assert governance.get("status") == "fragmented"
    assert governance.get("governance_score") == 0
    assert governance.get("oversight_councils") and len(governance["oversight_councils"]) == 4
    assert "Telemetry recovery" in governance.get("oversight_focus", [])
    assert "High-severity risks awaiting review" in governance.get("compliance_gaps", [])
    assert any("Risk:" in item for item in governance.get("watch_items", []))
    assert governance.get("next_review_hours") == pytest.approx(2.0)
    assert "Align command cell" in governance.get("recommended_actions", [])


def test_gather_brief_includes_operational_governance(monkeypatch):
    now = datetime(2024, 7, 10, 6, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        intel_brief,
        "meta_analysis",
        lambda hours: {"detections": {}, "feedback_accuracy": 0.8, "cluster_count": 0},
    )

    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_recovery",
        lambda brief: {
            "status": "recover",
            "recovery_score": 68,
            "insight_drivers": ["Telemetry"],
            "recommended_actions": ["Close dependency"],
            "critical_dependencies": ["Telemetry feed"],
            "recovery_window_hours": 8.0,
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_continuity",
        lambda brief: {
            "status": "steady",
            "continuity_score": 72,
            "primary_constraints": ["Bandwidth"],
            "recommended_actions": ["Maintain pipeline"],
            "continuity_horizon_hours": 12.0,
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_resilience",
        lambda brief: {
            "status": "resilient",
            "resilience_score": 78,
            "weak_spots": ["Sensor ops"],
            "recommended_actions": ["Audit sensors"],
            "stability_window_hours": 9.0,
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_mission_assurance",
        lambda brief: {
            "status": "steady",
            "assurance_score": 74,
            "recommended_actions": ["Review mission"],
            "drivers": ["Tempo"],
            "next_checkpoint_hours": 6.0,
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_resource_sustainment",
        lambda brief: {
            "status": "reinforce",
            "drivers": ["Logistics support"],
            "recommended_actions": ["Add shift"],
            "resource_needs": [{"name": "Ops team", "support_window_hours": 10.0}],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_command_alignment",
        lambda brief: {
            "status": "focus",
            "alignment_score": 76,
            "focus_areas": ["Telemetry"],
            "drivers": ["Ops sync"],
            "coordination_gaps": ["Telemetry vs Ops"],
            "recommended_actions": ["Schedule sync"],
            "next_sync_hours": 4.0,
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_command_directives",
        lambda brief: {
            "status": "focus",
            "focus_areas": ["Telemetry"],
            "drivers": ["Ops"],
            "recommended_actions": ["Publish guidance"],
            "planning_window_hours": 3.0,
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_communication_plan",
        lambda brief: {
            "status": "focused",
            "key_messages": ["Telemetry sync"],
            "recommended_actions": ["Brief ops"],
            "audiences": [{"audience": "Ops", "cadence_hours": 6.0}],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_risk_register",
        lambda brief: {
            "status": "elevated",
            "severity_score": 68,
            "risk_count": 1,
            "risks": [
                {
                    "name": "Telemetry",
                    "severity": 3,
                    "status": "monitor",
                    "review_window_hours": 5.0,
                }
            ],
            "recommended_actions": ["Track risk"],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_support_priorities",
        lambda brief: {
            "status": "reinforce",
            "drivers": ["Ops support"],
            "recommended_actions": ["Mobilise ops"],
            "priorities": [{"name": "Ops", "support_window_hours": 7.0}],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_response_readiness",
        lambda brief: {
            "level": "strained",
            "drivers": ["Coverage"],
            "priority_actions": ["Add coverage"],
            "support_window_hours": 6.0,
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_response_pressure",
        lambda brief: {
            "status": "backlog",
            "drivers": ["Queue"],
            "recommended_actions": ["Clear queue"],
            "estimated_clearance_hours": 8.0,
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_contingency_plans",
        lambda brief: {
            "status": "prepare",
            "scenarios": [{"name": "Telemetry fail", "review_window_hours": 9.0}],
            "recommended_actions": ["Prep contingency"],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_outlook",
        lambda brief: {
            "status": "heightened_watch",
            "severity": 68,
            "focus_areas": ["Telemetry"],
            "drivers": ["Tempo"],
            "recommended_actions": ["Align plan"],
            "planning_horizon_hours": 6.0,
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_transformation",
        lambda brief: {
            "status": "progressing",
            "transformation_score": 78,
            "transformation_focus": ["Telemetry"],
            "recommended_actions": ["Align command cell"],
            "constraints": ["Telemetry backlog"],
            "next_review_hours": 6.0,
            "enablers": ["Ops support"],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_escalation_matrix",
        lambda brief: {
            "status": "monitor",
            "focus_areas": ["Telemetry"],
            "drivers": ["Signals"],
            "recommended_actions": ["Monitor escalation"],
            "next_review_hours": 7.0,
        },
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    governance = brief.get("operational_governance")
    assert governance is not None
    assert governance.get("status") == "watch"
    assert governance.get("governance_score") == 60
    assert governance.get("next_review_hours") == pytest.approx(3.0)
    assert governance.get("oversight_councils") and len(governance["oversight_councils"]) == 4

    insight = brief.get("insights", {}).get("operational_governance", {})
    assert insight.get("status") == governance.get("status")
    assert insight.get("score") == governance.get("governance_score")
    assert insight.get("council_count") == len(governance.get("oversight_councils", []))
    assert insight.get("gap_count") == len(governance.get("compliance_gaps", []))

    recommendations = brief.get("recommendations", [])
    assert "Align command cell" in recommendations
    assert any("Mobilise ops" in rec for rec in recommendations)


def test_gather_intelligence_brief_builds_communication_plan(monkeypatch):
    now = datetime(2024, 9, 10, 8, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)

    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {"detections": {"troop": {"count": 5, "avg_conf": 0.82}}})
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])

    monkeypatch.setattr(
        intel_brief,
        "_summarise_freshness",
        lambda **kwargs: {
            "feeds": {
                "detections": {"status": "warning"},
                "predictions": {"status": "stale"},
            }
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_brief_health",
        lambda brief: {"risk_level": "high"},
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_posture",
        lambda brief: {"status": "recover", "focus": "Restore telemetry", "horizon_hours": 2.0},
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_response_readiness",
        lambda brief: {
            "level": "critical",
            "support_window_hours": 1.5,
            "priority_actions": ["Stage rapid response teams."],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_response_pressure",
        lambda brief: {
            "severity": 2,
            "status": "critical_backlog",
            "recommended_actions": ["Deploy surge analysts."],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_support_priorities",
        lambda brief: {"status": "mobilise", "priorities": []},
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_intelligence_confidence",
        lambda brief: {"level": "low"},
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_intelligence_gaps",
        lambda brief: [{"gap": "predictions", "severity": "major"}],
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_outlook",
        lambda brief: {
            "status": "rapid_response",
            "severity_score": 10,
            "focus_areas": ["Telemetry recovery"],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_command_directives",
        lambda brief: {
            "severity": 14,
            "status": "accelerate",
            "drivers": ["Telemetry feeds require leadership direction."],
            "focus_areas": ["Telemetry recovery"],
            "planning_window_hours": 1.0,
        },
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    plan = brief.get("communication_plan")
    assert plan is not None
    assert plan.get("status") in {"heightened", "focused", "escalated"}
    assert brief.get("insights", {}).get("communication_plan", {}).get("audience_count") == len(
        plan.get("audiences", [])
    )
    assert any("leadership" in rec.lower() for rec in brief.get("recommendations", []))
    assert any(entry.get("audience") for entry in plan.get("audiences", []))
    contingency = brief.get("contingency_plans")
    assert contingency is not None
    assert contingency.get("status") in {"prepare", "ready", "activate"}
    assert contingency.get("scenarios")
    insight = brief.get("insights", {}).get("contingency_plans", {})
    assert insight.get("scenario_count") == len(contingency.get("scenarios", []))
    assert any("surge" in rec.lower() for rec in brief.get("recommendations", []))
    sustainment = brief.get("resource_sustainment")
    assert sustainment is not None
    assert sustainment.get("status") in {"reinforce", "accelerate", "surge"}
    sustainment_insight = brief.get("insights", {}).get("resource_sustainment", {})
    assert sustainment_insight.get("status") == sustainment.get("status")
    assert sustainment_insight.get("needs") == len(sustainment.get("resource_needs", []))
    assert any("telemetry" in rec.lower() for rec in brief.get("recommendations", []))
    risk_register = brief.get("operational_risks")
    assert risk_register is not None
    assert risk_register.get("status") in {"critical", "escalated", "elevated"}
    risk_insight = brief.get("insights", {}).get("operational_risks", {})
    assert risk_insight.get("risk_count") == risk_register.get("risk_count")
    assert risk_insight.get("status") == risk_register.get("status")
    assert risk_insight.get("severity_score") == risk_register.get("severity_score")
    assert any("risk" in rec.lower() for rec in brief.get("recommendations", []))

    transformation = brief.get("operational_transformation")
    assert transformation is not None
    assert transformation.get("status")
    insight = brief.get("insights", {}).get("operational_transformation", {})
    assert insight.get("status") == transformation.get("status")
    assert insight.get("score") == transformation.get("transformation_score")
    if transformation.get("quick_wins"):
        assert insight.get("quick_wins") == len(transformation.get("quick_wins", []))
    if transformation.get("long_horizon_initiatives"):
        assert insight.get("initiatives") == len(transformation.get("long_horizon_initiatives", []))
    for action in transformation.get("recommended_actions", []):
        assert action in brief.get("recommendations", [])


def test_gather_intelligence_brief_includes_frontline_support(monkeypatch):
    now = datetime(2024, 9, 11, 12, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(
        intel_brief,
        "meta_analysis",
        lambda hours: {"detections": {"troop": {"count": 1, "avg_conf": 0.6}}},
    )
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(
        intel_brief,
        "_summarise_freshness",
        lambda **kwargs: {
            "feeds": {
                "detections": {"status": "warning", "age_minutes": 65},
                "predictions": {"status": "stale", "age_minutes": 120},
            },
            "stalest_feed": "predictions",
            "worst_case_minutes": 120,
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_intelligence_gaps",
        lambda brief: [
            {
                "name": "FPV resupply telemetry",
                "severity": "critical",
                "recommended_action": "Synchronise FPV inventory feeds with logistics.",
            }
        ],
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_support_priorities",
        lambda brief: {
            "status": "mobilise",
            "recommended_actions": ["Escalate fires resupply coordination."],
            "priorities": [
                {
                    "name": "3rd Assault Brigade",
                    "focus": "Donetsk corridor",
                    "support_window_hours": 4.0,
                }
            ],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_response_readiness",
        lambda brief: {
            "level": "critical",
            "support_window_hours": 4.5,
            "priority_actions": ["Extend analyst coverage for fires queues."],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_response_pressure",
        lambda brief: {
            "status": "critical_backlog",
            "estimated_clearance_hours": 6.0,
            "drivers": ["Prediction backlog"],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_resource_sustainment",
        lambda brief: {
            "status": "surge",
            "resupply_window_hours": 4.5,
            "recommended_actions": ["Deploy ammunition convoy to eastern axis."],
            "allocation_plan": [
                {
                    "resource": "155mm shells",
                    "priority": "immediate",
                    "focus": "3rd Assault Brigade",
                    "quantity": 3,
                    "window_hours": 4.0,
                }
            ],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_continuity",
        lambda brief: {
            "status": "constrained",
            "continuity_score": 54,
            "primary_constraints": ["Logistics corridor capacity"],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_resilience",
        lambda brief: {
            "status": "fragile",
            "resilience_score": 58,
            "weak_spots": ["Ammunition stockpiles"],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_recovery",
        lambda brief: {"status": "recover", "recovery_score": 60},
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_outlook",
        lambda brief: {"status": "heightened_watch", "severity": 72},
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_risk_register",
        lambda brief: {
            "status": "elevated",
            "severity_score": 80,
            "risk_count": 1,
            "risks": [
                {
                    "name": "Fires resupply",
                    "severity": 4,
                    "status": "monitor",
                    "review_window_hours": 6.0,
                }
            ],
            "recommended_actions": ["Review sustainment risk with command."],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_mission_assurance",
        lambda brief: {"status": "strained", "assurance_score": 55},
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_command_alignment",
        lambda brief: {
            "status": "drift",
            "alignment_score": 54,
            "recommended_actions": ["Sync operations and sustainment cells."],
        },
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_operational_transformation",
        lambda brief: {"status": "watch", "transformation_score": 60},
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    frontline = brief.get("frontline_support")
    assert frontline is not None
    assert frontline.get("status") in {"mobilise", "critical"}
    assert frontline.get("priority_units")
    assert frontline.get("ukrainian_operator_notes")

    insight = brief.get("insights", {}).get("frontline_support", {})
    assert insight.get("status") == frontline.get("status")
    assert insight.get("priority_unit_count") == len(frontline.get("priority_units", []))
    assert insight.get("coordination_window_hours") == frontline.get("coordination_window_hours")

    recommendations = brief.get("recommendations", [])
    assert any("Joint Forces" in rec for rec in recommendations)
    assert any("logistics" in rec.lower() or "resupply" in rec.lower() for rec in recommendations)

    automation = brief.get("automation_playbook")
    assert automation is not None
    assert automation.get("status")
    assert isinstance(automation.get("automation_score"), (int, float))
    insight = brief.get("insights", {}).get("automation_playbook", {})
    assert insight.get("status") == automation.get("status")
    if automation.get("automation_tasks"):
        assert insight.get("task_count") == len(automation.get("automation_tasks", []))
    window = automation.get("automation_window_hours")
    if isinstance(window, (float, int)):
        assert insight.get("automation_window_hours") == window
    prompts = automation.get("ukrainian_operator_prompts", [])
    assert prompts and any("журн" in prompt.lower() or "перевір" in prompt.lower() for prompt in prompts)


def test_gather_intelligence_brief_adds_automation_guardrails(monkeypatch):
    now = datetime(2024, 9, 13, 8, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    automation_payload = {
        "status": "guided",
        "automation_score": 68,
        "automation_tasks": [
            {
                "task": "Queue daily automation brief",
                "mode": "guided",
                "owner": "Automation Cell",
                "window_hours": 3.0,
            }
        ],
        "recommended_actions": ["Review automation guardrails at shift turnover."],
    }
    guardrail_payload = {
        "status": "manual_guarded",
        "autonomy_score": 62.5,
        "guardrails": ["Duty officer approval required for automation runs."],
        "next_review_hours": 3.0,
        "recommended_actions": ["Guard automation handoff with Ukrainian oversight."],
    }

    monkeypatch.setattr(
        intel_brief, "_derive_automation_playbook", lambda brief: automation_payload
    )
    monkeypatch.setattr(
        intel_brief, "_derive_automation_guardrails", lambda brief: guardrail_payload
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    guardrails = brief.get("automation_guardrails")
    assert guardrails == guardrail_payload
    insight = brief.get("insights", {}).get("automation_guardrails", {})
    assert insight.get("status") == guardrail_payload["status"]
    assert insight.get("score") == guardrail_payload["autonomy_score"]
    assert insight.get("guardrail_count") == len(guardrail_payload["guardrails"])
    assert insight.get("next_review_hours") == guardrail_payload["next_review_hours"]
    recommendations = brief.get("recommendations", [])
    assert any("Ukrainian oversight" in rec for rec in recommendations)


def test_gather_intelligence_brief_adds_automation_mission_control(monkeypatch):
    now = datetime(2024, 9, 13, 8, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    automation_payload = {"status": "autonomous", "automation_score": 86}
    guardrail_payload = {"status": "guided", "autonomy_score": 72}
    mission_control_payload = {
        "status": "supervised",
        "mission_control_score": 78.5,
        "next_sync_hours": 2.0,
        "supervision_level": "supervised",
        "recommended_actions": ["Log automation mission control summary for Ukrainian operators."],
    }

    monkeypatch.setattr(
        intel_brief, "_derive_automation_playbook", lambda brief: automation_payload
    )
    monkeypatch.setattr(
        intel_brief, "_derive_automation_guardrails", lambda brief: guardrail_payload
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_automation_mission_control",
        lambda brief: mission_control_payload,
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    mission_control = brief.get("automation_mission_control")
    assert mission_control == mission_control_payload
    insight = brief.get("insights", {}).get("automation_mission_control", {})
    assert insight.get("status") == mission_control_payload["status"]
    assert insight.get("score") == mission_control_payload["mission_control_score"]
    assert insight.get("next_sync_hours") == mission_control_payload["next_sync_hours"]
    assert insight.get("supervision_level") == mission_control_payload["supervision_level"]
    recommendations = brief.get("recommendations", [])
    assert any("mission control summary" in rec.lower() for rec in recommendations)


def test_automation_autonomy_restricts_under_manual_conditions():
    brief: Dict[str, Any] = {
        "automation_playbook": {"status": "manual_override", "automation_score": 52},
        "automation_guardrails": {
            "status": "locked_down",
            "autonomy_score": 45,
            "next_review_hours": 2.0,
            "monitoring_channels": ["Ops Net"],
            "ukrainian_checklist": ["Перевіряйте автоматизацію вручну."],
        },
        "automation_mission_control": {
            "status": "manual_control",
            "mission_control_score": 58,
            "next_sync_hours": 1.5,
            "recommended_actions": ["Brief leadership on manual automation posture."],
        },
        "response_readiness": {"level": "critical", "support_window_hours": 1.0},
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 6.0,
        },
        "frontline_support": {"status": "mobilise"},
        "resource_sustainment": {"status": "surge"},
        "support_priorities": {"status": "mobilise"},
        "operational_governance": {"status": "degraded"},
        "command_alignment": {"status": "misaligned"},
        "command_directives": {"status": "escalate"},
        "communication_plan": {"status": "crisis"},
        "mission_assurance": {"assurance_score": 48},
        "operational_resilience": {"resilience_score": 50},
        "operational_continuity": {"continuity_score": 52},
        "operational_recovery": {"recovery_score": 54},
        "operational_transformation": {"transformation_score": 48},
        "operational_outlook": {"status": "escalate"},
        "escalation_readiness": {"status": "escalate", "next_review_hours": 4.0},
        "intelligence_confidence": {"level": "low"},
        "detection_quality": {"weighted_avg_confidence": 0.48},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "stale", "age_minutes": 210},
                "predictions": {"status": "warning", "age_minutes": 120},
            }
        },
        "operational_risks": {"severity_score": 88},
        "intelligence_gaps": [
            {"severity": "critical", "description": "Telemetry automation gap"}
        ],
        "meta": {"feedback_accuracy": 0.5},
    }

    autonomy = intel_brief._derive_automation_autonomy(brief)
    assert autonomy is not None
    assert autonomy.get("status") == "manual_only"
    assert autonomy.get("autonomy_score") < 60
    safeguards = " ".join(autonomy.get("ukrainian_safeguards", []))
    assert "Фіксуйте" in safeguards or "Затверджуйте" in safeguards
    fallback = autonomy.get("fallback_protocols", [])
    assert any("Duty officer" in step or "override" in step for step in fallback)
    actions = " ".join(autonomy.get("recommended_actions", []))
    assert "autonomy status" in actions.lower()
    risk_factors = " ".join(autonomy.get("risk_factors", []))
    assert "guardrails" in risk_factors.lower() or "backlog" in risk_factors.lower()


def test_automation_autonomy_identifies_trusted_tasks_when_ready():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "autonomous",
            "automation_score": 90,
            "automation_tasks": [
                {
                    "task": "Dispatch readiness bulletin",
                    "mode": "automated",
                    "owner": "Automation Cell",
                    "window_hours": 3.0,
                },
                {
                    "task": "Coordinate manual review",
                    "mode": "guided",
                    "owner": "Duty Officer",
                    "window_hours": 2.0,
                },
            ],
            "automation_tracks": ["Ops automation"],
            "recommended_actions": [
                "Share automation confidence summary with Ukrainian shift lead.",
            ],
            "monitoring_channels": ["Automation Ops Room"],
        },
        "automation_guardrails": {
            "status": "autonomous",
            "autonomy_score": 92,
            "monitoring_channels": ["Ops Guardrail Net"],
            "recommended_actions": ["Refresh guardrail approvals at end of shift."],
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "mission_control_score": 88,
            "supervision_level": "mission_ready",
            "mission_channels": ["Mission Control Net"],
            "recommended_actions": ["Archive mission control summary."],
        },
        "response_readiness": {"level": "reinforced", "support_window_hours": 6.0},
        "response_pressure": {"status": "cleared", "estimated_clearance_hours": 8.0},
        "frontline_support": {"status": "steady"},
        "resource_sustainment": {"status": "steady"},
        "support_priorities": {"status": "steady"},
        "operational_governance": {"status": "steady"},
        "command_alignment": {"status": "aligned"},
        "command_directives": {"status": "synchronise"},
        "communication_plan": {"status": "stabilise"},
        "mission_assurance": {"assurance_score": 82},
        "operational_resilience": {"resilience_score": 80},
        "operational_continuity": {"continuity_score": 78},
        "operational_recovery": {"recovery_score": 76},
        "operational_transformation": {"transformation_score": 84},
        "operational_outlook": {"status": "steady"},
        "escalation_readiness": {"status": "monitor", "next_review_hours": 12.0},
        "intelligence_confidence": {"level": "high"},
        "detection_quality": {"weighted_avg_confidence": 0.78},
        "data_freshness": {"feeds": {"detections": {"status": "fresh", "age_minutes": 15}}},
        "operational_risks": {"severity_score": 40},
        "intelligence_gaps": [],
        "meta": {"feedback_accuracy": 0.9},
    }

    autonomy = intel_brief._derive_automation_autonomy(brief)
    assert autonomy is not None
    assert autonomy.get("status") == "autonomous_ready"
    assert autonomy.get("autonomy_score") >= 80
    assert autonomy.get("autonomy_window_hours") == pytest.approx(0.25, rel=1e-3)
    trusted = autonomy.get("trusted_tasks", [])
    assert any("Dispatch readiness bulletin" in task for task in trusted)
    restricted = autonomy.get("restricted_tasks", [])
    assert any("guided" in task.lower() for task in restricted)
    enablers = " ".join(autonomy.get("autonomy_enablers", []))
    assert "readiness" in enablers.lower() or "guardrails" in enablers.lower()
    monitoring = autonomy.get("monitoring_requirements", [])
    assert any("Mission Control Net" in channel for channel in monitoring)


def test_gather_intelligence_brief_adds_automation_autonomy(monkeypatch):
    now = datetime(2024, 9, 13, 8, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    monkeypatch.setattr(
        intel_brief, "_derive_automation_playbook", lambda brief: {"status": "autonomous"}
    )
    monkeypatch.setattr(
        intel_brief, "_derive_automation_guardrails", lambda brief: {"status": "pilot"}
    )
    monkeypatch.setattr(
        intel_brief,
        "_derive_automation_mission_control",
        lambda brief: {"status": "supervised", "mission_control_score": 70},
    )

    autonomy_payload = {
        "status": "mission_ready",
        "autonomy_score": 78.2,
        "autonomy_window_hours": 2.5,
        "trusted_tasks": ["Dispatch readiness bulletin (automated)"],
        "recommended_actions": [
            "Publish automation autonomy status to the Ukrainian operations dashboard each shift."
        ],
    }
    monkeypatch.setattr(
        intel_brief, "_derive_automation_autonomy", lambda brief: autonomy_payload
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    autonomy = brief.get("automation_autonomy")
    assert autonomy == autonomy_payload
    insight = brief.get("insights", {}).get("automation_autonomy", {})
    assert insight.get("status") == autonomy_payload["status"]
    assert insight.get("score") == autonomy_payload["autonomy_score"]
    assert insight.get("autonomy_window_hours") == autonomy_payload["autonomy_window_hours"]
    assert insight.get("trusted_task_count") == len(autonomy_payload["trusted_tasks"])
    recommendations = brief.get("recommendations", [])
    assert any("autonomy status" in rec.lower() for rec in recommendations)


def test_automation_failsafes_flags_manual_conditions():
    brief: Dict[str, Any] = {
        "automation_playbook": {"status": "manual_override"},
        "automation_guardrails": {"status": "locked_down", "next_review_hours": 2.0},
        "automation_mission_control": {"status": "manual_control", "next_sync_hours": 1.0},
        "automation_autonomy": {
            "status": "manual_control",
            "autonomy_window_hours": 1.0,
        },
        "response_readiness": {"level": "critical", "support_window_hours": 0.5},
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 6.0,
        },
        "data_freshness": {
            "feeds": {"detections": {"status": "stale", "age_minutes": 120}}
        },
        "intelligence_confidence": {"level": "low"},
        "detection_quality": {"weighted_avg_confidence": 0.42},
        "intelligence_gaps": [{"name": "Telemetry sync", "severity": "critical"}],
        "operational_risks": {"severity_score": 90},
    }

    failsafes = intel_brief._derive_automation_failsafes(brief)
    assert failsafes is not None
    assert failsafes.get("status") == "manual_recovery"
    assert failsafes.get("failsafe_score") and failsafes["failsafe_score"] < 55
    prompts = failsafes.get("ukrainian_operator_prompts", [])
    assert any("журнал" in prompt.lower() or "резерв" in prompt.lower() for prompt in prompts)
    actions = failsafes.get("recommended_actions", [])
    assert any("failsafe" in action.lower() for action in actions)


def test_automation_failsafes_confirms_secured_posture():
    brief: Dict[str, Any] = {
        "automation_guardrails": {
            "status": "autonomous",
            "next_review_hours": 6.0,
            "monitoring_channels": ["Ops Net"],
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "next_sync_hours": 4.0,
        },
        "automation_autonomy": {
            "status": "mission_ready",
            "autonomy_window_hours": 6.0,
        },
        "response_readiness": {"level": "reinforced", "support_window_hours": 8.0},
        "response_pressure": {
            "status": "cleared",
            "estimated_clearance_hours": 2.0,
        },
        "operational_governance": {"governance_score": 80},
        "mission_assurance": {"assurance_score": 78},
        "operational_resilience": {"resilience_score": 82},
        "operational_continuity": {"continuity_score": 84},
        "operational_transformation": {"transformation_score": 78},
        "intelligence_confidence": {"level": "high"},
        "data_freshness": {
            "feeds": {"detections": {"status": "fresh", "age_minutes": 10}}
        },
    }

    failsafes = intel_brief._derive_automation_failsafes(brief)
    assert failsafes is not None
    assert failsafes.get("status") == "secured"
    assert failsafes.get("failsafe_score") and failsafes["failsafe_score"] >= 85
    channels = failsafes.get("fallback_channels", [])
    assert any("ops" in channel.lower() for channel in channels)


def test_gather_intelligence_brief_adds_automation_failsafes(monkeypatch):
    now = datetime(2024, 9, 14, 9, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    monkeypatch.setattr(intel_brief, "_derive_automation_playbook", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_guardrails", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_mission_control", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_autonomy", lambda brief: {})
    monkeypatch.setattr(
        intel_brief, "_derive_automation_strategic_convergence", lambda brief: {}
    )

    failsafe_payload = {
        "status": "watch",
        "failsafe_score": 72.5,
        "failsafe_window_hours": 2.5,
        "failsafe_tests": ["Drill guardrail shutdown"],
        "recommended_actions": ["Escalate failsafe summary to Ukrainian duty officer."],
    }

    monkeypatch.setattr(
        intel_brief, "_derive_automation_failsafes", lambda brief: failsafe_payload
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    failsafes = brief.get("automation_failsafes")
    assert failsafes == failsafe_payload

    insight = brief.get("insights", {}).get("automation_failsafes", {})
    assert insight.get("status") == failsafe_payload["status"]
    assert insight.get("score") == failsafe_payload["failsafe_score"]
    assert insight.get("failsafe_window_hours") == failsafe_payload["failsafe_window_hours"]
    assert insight.get("test_count") == len(failsafe_payload["failsafe_tests"])

    recommendations = brief.get("recommendations", [])
    assert any("failsafe" in rec.lower() for rec in recommendations)


def test_automation_validation_flags_manual_conditions():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "manual_override",
            "automation_window_hours": 1.0,
            "monitoring_channels": ["Ops Chat"],
        },
        "automation_guardrails": {"status": "locked_down", "next_review_hours": 1.0},
        "automation_mission_control": {
            "status": "manual_control",
            "next_sync_hours": 2.0,
        },
        "automation_autonomy": {
            "status": "manual_control",
            "autonomy_window_hours": 1.0,
        },
        "automation_failsafes": {
            "status": "manual_recovery",
            "failsafe_window_hours": 0.5,
        },
        "response_readiness": {"level": "critical", "support_window_hours": 0.75},
        "response_pressure": {"status": "critical_backlog"},
        "frontline_support": {"status": "critical"},
        "resource_sustainment": {"status": "strained"},
        "support_priorities": {
            "priorities": [
                {"name": "Signals", "support_window_hours": 1.5},
            ]
        },
        "operational_governance": {"status": "strained", "governance_score": 55},
        "mission_assurance": {"assurance_score": 50},
        "operational_resilience": {"resilience_score": 55},
        "operational_continuity": {"continuity_score": 58},
        "operational_recovery": {"recovery_score": 50},
        "operational_transformation": {"transformation_score": 55},
        "intelligence_confidence": {"level": "low"},
        "detection_quality": {"weighted_avg_confidence": 0.5},
        "data_freshness": {
            "feeds": {"detections": {"status": "stale", "age_minutes": 120}}
        },
        "intelligence_gaps": [{"name": "Telemetry sync", "severity": "critical"}],
        "meta": {"feedback_accuracy": 0.5},
    }

    validation = intel_brief._derive_automation_validation(brief)
    assert validation is not None
    assert validation.get("status") == "manual_validation"
    score = validation.get("validation_score")
    assert isinstance(score, (int, float)) and score < 60
    assert validation.get("validation_window_hours") == pytest.approx(0.5, rel=1e-3)
    training = validation.get("training_requirements", [])
    assert any("трен" in req.lower() or "drill" in req.lower() for req in training)
    prompts = validation.get("ukrainian_operator_prompts", [])
    assert any("україн" in prompt.lower() for prompt in prompts)
    actions = validation.get("recommended_actions", [])
    assert any("validation" in action.lower() for action in actions)


def test_automation_validation_confirms_mission_ready():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "autonomous",
            "automation_tracks": ["Triage automation"],
            "automation_window_hours": 4.0,
            "monitoring_channels": ["Ops Net"],
            "recommended_actions": ["Keep automation log updated"],
        },
        "automation_guardrails": {
            "status": "autonomous",
            "next_review_hours": 6.0,
            "monitoring_channels": ["Guardrail Net"],
            "guardrails": ["Dual approval"],
            "recommended_actions": ["Share guardrail report"],
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "next_sync_hours": 8.0,
            "mission_channels": ["Mission Net"],
            "recommended_actions": ["Brief mission board"],
        },
        "automation_autonomy": {
            "status": "mission_ready",
            "autonomy_window_hours": 6.0,
        },
        "automation_failsafes": {
            "status": "secured",
            "failsafe_window_hours": 12.0,
            "failsafe_tests": ["Drill failsafe"],
            "recommended_actions": ["Log failsafe summary"],
            "fallback_channels": ["Failsafe Net"],
        },
        "response_readiness": {"level": "reinforced", "support_window_hours": 10.0},
        "response_pressure": {"status": "cleared"},
        "frontline_support": {"status": "supported"},
        "resource_sustainment": {
            "status": "steady",
            "allocation_plan": [{"resource": "Fuel convoy", "window_hours": 9.0}],
        },
        "support_priorities": {
            "priorities": [
                {
                    "name": "Signals",
                    "focus": "Automation audit",
                    "support_window_hours": 6.0,
                }
            ]
        },
        "operational_governance": {"status": "aligned", "governance_score": 82},
        "mission_assurance": {"assurance_score": 82},
        "operational_resilience": {"resilience_score": 85},
        "operational_continuity": {"continuity_score": 83},
        "operational_recovery": {"recovery_score": 72},
        "operational_transformation": {"transformation_score": 82},
        "intelligence_confidence": {"level": "high"},
        "detection_quality": {"weighted_avg_confidence": 0.8},
        "data_freshness": {
            "feeds": {"detections": {"status": "fresh", "age_minutes": 20}}
        },
        "meta": {"feedback_accuracy": 0.9},
    }

    validation = intel_brief._derive_automation_validation(brief)
    assert validation is not None
    assert validation.get("status") == "mission_ready"
    assert validation.get("validation_score") and validation["validation_score"] >= 88
    assert validation.get("validation_window_hours") == pytest.approx(0.33, rel=1e-2)
    tracks = " ".join(validation.get("validation_tracks", []))
    assert "support coordination" in tracks.lower()
    evidence = " ".join(validation.get("validation_evidence", []))
    assert "net" in evidence.lower()


def test_gather_intelligence_brief_adds_automation_validation(monkeypatch):
    now = datetime(2024, 9, 15, 10, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    monkeypatch.setattr(intel_brief, "_derive_automation_playbook", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_guardrails", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_mission_control", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_autonomy", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_failsafes", lambda brief: {})
    monkeypatch.setattr(
        intel_brief, "_derive_automation_strategic_convergence", lambda brief: {}
    )

    validation_payload = {
        "status": "watch",
        "validation_score": 72.4,
        "validation_window_hours": 3.5,
        "training_requirements": ["Pair analysts with automation validation drills."],
        "recommended_actions": ["Share validation summary with Ukrainian duty officer."],
    }

    monkeypatch.setattr(
        intel_brief, "_derive_automation_validation", lambda brief: validation_payload
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    validation = brief.get("automation_validation")
    assert validation == validation_payload

    insight = brief.get("insights", {}).get("automation_validation", {})
    assert insight.get("status") == validation_payload["status"]
    assert insight.get("score") == validation_payload["validation_score"]
    assert (
        insight.get("validation_window_hours")
        == validation_payload["validation_window_hours"]
    )
    assert (
        insight.get("training_requirement_count")
        == len(validation_payload["training_requirements"])
    )

    recommendations = brief.get("recommendations", [])
    assert any("validation" in rec.lower() for rec in recommendations)


def test_automation_deployment_holds_under_guardrails_and_validation_pressure():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "manual_override",
            "automation_score": 58,
            "automation_window_hours": 3.5,
            "automation_tasks": [
                {
                    "task": "Dispatch frontline logistics",
                    "mode": "guided",
                    "owner": "Logistics Cell",
                    "window_hours": 3.0,
                },
                {
                    "task": "Publish fires summary",
                    "mode": "manual",
                    "owner": "Fires Officer",
                    "window_hours": 1.0,
                },
            ],
        },
        "automation_guardrails": {
            "status": "locked_down",
            "autonomy_score": 52,
            "next_review_hours": 1.5,
        },
        "automation_mission_control": {
            "status": "manual_control",
            "mission_control_score": 54,
            "next_sync_hours": 2.0,
        },
        "automation_autonomy": {
            "status": "manual_guarded",
            "autonomy_window_hours": 2.5,
        },
        "automation_failsafes": {
            "status": "manual",
            "failsafe_window_hours": 2.0,
        },
        "automation_validation": {
            "status": "manual_review",
            "validation_window_hours": 4.0,
        },
        "response_readiness": {"level": "critical", "support_window_hours": 1.0},
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 6.0,
        },
        "frontline_support": {"status": "mobilise"},
        "support_priorities": {"status": "mobilise"},
        "resource_sustainment": {"status": "surge"},
        "command_alignment": {"status": "misaligned"},
        "command_directives": {"status": "crisis"},
        "communication_plan": {"status": "crisis"},
        "operational_governance": {"governance_score": 48},
        "mission_assurance": {"assurance_score": 52},
        "operational_resilience": {"resilience_score": 54},
        "operational_continuity": {"continuity_score": 56},
        "operational_recovery": {"recovery_score": 50},
        "operational_transformation": {"transformation_score": 50},
        "escalation_readiness": {"status": "escalate", "next_review_hours": 2.0},
        "intelligence_confidence": {"level": "low"},
        "detection_quality": {"weighted_avg_confidence": 0.5},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "stale", "age_minutes": 140},
                "predictions": {"status": "warning", "age_minutes": 90},
            }
        },
        "intelligence_gaps": [
            {"severity": "critical", "description": "Telemetry outage"},
            {"severity": "major", "description": "Feedback backlog"},
        ],
        "meta": {"feedback_accuracy": 0.6},
        "activity_summary": {"tempo": "surge"},
    }

    deployment = intel_brief._derive_automation_deployment(brief)
    assert deployment is not None
    assert deployment.get("status") in {"hold", "manual_override"}
    assert deployment.get("deployment_score") is not None
    assert deployment["deployment_score"] < 70
    prereqs = " ".join(deployment.get("prerequisites", []))
    assert "guardrail" in prereqs.lower() or "validation" in prereqs.lower()
    prompts = " ".join(deployment.get("ukrainian_operator_prompts", []))
    assert "автомат" in prompts.lower() or "журнал" in prompts.lower()
    actions = " ".join(deployment.get("recommended_actions", []))
    assert "deployment" in actions.lower() or "mission" in actions.lower()
    window = deployment.get("deployment_window_hours")
    assert isinstance(window, (int, float)) and window <= 2.0


def test_automation_deployment_confirms_ready_posture():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "ready",
            "automation_score": 92,
            "automation_window_hours": 6.0,
            "automation_tasks": [
                {
                    "task": "Publish shift brief",
                    "mode": "automated",
                    "owner": "Automation Cell",
                    "window_hours": 4.0,
                },
                {
                    "task": "Sync support queues",
                    "mode": "automated",
                    "owner": "Support Desk",
                    "window_hours": 5.0,
                },
            ],
        },
        "automation_guardrails": {
            "status": "autonomous",
            "autonomy_score": 90,
            "next_review_hours": 12.0,
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "mission_control_score": 86,
            "next_sync_hours": 8.0,
        },
        "automation_autonomy": {
            "status": "autonomous_ready",
            "autonomy_window_hours": 9.0,
        },
        "automation_failsafes": {
            "status": "mission_ready",
            "failsafe_window_hours": 10.0,
        },
        "automation_validation": {
            "status": "mission_ready",
            "validation_window_hours": 6.0,
        },
        "response_readiness": {"level": "reinforced", "support_window_hours": 7.0},
        "response_pressure": {"status": "cleared", "estimated_clearance_hours": 6.5},
        "frontline_support": {"status": "steady"},
        "resource_sustainment": {"status": "steady"},
        "support_priorities": {"status": "steady"},
        "command_directives": {"status": "stabilise"},
        "command_alignment": {"status": "aligned"},
        "communication_plan": {"status": "steady"},
        "operational_governance": {"governance_score": 82},
        "mission_assurance": {"assurance_score": 84},
        "operational_resilience": {"resilience_score": 86},
        "operational_continuity": {"continuity_score": 88},
        "operational_recovery": {"recovery_score": 80},
        "operational_transformation": {"transformation_score": 84},
        "escalation_readiness": {"status": "steady", "next_review_hours": 18.0},
        "intelligence_confidence": {"level": "high"},
        "detection_quality": {"weighted_avg_confidence": 0.84},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "fresh", "age_minutes": 0},
                "predictions": {"status": "fresh", "age_minutes": 0},
            }
        },
        "intelligence_gaps": [],
        "meta": {"feedback_accuracy": 0.9},
        "activity_summary": {"tempo": "steady"},
    }

    deployment = intel_brief._derive_automation_deployment(brief)
    assert deployment is not None
    assert deployment.get("status") == "ready"
    assert deployment.get("deployment_score") and deployment["deployment_score"] >= 90
    window = deployment.get("deployment_window_hours")
    assert isinstance(window, (int, float)) and window == pytest.approx(4.0, rel=1e-2)
    tracks = deployment.get("deployment_tracks", [])
    assert len(tracks) == 2
    assert any(track.get("readiness") == "auto" for track in tracks)
    drivers = " ".join(deployment.get("drivers", []))
    assert "automation playbook" in drivers.lower()
    actions = " ".join(deployment.get("recommended_actions", []))
    assert "deployment" in actions.lower()


def test_gather_intelligence_brief_adds_automation_deployment(monkeypatch):
    now = datetime(2024, 9, 16, 9, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    monkeypatch.setattr(intel_brief, "_derive_automation_playbook", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_guardrails", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_mission_control", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_autonomy", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_failsafes", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_validation", lambda brief: {})
    monkeypatch.setattr(
        intel_brief, "_derive_automation_strategic_convergence", lambda brief: {}
    )

    deployment_payload = {
        "status": "staged",
        "deployment_score": 78.4,
        "deployment_window_hours": 3.0,
        "deployment_tracks": [
            {"name": "Publish mission bulletin", "readiness": "auto", "window_hours": 3.0}
        ],
        "recommended_actions": [
            "Coordinate deployment readiness update with Ukrainian mission control."
        ],
    }

    monkeypatch.setattr(
        intel_brief, "_derive_automation_deployment", lambda brief: deployment_payload
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    deployment = brief.get("automation_deployment")
    assert deployment == deployment_payload

    insight = brief.get("insights", {}).get("automation_deployment", {})
    assert insight.get("status") == deployment_payload["status"]
    assert insight.get("deployment_score") == deployment_payload["deployment_score"]
    assert (
        insight.get("deployment_window_hours")
        == deployment_payload["deployment_window_hours"]
    )

    recommendations = brief.get("recommendations", [])
    assert any("deployment" in rec.lower() for rec in recommendations)


def test_automation_overwatch_demands_manual_watch():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "manual_override",
            "monitoring_channels": ["Automation Ops Net"],
            "recommended_actions": ["Log automation overrides in mission journal."],
        },
        "automation_guardrails": {
            "status": "locked_down",
            "next_review_hours": 1.5,
            "monitoring_channels": ["Guardrail Watch"],
            "fallback_channels": ["HF-Backup"],
            "recommended_actions": ["Review guardrail approvals with command."],
        },
        "automation_mission_control": {
            "status": "manual_control",
            "mission_control_score": 55,
            "next_sync_hours": 1.0,
            "mission_channels": ["Mission Control Net"],
            "recommended_actions": ["Brief leadership on automation posture."],
        },
        "automation_autonomy": {
            "status": "manual_guarded",
            "autonomy_window_hours": 2.0,
        },
        "automation_failsafes": {
            "status": "manual",
            "failsafe_window_hours": 1.5,
            "fallback_channels": ["Manual Hotline"],
            "recommended_actions": ["Run failsafe drill before release."],
        },
        "automation_validation": {
            "status": "manual_review",
            "validation_window_hours": 3.0,
            "recommended_actions": ["Complete validation checklist."],
        },
        "automation_deployment": {
            "status": "hold",
            "deployment_window_hours": 2.5,
            "recommended_actions": ["Hold automated publication until cleared."],
        },
        "response_readiness": {"level": "critical", "support_window_hours": 1.0},
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 5.0,
        },
        "frontline_support": {"status": "mobilise"},
        "resource_sustainment": {"status": "surge"},
        "support_priorities": {"status": "mobilise"},
        "operational_governance": {
            "governance_score": 50,
            "next_review_hours": 2.0,
        },
        "mission_assurance": {"assurance_score": 52},
        "operational_resilience": {"resilience_score": 53},
        "operational_continuity": {"continuity_score": 55},
        "operational_recovery": {"recovery_score": 54},
        "operational_transformation": {"transformation_score": 52},
        "command_directives": {
            "status": "crisis",
            "recommended_actions": ["Issue crisis briefing to automation cell."],
        },
        "command_alignment": {
            "status": "misaligned",
            "recommended_actions": ["Sync commanders on automation outputs."],
        },
        "communication_plan": {
            "status": "crisis",
            "recommended_actions": ["Mirror automation notes to comms."],
        },
        "escalation_readiness": {"status": "escalate", "next_review_hours": 1.0},
        "intelligence_confidence": {"level": "low"},
        "detection_quality": {"weighted_avg_confidence": 0.5},
        "data_freshness": {
            "feeds": {"detections": {"status": "stale", "age_minutes": 160}}
        },
        "operational_risks": {"severity_score": 85},
        "intelligence_gaps": [
            {"severity": "critical", "description": "Telemetry outage"},
        ],
        "meta": {"feedback_accuracy": 0.6},
    }

    overwatch = intel_brief._derive_automation_overwatch(brief)
    assert overwatch is not None
    assert overwatch.get("status") in {"manual_watch", "paired_watch"}
    assert overwatch.get("overwatch_score") is not None
    assert overwatch["overwatch_score"] < 70
    assert overwatch.get("watch_teams")
    assert any("Net" in channel for channel in overwatch.get("monitoring_channels", []))
    prompts = " ".join(overwatch.get("ukrainian_watch_prompts", []))
    assert "овер" in prompts.lower() or "перевір" in prompts.lower()
    assert overwatch.get("fallback_channels")
    actions = " ".join(overwatch.get("recommended_actions", []))
    assert "automation" in actions.lower() or "overwatch" in actions.lower()


def test_automation_overwatch_confirms_ready_posture():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "autonomous",
            "monitoring_channels": ["Automation Ops Net"],
            "drivers": ["Playbook steady"],
            "recommended_actions": ["Audit automation logs weekly."],
        },
        "automation_guardrails": {
            "status": "autonomous",
            "next_review_hours": 12.0,
            "monitoring_channels": ["Guardrail Channel"],
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "mission_control_score": 90,
            "next_sync_hours": 8.0,
            "mission_channels": ["Mission Control Net"],
            "control_focus": ["Audit cadence"],
        },
        "automation_autonomy": {
            "status": "autonomous_ready",
            "autonomy_window_hours": 10.0,
        },
        "automation_failsafes": {
            "status": "mission_ready",
            "failsafe_window_hours": 9.0,
            "fallback_channels": ["Failsafe Net"],
        },
        "automation_validation": {
            "status": "mission_ready",
            "validation_window_hours": 6.0,
        },
        "automation_deployment": {
            "status": "ready",
            "deployment_window_hours": 6.5,
        },
        "response_readiness": {"level": "reinforced", "support_window_hours": 6.0},
        "response_pressure": {"status": "cleared", "estimated_clearance_hours": 4.0},
        "frontline_support": {"status": "steady"},
        "resource_sustainment": {"status": "steady"},
        "support_priorities": {"status": "steady"},
        "operational_governance": {
            "governance_score": 85,
            "next_review_hours": 24.0,
        },
        "mission_assurance": {"assurance_score": 88},
        "operational_resilience": {"resilience_score": 90},
        "operational_continuity": {"continuity_score": 88},
        "operational_recovery": {"recovery_score": 86},
        "operational_transformation": {"transformation_score": 82},
        "command_directives": {"status": "stabilise"},
        "command_alignment": {"status": "aligned"},
        "communication_plan": {"status": "steady"},
        "escalation_readiness": {"status": "steady", "next_review_hours": 18.0},
        "intelligence_confidence": {"level": "high"},
        "detection_quality": {"weighted_avg_confidence": 0.86},
        "data_freshness": {
            "feeds": {"detections": {"status": "fresh", "age_minutes": 5}}
        },
        "operational_risks": {"severity_score": 40},
        "intelligence_gaps": [],
        "meta": {"feedback_accuracy": 0.9},
    }

    overwatch = intel_brief._derive_automation_overwatch(brief)
    assert overwatch is not None
    assert overwatch.get("status") == "mission_ready"
    assert overwatch.get("overwatch_score") and overwatch["overwatch_score"] >= 85
    assert overwatch.get("watch_teams")
    assert "Mission Control Net" in " ".join(overwatch.get("monitoring_channels", []))
    assert overwatch.get("ukrainian_watch_prompts", []) == [] or isinstance(
        overwatch.get("ukrainian_watch_prompts"), list
    )


def test_automation_battle_management_requires_manual_bridge():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "manual_override",
            "monitoring_channels": ["Automation Ops Net"],
            "recommended_actions": ["Review automation battle plans manually."],
            "automation_tasks": [{"task": "Triage"}],
        },
        "automation_guardrails": {
            "status": "locked_down",
            "next_review_hours": 1.0,
            "monitoring_channels": ["Guardrail Watch"],
            "fallback_channels": ["HF Backup"],
            "recommended_actions": ["Log guardrail overrides before release."],
        },
        "automation_mission_control": {
            "status": "manual_control",
            "mission_control_score": 58,
            "next_sync_hours": 1.0,
            "mission_channels": ["Mission Control Net"],
            "handoff_requirements": ["Duty officer approval"],
            "recommended_actions": ["Brief leadership before automation releases."],
        },
        "automation_overwatch": {
            "status": "manual_watch",
            "next_sync_hours": 1.5,
            "monitoring_channels": ["Overwatch Net"],
            "fallback_channels": ["HF Reserve"],
            "ukrainian_watch_prompts": ["Підтвердіть ручну перевірку кожного пакету."],
            "recommended_actions": ["Pair overwatch with mission control."],
        },
        "automation_autonomy": {
            "status": "manual_only",
            "autonomy_window_hours": 2.0,
            "trusted_tasks": ["Sensor checks"],
            "ukrainian_safeguards": ["Фіксуйте кожне автономне рішення."],
            "recommended_actions": ["Document autonomy overrides."],
        },
        "automation_failsafes": {
            "status": "manual",
            "failsafe_window_hours": 1.0,
            "fallback_channels": ["Manual Hotline"],
            "recommended_actions": ["Run failsafe drill before release."],
        },
        "automation_validation": {
            "status": "manual_review",
            "validation_window_hours": 3.0,
            "recommended_actions": ["Complete validation checklist."],
        },
        "automation_deployment": {
            "status": "hold",
            "deployment_window_hours": 2.5,
            "deployment_tracks": [
                {
                    "name": "Automation roll-up",
                    "owner": "Mission control",
                    "readiness": "manual",
                    "window_hours": 2.5,
                    "status": "hold",
                }
            ],
            "recommended_actions": ["Delay deployment until validation clears."],
        },
        "response_readiness": {"level": "critical", "support_window_hours": 1.0},
        "response_pressure": {
            "status": "critical_backlog",
            "estimated_clearance_hours": 5.0,
        },
        "frontline_support": {
            "status": "critical",
            "brigade_support": [
                {
                    "unit": "54th Brigade",
                    "resource": "Drone team",
                    "priority": "urgent",
                    "window_hours": 2.0,
                }
            ],
            "recommended_actions": ["Notify brigade liaison before releases."],
        },
        "resource_sustainment": {
            "status": "surge",
            "recommended_actions": ["Coordinate logistics for automation outputs."],
        },
        "support_priorities": {
            "status": "mobilise",
            "recommended_actions": ["Align support cells with automation outputs."],
        },
        "command_directives": {
            "status": "crisis",
            "recommended_actions": ["Brief command on automation posture."],
        },
        "command_alignment": {
            "status": "misaligned",
            "recommended_actions": ["Sync commanders on automation actions."],
        },
        "communication_plan": {
            "status": "crisis",
            "channels": ["Command Net"],
            "recommended_actions": ["Mirror automation notes to comms cell."],
        },
        "mission_assurance": {"assurance_score": 52},
        "operational_resilience": {"resilience_score": 54},
        "operational_continuity": {"continuity_score": 55},
        "operational_recovery": {"recovery_score": 53},
        "operational_transformation": {"transformation_score": 52},
        "operational_governance": {
            "governance_score": 55,
            "next_review_hours": 1.5,
            "recommended_actions": ["Log automation escalations for governance review."],
        },
        "escalation_readiness": {"status": "escalate", "next_review_hours": 1.0},
        "intelligence_confidence": {"level": "low"},
        "detection_quality": {"weighted_avg_confidence": 0.5},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "stale", "age_minutes": 120},
                "predictions": {"status": "warning", "age_minutes": 80},
            }
        },
        "operational_risks": {"severity_score": 85},
        "meta": {"feedback_accuracy": 0.6},
    }

    battle = intel_brief._derive_automation_battle_management(brief)
    assert battle is not None
    assert battle.get("status") in {"manual_bridge", "paired_ops"}
    assert battle.get("battle_management_score") is not None
    assert battle["battle_management_score"] < 75
    assert battle.get("coordination_tracks")
    assert battle.get("battle_channels")
    assert battle.get("ukrainian_operator_prompts")
    assert battle.get("handoff_requirements")
    assert any(
        "automation" in action.lower()
        for action in battle.get("recommended_actions", [])
    )


def test_automation_battle_management_confirms_ready_posture():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "autonomous",
            "automation_score": 90,
            "monitoring_channels": ["Automation Ops Net"],
            "automation_tasks": [
                {"task": "Sensor triage", "owner": "Automation cell", "mode": "autonomous"}
            ],
        },
        "automation_guardrails": {
            "status": "autonomous",
            "autonomy_score": 90,
            "next_review_hours": 12.0,
            "monitoring_channels": ["Guardrail Channel"],
            "recommended_actions": ["Publish guardrail summary weekly."],
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "mission_control_score": 90,
            "next_sync_hours": 8.0,
            "mission_channels": ["Mission Control Net"],
            "control_focus": ["Automation scaling"],
        },
        "automation_overwatch": {
            "status": "mission_ready",
            "next_sync_hours": 6.0,
            "monitoring_channels": ["Overwatch Net"],
            "watch_focus": ["Edge cases"],
        },
        "automation_autonomy": {
            "status": "autonomous_ready",
            "autonomy_window_hours": 10.0,
            "trusted_tasks": ["Routine triage"],
        },
        "automation_failsafes": {
            "status": "mission_ready",
            "failsafe_window_hours": 9.0,
            "fallback_channels": ["Failsafe Net"],
        },
        "automation_validation": {
            "status": "mission_ready",
            "validation_window_hours": 6.0,
        },
        "automation_deployment": {
            "status": "ready",
            "deployment_window_hours": 6.5,
            "deployment_tracks": [
                {
                    "name": "Automation rollout",
                    "owner": "Automation cell",
                    "readiness": "ready",
                    "window_hours": 6.5,
                    "status": "ready",
                }
            ],
        },
        "response_readiness": {"level": "reinforced", "support_window_hours": 6.0},
        "response_pressure": {"status": "cleared", "estimated_clearance_hours": 3.0},
        "frontline_support": {
            "status": "steady",
            "brigade_support": [
                {
                    "unit": "92nd Brigade",
                    "resource": "ISR cell",
                    "priority": "steady",
                    "window_hours": 8.0,
                }
            ],
        },
        "resource_sustainment": {"status": "steady"},
        "support_priorities": {"status": "steady"},
        "command_directives": {"status": "stabilise"},
        "command_alignment": {"status": "aligned"},
        "communication_plan": {"status": "steady", "channels": ["Ops Net"]},
        "mission_assurance": {"assurance_score": 88},
        "operational_resilience": {"resilience_score": 90},
        "operational_continuity": {"continuity_score": 88},
        "operational_recovery": {"recovery_score": 86},
        "operational_transformation": {"transformation_score": 82},
        "operational_governance": {
            "governance_score": 85,
            "next_review_hours": 24.0,
        },
        "escalation_readiness": {"status": "steady", "next_review_hours": 18.0},
        "intelligence_confidence": {"level": "high"},
        "detection_quality": {"weighted_avg_confidence": 0.88},
        "data_freshness": {
            "feeds": {
                "detections": {"status": "fresh", "age_minutes": 5},
                "predictions": {"status": "fresh", "age_minutes": 6},
            }
        },
        "operational_risks": {"severity_score": 30},
        "meta": {"feedback_accuracy": 0.9},
        "operational_outlook": {"status": "steady", "focus_areas": ["Automation"]},
    }

    battle = intel_brief._derive_automation_battle_management(brief)
    assert battle is not None
    assert battle.get("status") == "mission_ready"
    assert battle.get("battle_management_score") and battle["battle_management_score"] >= 85
    assert battle.get("coordination_tracks")
    assert battle.get("battle_channels")
    assert not battle.get("ukrainian_operator_prompts") or isinstance(
        battle.get("ukrainian_operator_prompts"), list
    )


def test_gather_intelligence_brief_adds_automation_overwatch(monkeypatch):
    now = datetime(2024, 9, 17, 9, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    monkeypatch.setattr(intel_brief, "_derive_automation_playbook", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_guardrails", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_mission_control", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_autonomy", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_failsafes", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_validation", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_deployment", lambda brief: {})
    monkeypatch.setattr(
        intel_brief, "_derive_automation_strategic_convergence", lambda brief: {}
    )

    overwatch_payload = {
        "status": "focused_watch",
        "overwatch_score": 74.2,
        "watch_teams": ["Automation Overwatch Team", "Mission Control Liaison"],
        "next_sync_hours": 2.5,
        "recommended_actions": [
            "Coordinate overwatch hand-off with Ukrainian mission control.",
        ],
    }

    monkeypatch.setattr(
        intel_brief, "_derive_automation_overwatch", lambda brief: overwatch_payload
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    overwatch = brief.get("automation_overwatch")
    assert overwatch == overwatch_payload

    insight = brief.get("insights", {}).get("automation_overwatch", {})
    assert insight.get("status") == overwatch_payload["status"]
    assert insight.get("overwatch_score") == overwatch_payload["overwatch_score"]
    assert insight.get("watch_team_count") == len(overwatch_payload["watch_teams"])
    assert insight.get("next_sync_hours") == overwatch_payload["next_sync_hours"]

    recommendations = brief.get("recommendations", [])
    assert any("overwatch" in rec.lower() for rec in recommendations)


def test_gather_intelligence_brief_adds_automation_battle_management(monkeypatch):
    now = datetime(2024, 10, 1, 10, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    monkeypatch.setattr(intel_brief, "_derive_automation_playbook", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_guardrails", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_mission_control", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_autonomy", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_failsafes", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_validation", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_deployment", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_overwatch", lambda brief: {})
    monkeypatch.setattr(
        intel_brief, "_derive_automation_strategic_convergence", lambda brief: {}
    )

    battle_payload = {
        "status": "coordinated",
        "battle_management_score": 82.1,
        "battle_management_window_hours": 3.5,
        "coordination_tracks": [
            {
                "name": "Mission control sync",
                "lead": "Mission control",
                "readiness": "ready",
                "window_hours": 3.5,
            }
        ],
        "recommended_actions": ["Coordinate automation battle update with brigade liaisons."],
    }

    monkeypatch.setattr(
        intel_brief,
        "_derive_automation_battle_management",
        lambda brief: battle_payload,
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    battle = brief.get("automation_battle_management")
    assert battle == battle_payload

    insight = brief.get("insights", {}).get("automation_battle_management", {})
    assert insight.get("status") == battle_payload["status"]
    assert (
        insight.get("battle_management_score")
        == battle_payload["battle_management_score"]
    )
    assert (
        insight.get("battle_management_window_hours")
        == battle_payload["battle_management_window_hours"]
    )
    assert (
        insight.get("coordination_track_count")
        == len(battle_payload["coordination_tracks"])
    )

    recommendations = brief.get("recommendations", [])
    assert any("battle" in rec.lower() for rec in recommendations)


def test_automation_campaign_orchestration_requires_manual_bridge():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "manual_override",
            "monitoring_channels": ["Automation Ops Net"],
            "automation_tasks": [
                {
                    "task": "Triage queue",
                    "owner": "Automation cell",
                    "mode": "manual",
                    "window_hours": 1.0,
                    "status": "hold",
                }
            ],
            "recommended_actions": ["Review automation releases with command."]
        },
        "automation_guardrails": {
            "status": "locked_down",
            "monitoring_channels": ["Guardrail Net"],
            "recommended_actions": ["Document guardrail overrides."],
        },
        "automation_mission_control": {
            "status": "manual_control",
            "mission_control_score": 56,
            "mission_channels": ["Mission Control Net"],
            "recommended_actions": ["Brief shift leadership on automation risks."],
        },
        "automation_battle_management": {
            "status": "manual_bridge",
            "battle_management_window_hours": 1.0,
            "battle_channels": ["Battle Net"],
            "coordination_tracks": [
                {
                    "name": "Manual battle package",
                    "lead": "Duty officer",
                    "readiness": "manual",
                    "window_hours": 1.0,
                    "status": "hold",
                }
            ],
            "recommended_actions": ["Coordinate manual battle package release."],
        },
        "automation_overwatch": {
            "status": "manual_watch",
            "monitoring_channels": ["Overwatch Net"],
            "recommended_actions": ["Pair overwatch with mission control."],
        },
        "automation_autonomy": {
            "status": "manual_only",
            "autonomy_window_hours": 1.5,
            "ukrainian_safeguards": ["Фіксуйте кожен ручний контроль."],
            "recommended_actions": ["Document manual autonomy overrides."],
        },
        "automation_failsafes": {
            "status": "manual",
            "failsafe_window_hours": 1.0,
            "recommended_actions": ["Run failsafe drill before automation release."],
        },
        "automation_validation": {
            "status": "manual_review",
            "validation_window_hours": 2.0,
            "recommended_actions": ["Complete validation checklist with QA cell."],
        },
        "automation_deployment": {
            "status": "hold",
            "deployment_window_hours": 2.5,
            "deployment_tracks": [
                {
                    "name": "Automation roll-up",
                    "owner": "Mission control",
                    "readiness": "manual",
                    "window_hours": 2.5,
                    "status": "hold",
                }
            ],
            "recommended_actions": ["Delay deployment until validation clears."],
        },
        "response_readiness": {"level": "critical", "support_window_hours": 1.0},
        "response_pressure": {"status": "critical_backlog", "estimated_clearance_hours": 5.0},
        "frontline_support": {
            "status": "critical",
            "brigade_support": [
                {
                    "unit": "54th Brigade",
                    "priority": "urgent",
                    "window_hours": 2.0,
                    "status": "waiting",
                }
            ],
            "recommended_actions": ["Alert brigade liaison before automation releases."],
        },
        "resource_sustainment": {
            "status": "surge",
            "resource_needs": [{"resource": "Generator"}],
            "recommended_actions": ["Coordinate logistics for automation payloads."],
        },
        "support_priorities": {
            "status": "mobilise",
            "coordination_queue": [
                {
                    "task": "Staff overwatch",
                    "team": "Ops Support",
                    "priority": "immediate",
                    "window_hours": 1.0,
                    "status": "pending",
                }
            ],
            "recommended_actions": ["Mobilise support cells around automation outputs."],
        },
        "command_directives": {
            "status": "crisis",
            "recommended_actions": ["Brief command staff on automation posture."],
        },
        "command_alignment": {
            "status": "misaligned",
            "recommended_actions": ["Sync commanders on automation actions."],
        },
        "communication_plan": {
            "status": "crisis",
            "channels": ["Command Net"],
            "recommended_actions": ["Mirror automation notes to comms cell."],
        },
        "mission_assurance": {"assurance_score": 55},
        "operational_resilience": {"resilience_score": 54},
        "operational_continuity": {"continuity_score": 53},
        "operational_recovery": {"recovery_score": 52},
        "operational_transformation": {"transformation_score": 50},
        "operational_governance": {"governance_score": 55, "next_review_hours": 2.0},
        "operational_outlook": {
            "status": "escalate",
            "focus_areas": ["Telemetry recovery"],
            "review_window_hours": 1.5,
        },
        "operational_posture": {"status": "recover", "focus": ["Stabilise automation"]},
        "operational_risks": {"severity_score": 90},
        "intelligence_confidence": {"level": "low"},
        "detection_quality": {"weighted_avg_confidence": 0.5},
        "data_freshness": {
            "feeds": {"detections": {"status": "stale", "age_minutes": 120}}
        },
        "intelligence_gaps": [
            {"severity": "critical", "description": "Prediction coverage below 40%."}
        ],
        "meta": {"feedback_accuracy": 0.6},
    }

    campaign = intel_brief._derive_automation_campaign_orchestration(brief)
    assert campaign is not None
    assert campaign.get("status") in {"manual_bridge", "paired_ops"}
    assert campaign.get("campaign_orchestration_score") is not None
    assert campaign["campaign_orchestration_score"] < 70
    assert campaign.get("operational_dependencies")
    assert campaign.get("orchestration_tracks")
    assert any(track.get("source") for track in campaign.get("orchestration_tracks", []))
    assert campaign.get("ukrainian_operator_prompts")
    assert campaign.get("campaign_channels")


def test_automation_campaign_orchestration_confirms_ready_posture():
    brief: Dict[str, Any] = {
        "automation_playbook": {
            "status": "autonomous",
            "automation_score": 92,
            "monitoring_channels": ["Automation Ops Net"],
            "automation_tasks": [
                {
                    "task": "Sensor triage",
                    "owner": "Automation cell",
                    "mode": "autonomous",
                    "window_hours": 6.0,
                    "status": "mission_ready",
                }
            ],
            "recommended_actions": ["Continue autonomous campaign releases."],
        },
        "automation_guardrails": {
            "status": "steady",
            "monitoring_channels": ["Guardrail Ops"],
            "recommended_actions": ["Log guardrail review results."],
            "next_review_hours": 12.0,
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "mission_control_score": 92,
            "mission_channels": ["Mission Control Net"],
            "next_sync_hours": 6.0,
            "recommended_actions": ["Publish automation campaign summary."],
        },
        "automation_battle_management": {
            "status": "mission_ready",
            "battle_management_window_hours": 4.0,
            "battle_channels": ["Battle Net"],
            "coordination_tracks": [
                {
                    "name": "Fire support sync",
                    "lead": "Operations",
                    "readiness": "ready",
                    "window_hours": 4.0,
                    "status": "mission_ready",
                }
            ],
            "recommended_actions": ["Share battle automation plan with brigades."],
        },
        "automation_overwatch": {
            "status": "mission_ready",
            "monitoring_channels": ["Overwatch Net"],
            "next_sync_hours": 6.0,
            "recommended_actions": ["Maintain overwatch sampling cadence."],
        },
        "automation_autonomy": {
            "status": "mission_ready",
            "autonomy_window_hours": 6.0,
            "trusted_tasks": ["Sensor triage"],
            "recommended_actions": ["Audit automation tasks weekly."],
        },
        "automation_failsafes": {
            "status": "mission_ready",
            "failsafe_window_hours": 12.0,
            "recommended_actions": ["Continue monthly failsafe rehearsals."],
        },
        "automation_validation": {
            "status": "mission_ready",
            "validation_window_hours": 8.0,
            "recommended_actions": ["Maintain validation cadence."],
        },
        "automation_deployment": {
            "status": "ready",
            "deployment_window_hours": 6.0,
            "deployment_tracks": [
                {
                    "name": "Automation deployment wave",
                    "owner": "Mission control",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "ready",
                }
            ],
            "recommended_actions": ["Execute deployment wave with brigade reps."],
        },
        "response_readiness": {"level": "reinforced", "support_window_hours": 8.0},
        "response_pressure": {"status": "cleared", "estimated_clearance_hours": 2.0},
        "frontline_support": {
            "status": "reinforced",
            "brigade_support": [
                {
                    "unit": "92nd Brigade",
                    "priority": "ready",
                    "window_hours": 5.0,
                    "status": "engaged",
                }
            ],
            "recommended_actions": ["Confirm supply windows with brigade."],
        },
        "resource_sustainment": {
            "status": "steady",
            "resource_needs": [],
            "recommended_actions": ["Maintain resupply watch list."],
        },
        "support_priorities": {
            "status": "steady",
            "coordination_queue": [
                {
                    "task": "Automation sync brief",
                    "team": "Support Cell",
                    "priority": "routine",
                    "window_hours": 6.0,
                    "status": "scheduled",
                }
            ],
            "recommended_actions": ["Share automation schedule with support cell."],
        },
        "command_directives": {
            "status": "stabilise",
            "recommended_actions": ["Report automation stability to leadership."],
        },
        "command_alignment": {
            "status": "aligned",
            "recommended_actions": ["Continue aligned command cadence."],
        },
        "communication_plan": {
            "status": "steady",
            "channels": ["Command Net"],
            "recommended_actions": ["Push automation highlights to comms team."],
        },
        "mission_assurance": {"assurance_score": 88},
        "operational_resilience": {"resilience_score": 90},
        "operational_continuity": {"continuity_score": 86},
        "operational_recovery": {"recovery_score": 82},
        "operational_transformation": {"transformation_score": 84},
        "operational_governance": {"governance_score": 82, "next_review_hours": 24.0},
        "operational_outlook": {
            "status": "steady",
            "focus_areas": ["Automation uplift"],
            "review_window_hours": 12.0,
        },
        "operational_posture": {"status": "steady", "focus": ["Expand automation"]},
        "operational_risks": {"severity_score": 40},
        "intelligence_confidence": {"level": "high"},
        "detection_quality": {"weighted_avg_confidence": 0.9},
        "data_freshness": {
            "feeds": {"detections": {"status": "fresh", "age_minutes": 5}}
        },
        "intelligence_gaps": [],
        "meta": {"feedback_accuracy": 0.9},
    }

    campaign = intel_brief._derive_automation_campaign_orchestration(brief)
    assert campaign is not None
    assert campaign.get("status") in {"mission_ready", "coordinated"}
    assert campaign.get("campaign_orchestration_score") and campaign[
        "campaign_orchestration_score"
    ] >= 85
    assert campaign.get("orchestration_tracks")
    assert any(track.get("source") == "battle" for track in campaign.get("orchestration_tracks", []))
    assert campaign.get("integration_partners")
    assert "Automation Ops Net" in " ".join(campaign.get("campaign_channels", []))


def test_automation_joint_operations_requires_manual_bridge():
    brief: Dict[str, Any] = {
        "automation_campaign_orchestration": {
            "status": "manual_bridge",
            "campaign_orchestration_score": 58,
            "orchestration_tracks": [
                {
                    "name": "Manual campaign sync",
                    "lead": "Duty officer",
                    "mode": "manual",
                    "readiness": "manual",
                    "window_hours": 1.5,
                    "status": "hold",
                    "source": "automation",
                }
            ],
            "integration_partners": ["Joint Ops"],
            "operational_dependencies": ["Telemetry recovery"],
            "recommended_actions": ["Brief coalition command on manual bridge posture."],
            "ukrainian_operator_prompts": [
                "Повідомте чергових союзників про ручний режим кампанії.",
            ],
        },
        "automation_battle_management": {
            "status": "manual_bridge",
            "battle_management_window_hours": 1.0,
            "coordination_tracks": [
                {
                    "name": "Manual battle package",
                    "lead": "Fires lead",
                    "readiness": "manual",
                    "window_hours": 1.0,
                    "status": "hold",
                }
            ],
            "recommended_actions": ["Coordinate manual battle approvals with partners."],
        },
        "automation_mission_control": {
            "status": "manual_control",
            "mission_channels": ["Mission Net"],
            "recommended_actions": ["Hold manual mission control brief every hour."],
        },
        "automation_guardrails": {
            "status": "locked_down",
            "monitoring_channels": ["Guardrail Net"],
            "recommended_actions": ["Distribute guardrail override log."],
        },
        "automation_autonomy": {
            "status": "manual_only",
            "autonomy_window_hours": 1.5,
            "ukrainian_safeguards": ["Записуйте всі ручні рішення."],
        },
        "automation_failsafes": {
            "status": "manual",
            "failsafe_window_hours": 1.0,
            "recommended_actions": ["Schedule joint failsafe drill."],
        },
        "automation_validation": {
            "status": "manual_review",
            "validation_window_hours": 2.0,
            "recommended_actions": ["Share validation evidence with coalition QA."],
        },
        "automation_deployment": {
            "status": "hold",
            "deployment_tracks": [
                {
                    "name": "Manual deployment wave",
                    "owner": "Automation cell",
                    "readiness": "manual",
                    "window_hours": 2.0,
                    "status": "hold",
                }
            ],
            "recommended_actions": ["Confirm deployment hold with partner liaisons."],
        },
        "frontline_support": {
            "status": "critical",
            "brigade_support": [
                {
                    "unit": "54th Brigade",
                    "priority": "urgent",
                    "window_hours": 2.0,
                    "status": "waiting",
                }
            ],
            "support_corridors": ["Dnipro logistics"],
            "recommended_actions": ["Alert brigade liaison about manual automation releases."],
        },
        "support_priorities": {
            "status": "mobilise",
            "coordination_queue": [
                {
                    "task": "Manual automation watch",
                    "team": "Ops Support",
                    "priority": "immediate",
                    "window_hours": 1.0,
                    "status": "pending",
                }
            ],
            "recommended_actions": ["Mobilise coalition ops support for manual bridge."],
        },
        "resource_sustainment": {
            "status": "surge",
            "resource_needs": ["Fuel convoy"],
            "recommended_actions": ["Coordinate surge logistics with partners."],
        },
        "command_directives": {
            "status": "crisis",
            "severity": 20,
            "recommended_actions": ["Run hourly command sync on automation."],
        },
        "command_alignment": {
            "status": "misaligned",
            "coordination_gaps": ["Leadership split on automation overrides"],
            "recommended_actions": ["Escalate alignment gap to coalition command."],
        },
        "communication_plan": {
            "status": "escalated",
            "channels": ["Command Net"],
            "recommended_actions": ["Send manual bridge summary to partners."],
        },
        "response_readiness": {"level": "critical", "support_window_hours": 1.0},
        "response_pressure": {"status": "critical_backlog", "estimated_clearance_hours": 4.0},
        "mission_assurance": {"status": "at_risk"},
        "operational_resilience": {"status": "vulnerable"},
        "operational_continuity": {"status": "constrained"},
        "operational_recovery": {"status": "manual_recovery"},
        "operational_transformation": {"status": "mobilise"},
        "operational_governance": {"governance_score": 52},
    }

    joint_ops = intel_brief._derive_automation_joint_operations(brief)
    assert joint_ops is not None
    assert joint_ops.get("status") in {"manual_bridge", "manual_joint"}
    assert joint_ops.get("joint_operations_score") is not None
    assert joint_ops["joint_operations_score"] < 70
    assert joint_ops.get("joint_operation_tracks")
    assert joint_ops.get("operational_dependencies")
    assert joint_ops.get("ukrainian_operator_prompts")


def test_automation_joint_operations_confirms_coalition_ready():
    brief: Dict[str, Any] = {
        "automation_campaign_orchestration": {
            "status": "coordinated",
            "campaign_orchestration_score": 92,
            "campaign_window_hours": 6.0,
            "orchestration_tracks": [
                {
                    "name": "Coalition automation sync",
                    "lead": "Mission control",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "scheduled",
                    "source": "automation",
                }
            ],
            "integration_partners": ["Allied Command"],
            "campaign_channels": ["Automation Ops Net"],
            "recommended_actions": ["Publish coalition automation outlook."],
        },
        "automation_battle_management": {
            "status": "mission_ready",
            "battle_management_window_hours": 6.0,
            "coordination_tracks": [
                {
                    "name": "Coalition fires sync",
                    "lead": "Coalition fires",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "mission_ready",
                    "source": "battle",
                }
            ],
            "recommended_actions": ["Continue joint fires rehearsals."],
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "mission_channels": ["Mission Control Net"],
            "control_focus": ["Coalition alignment"],
            "recommended_actions": ["Share mission ready summary with partners."],
        },
        "automation_guardrails": {
            "status": "steady",
            "monitoring_channels": ["Guardrail Ops"],
        },
        "automation_autonomy": {
            "status": "mission_ready",
            "autonomy_window_hours": 8.0,
            "ukrainian_safeguards": ["Дотримуйтеся спільного протоколу контролю."],
        },
        "automation_failsafes": {
            "status": "secured",
            "failsafe_window_hours": 12.0,
        },
        "automation_validation": {
            "status": "mission_ready",
            "validation_window_hours": 10.0,
        },
        "automation_deployment": {
            "status": "ready",
            "deployment_window_hours": 8.0,
            "deployment_tracks": [
                {
                    "name": "Coalition deployment wave",
                    "owner": "Coalition automation",
                    "readiness": "ready",
                    "window_hours": 8.0,
                    "status": "ready",
                    "source": "deployment",
                }
            ],
        },
        "frontline_support": {
            "status": "reinforced",
            "priority_units": ["92nd Brigade"],
            "support_corridors": ["Logistics Highway"],
            "recommended_actions": ["Update frontline liaison on automation plan."],
        },
        "support_priorities": {
            "status": "reinforce",
            "teams": ["Support Cell"],
            "coordination_queue": [
                {
                    "task": "Coalition readiness brief",
                    "team": "Support Cell",
                    "priority": "next_shift",
                    "window_hours": 6.0,
                    "status": "scheduled",
                }
            ],
        },
        "resource_sustainment": {
            "status": "steady",
            "resource_needs": ["Drone spares"],
        },
        "command_directives": {"status": "steady", "severity": 4},
        "command_alignment": {"status": "aligned", "drivers": ["Coalition cadence"]},
        "communication_plan": {"status": "focused", "channels": ["Command Net"]},
        "response_readiness": {"level": "reinforced", "support_window_hours": 8.0},
        "response_pressure": {"status": "cleared", "estimated_clearance_hours": 2.0},
        "mission_assurance": {"status": "assured"},
        "operational_resilience": {"status": "resilient"},
        "operational_continuity": {"status": "sustained"},
        "operational_recovery": {"status": "stabilise"},
        "operational_transformation": {"status": "steady"},
        "operational_governance": {"governance_score": 85},
    }

    joint_ops = intel_brief._derive_automation_joint_operations(brief)
    assert joint_ops is not None
    assert joint_ops.get("status") in {"coalition_ready", "synchronising"}
    score = joint_ops.get("joint_operations_score")
    assert isinstance(score, (int, float)) and score >= 80
    assert joint_ops.get("joint_operation_tracks")
    assert joint_ops.get("integration_channels")
    assert joint_ops.get("coalition_partners")
    assert joint_ops.get("support_cells")


def test_automation_theater_command_requires_manual_bridge():
    brief: Dict[str, Any] = {
        "automation_joint_operations": {
            "status": "manual_bridge",
            "joint_operation_tracks": [
                {
                    "name": "Manual coalition package",
                    "lead": "Coalition duty officer",
                    "mode": "manual",
                    "readiness": "manual",
                    "window_hours": 1.0,
                    "status": "hold",
                }
            ],
            "integration_channels": ["Coalition Net"],
            "coalition_partners": ["Allied Command"],
            "recommended_actions": ["Escalate manual bridge posture to coalition HQ."],
        },
        "automation_campaign_orchestration": {
            "status": "manual_bridge",
            "campaign_orchestration_score": 58,
            "orchestration_tracks": [
                {
                    "name": "Manual campaign sync",
                    "lead": "Duty officer",
                    "mode": "manual",
                    "readiness": "manual",
                    "window_hours": 1.5,
                    "status": "hold",
                    "source": "automation",
                }
            ],
            "recommended_actions": ["Brief theatre HQ on manual orchestration."]
        },
        "automation_battle_management": {
            "status": "manual_bridge",
            "coordination_tracks": [
                {
                    "name": "Manual battle package",
                    "lead": "Fires lead",
                    "mode": "manual",
                    "readiness": "manual",
                    "window_hours": 1.0,
                    "status": "hold",
                }
            ],
            "recommended_actions": ["Coordinate manual fires approvals per theatre."],
        },
        "automation_mission_control": {
            "status": "manual_control",
            "mission_channels": ["Mission Control Net"],
            "recommended_actions": ["Hold hourly manual release brief."]
        },
        "automation_guardrails": {
            "status": "locked_down",
            "monitoring_channels": ["Guardrail Log"],
            "recommended_actions": ["Distribute guardrail restrictions to theatre HQs."],
        },
        "automation_autonomy": {"status": "manual_only"},
        "automation_failsafes": {"status": "manual"},
        "automation_validation": {"status": "manual_review"},
        "automation_deployment": {"status": "hold"},
        "frontline_support": {
            "status": "critical",
            "recommended_actions": ["Alert brigades about manual automation releases."],
            "priority_units": ["54th Brigade"],
        },
        "resource_sustainment": {
            "status": "surge",
            "recommended_actions": ["Task coalition logistics for surge support."],
        },
        "command_directives": {"status": "critical", "recommended_actions": ["Brief command on manual posture."]},
        "command_alignment": {"status": "misaligned"},
        "communication_plan": {"status": "disrupted"},
        "operational_governance": {"governance_score": 40},
        "mission_assurance": {"status": "at_risk"},
        "operational_resilience": {"status": "fragile"},
        "operational_continuity": {"status": "degraded"},
        "operational_recovery": {"status": "recover"},
        "response_readiness": {"level": "critical"},
        "response_pressure": {"status": "critical_backlog"},
    }

    theater = intel_brief._derive_automation_theater_command(brief)
    assert theater is not None
    assert theater.get("status") in {"manual_bridge", "paired_command"}
    assert theater.get("theater_command_score") is not None
    assert theater.get("command_tracks")
    assert theater.get("support_requirements")
    assert theater.get("ukrainian_operator_prompts")


def test_automation_theater_command_confirms_ready_posture():
    brief: Dict[str, Any] = {
        "automation_joint_operations": {
            "status": "coalition_ready",
            "joint_operations_score": 88,
            "joint_operation_tracks": [
                {
                    "name": "Coalition automation package",
                    "lead": "Coalition mission lead",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "scheduled",
                    "source": "automation",
                }
            ],
            "integration_channels": ["Coalition Ops Net"],
            "coalition_partners": ["Allied Command"],
            "recommended_actions": ["Confirm coalition automation brief."]
        },
        "automation_campaign_orchestration": {
            "status": "coordinated",
            "campaign_orchestration_score": 92,
            "campaign_window_hours": 6.0,
            "orchestration_tracks": [
                {
                    "name": "Campaign automation sync",
                    "lead": "Mission control",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "scheduled",
                    "source": "automation",
                }
            ],
            "recommended_actions": ["Publish campaign automation status to theatres."],
        },
        "automation_battle_management": {
            "status": "mission_ready",
            "coordination_tracks": [
                {
                    "name": "Coalition fires sync",
                    "lead": "Fires coordination",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "mission_ready",
                    "source": "battle",
                }
            ],
            "recommended_actions": ["Maintain coalition fires rehearsal rhythm."],
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "mission_channels": ["Mission Control Net"],
            "recommended_actions": ["Distribute mission-ready summary."]
        },
        "automation_guardrails": {"status": "steady"},
        "automation_autonomy": {"status": "mission_ready"},
        "automation_failsafes": {"status": "secured"},
        "automation_validation": {"status": "mission_ready"},
        "automation_deployment": {"status": "ready"},
        "automation_overwatch": {"monitoring_channels": ["Automation Watch"], "status": "mission_ready"},
        "automation_playbook": {"automation_channels": ["Automation Ops"], "recommended_actions": ["Confirm playbook triggers."]},
        "frontline_support": {
            "status": "reinforced",
            "recommended_actions": ["Share automation cadence with frontline liaisons."],
            "priority_units": ["92nd Brigade"],
        },
        "resource_sustainment": {"status": "steady"},
        "command_directives": {"status": "steady"},
        "command_alignment": {"status": "aligned", "recommended_actions": ["Keep coalition sync briefings."]},
        "communication_plan": {"status": "focused"},
        "operational_governance": {"governance_score": 85},
        "mission_assurance": {"status": "assured"},
        "operational_resilience": {"status": "resilient"},
        "operational_continuity": {"status": "sustained"},
        "operational_recovery": {"status": "stabilise"},
        "response_readiness": {"level": "reinforced"},
        "response_pressure": {"status": "cleared"},
    }

    theater = intel_brief._derive_automation_theater_command(brief)
    assert theater is not None
    assert theater.get("status") in {"mission_ready", "synchronised_command"}
    score = theater.get("theater_command_score")
    assert isinstance(score, (int, float)) and score >= 80
    assert theater.get("command_tracks")
    assert theater.get("coordinating_theaters")
    assert theater.get("command_channels")
    assert theater.get("coalition_commanders")


def test_automation_supreme_command_requires_manual_override():
    brief: Dict[str, Any] = {
        "automation_theater_command": {
            "status": "manual_bridge",
            "command_tracks": [
                {
                    "name": "Manual theatre sync",
                    "lead": "Theatre duty",
                    "mode": "manual",
                    "readiness": "manual",
                    "window_hours": 1.0,
                    "status": "hold",
                    "source": "theater",
                }
            ],
            "command_channels": ["Theatre Net"],
            "coordinating_theaters": ["North"],
            "coalition_commanders": ["Duty commander"],
            "recommended_actions": ["Brief theatre HQ on manual override."]
        },
        "automation_joint_operations": {
            "status": "manual_bridge",
            "joint_operation_tracks": [
                {
                    "name": "Manual coalition track",
                    "lead": "Coalition liaison",
                    "mode": "manual",
                    "readiness": "manual",
                    "window_hours": 1.5,
                    "status": "hold",
                }
            ],
            "integration_channels": ["Coalition Net"],
            "coalition_partners": ["Partner HQ"],
            "recommended_actions": ["Notify coalition of manual bridge posture."]
        },
        "automation_campaign_orchestration": {
            "status": "manual_bridge",
            "orchestration_tracks": [
                {
                    "name": "Manual campaign plan",
                    "lead": "Campaign lead",
                    "mode": "manual",
                    "readiness": "manual",
                    "window_hours": 2.0,
                    "status": "hold",
                    "source": "campaign",
                }
            ],
            "recommended_actions": ["Escalate campaign orchestration risks."]
        },
        "automation_battle_management": {
            "status": "manual_bridge",
            "coordination_tracks": [
                {
                    "name": "Manual battle sync",
                    "lead": "Battle chief",
                    "mode": "manual",
                    "readiness": "manual",
                    "window_hours": 1.0,
                    "status": "hold",
                }
            ],
            "recommended_actions": ["Stage manual battle approvals across theatres."]
        },
        "automation_mission_control": {
            "status": "manual_control",
            "mission_channels": ["Mission Control Net"],
            "recommended_actions": ["Hold manual release board every hour."]
        },
        "automation_overwatch": {
            "status": "manual_overwatch",
            "recommended_actions": ["Assign overwatch officers to monitor manual posture."]
        },
        "automation_guardrails": {
            "status": "locked_down",
            "monitoring_channels": ["Guardrail Log"],
            "recommended_actions": ["Distribute guardrail lock-down bulletin."]
        },
        "automation_playbook": {
            "status": "manual_override",
            "automation_tasks": ["Manual targeting"],
            "ukrainian_operator_prompts": ["Погодьте релізи через ручний канал."]
        },
        "automation_autonomy": {"status": "manual_only"},
        "automation_failsafes": {"status": "manual"},
        "automation_validation": {"status": "manual_review"},
        "automation_deployment": {"status": "hold"},
        "frontline_support": {
            "status": "critical",
            "priority_units": ["92-га бригада"],
            "recommended_actions": ["Попередьте бригади про ручні випуски."]
        },
        "resource_sustainment": {
            "status": "surge",
            "recommended_actions": ["Request surge logistics for manual ops."]
        },
        "response_readiness": {"level": "critical"},
        "response_pressure": {"status": "critical_backlog"},
        "mission_assurance": {"status": "at_risk"},
        "operational_resilience": {"status": "fragile"},
        "operational_governance": {"governance_score": 40},
        "command_alignment": {"status": "misaligned"},
        "command_directives": {"status": "critical"},
    }

    supreme = intel_brief._derive_automation_supreme_command(brief)
    assert supreme is not None
    assert supreme.get("status") == "manual_override"
    assert supreme.get("supreme_command_score") is not None
    assert supreme.get("command_tracks")
    assert supreme.get("command_nodes")
    assert supreme.get("ukrainian_operator_prompts")


def test_automation_supreme_command_recognises_ready_state():
    brief: Dict[str, Any] = {
        "automation_theater_command": {
            "status": "mission_ready",
            "theater_command_score": 94,
            "command_window_hours": 6.0,
            "command_tracks": [
                {
                    "name": "Strategic automation sync",
                    "lead": "Joint command",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "scheduled",
                    "source": "theater",
                }
            ],
            "command_channels": ["Strategic Net"],
            "coordinating_theaters": ["East", "South"],
            "coalition_commanders": ["Joint commander"],
            "recommended_actions": ["Confirm national automation brief."],
            "ukrainian_operator_prompts": ["Перевірте готовність театрів до автоматизації."]
        },
        "automation_joint_operations": {
            "status": "coalition_ready",
            "joint_operation_tracks": [
                {
                    "name": "Coalition automation corridor",
                    "lead": "Coalition liaison",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "scheduled",
                }
            ],
            "integration_channels": ["Coalition Ops Net"],
            "coalition_partners": ["Allied HQ"],
            "recommended_actions": ["Share automation release windows with allies."]
        },
        "automation_campaign_orchestration": {
            "status": "coordinated",
            "campaign_orchestration_score": 92,
            "campaign_window_hours": 6.0,
            "orchestration_tracks": [
                {
                    "name": "Campaign automation plan",
                    "lead": "Automation director",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "scheduled",
                    "source": "campaign",
                }
            ],
            "integration_channels": ["Campaign Net"],
            "recommended_actions": ["Publish campaign orchestration summary."]
        },
        "automation_battle_management": {
            "status": "mission_ready",
            "coordination_tracks": [
                {
                    "name": "Operational fires automation",
                    "lead": "Fires lead",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 5.5,
                    "status": "scheduled",
                }
            ],
            "recommended_actions": ["Align battle automation with campaign window."]
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "mission_channels": ["Mission Control Net"],
            "ukrainian_operator_prompts": ["Підтвердьте готовність місії до автоматичного випуску."]
        },
        "automation_overwatch": {
            "status": "mission_ready",
            "monitoring_channels": ["Overwatch Log"],
            "recommended_actions": ["Update overwatch dashboards with automation plan."]
        },
        "automation_guardrails": {
            "status": "monitored",
            "monitoring_channels": ["Guardrail Log"],
            "recommended_actions": ["Share guardrail posture with command."]
        },
        "automation_playbook": {
            "status": "mission_ready",
            "automation_score": 90,
            "automation_tracks": ["Intel sync", "Support automation"],
            "automation_channels": ["Mission Control Net"],
            "ukrainian_operator_prompts": ["Перевірте готові автоматизовані задачі."]
        },
        "automation_autonomy": {"status": "mission_ready"},
        "automation_failsafes": {"status": "mission_ready"},
        "automation_validation": {"status": "mission_ready"},
        "automation_deployment": {"status": "mission_ready", "deployment_window_hours": 5.0},
        "frontline_support": {
            "status": "steady",
            "priority_units": ["92-га бригада"],
            "recommended_actions": ["Update brigades on automation release."]
        },
        "resource_sustainment": {
            "status": "steady",
            "resource_needs": ["Logistics sync"],
            "recommended_actions": ["Confirm logistics for automation rollout."]
        },
        "response_readiness": {"level": "ready"},
        "response_pressure": {"status": "stable"},
        "mission_assurance": {"status": "steady"},
        "operational_resilience": {"status": "reinforced"},
        "operational_governance": {"governance_score": 88},
        "command_alignment": {"status": "aligned"},
        "command_directives": {"status": "steady"},
    }

    supreme = intel_brief._derive_automation_supreme_command(brief)
    assert supreme is not None
    assert supreme.get("status") in {"mission_ready", "strategic_sync"}
    assert supreme.get("supreme_command_score") and supreme["supreme_command_score"] >= 80
    assert supreme.get("command_tracks")
    assert supreme.get("integration_channels")
    assert supreme.get("ukrainian_operator_prompts")


def test_automation_strategic_convergence_requires_signals():
    brief: Dict[str, Any] = {}

    assert intel_brief._derive_automation_strategic_convergence(brief) is None


def test_automation_strategic_convergence_flags_manual_bridge():
    brief: Dict[str, Any] = {
        "automation_supreme_command": {
            "status": "manual_override",
            "recommended_actions": ["Coordinate manual recovery of automation."],
            "command_nodes": ["Kyiv HQ"],
            "integration_channels": ["Strategic Net"],
        },
        "automation_theater_command": {"status": "manual_bridge"},
        "automation_joint_operations": {"status": "manual_bridge"},
        "automation_guardrails": {
            "status": "manual",
            "monitoring_channels": ["Guardrail Log"],
        },
        "automation_autonomy": {"status": "manual"},
        "automation_failsafes": {"status": "manual"},
        "automation_validation": {"status": "manual_review"},
        "automation_deployment": {"status": "hold"},
        "automation_playbook": {"status": "manual"},
        "automation_mission_control": {"status": "manual"},
        "frontline_support": {
            "status": "critical",
            "priority_units": ["92-га бригада"],
            "support_gaps": ["Manual queue"],
        },
        "resource_sustainment": {"status": "surge", "resource_needs": ["Fuel"]},
        "response_readiness": {"level": "critical"},
        "response_pressure": {"status": "critical_backlog"},
        "mission_assurance": {"status": "at_risk"},
        "operational_resilience": {"status": "fragile", "weak_spots": ["Telemetry"]},
        "operational_continuity": {"status": "disrupted", "constraints": ["Comms"]},
        "operational_governance": {"governance_score": 40},
        "command_alignment": {"status": "misaligned"},
        "command_directives": {"status": "critical"},
        "communication_plan": {"status": "manual"},
        "operational_risks": {
            "severity_score": 82,
            "risks": ["Automation backlog", "Manual escalation"],
        },
        "operational_recovery": {"status": "stabilise", "dependencies": ["Telemetry"]},
    }

    convergence = intel_brief._derive_automation_strategic_convergence(brief)
    assert convergence is not None
    assert convergence.get("status") == "manual_bridge"
    assert convergence.get("strategic_convergence_score") is not None
    prompts = convergence.get("ukrainian_operator_prompts", [])
    assert any("автоматиза" in prompt.lower() for prompt in prompts)
    assert convergence.get("cross_domain_tracks") is None or isinstance(
        convergence.get("cross_domain_tracks"), list
    )


def test_automation_strategic_convergence_recognises_ready_state():
    brief: Dict[str, Any] = {
        "automation_supreme_command": {
            "status": "mission_ready",
            "command_tracks": [
                {
                    "name": "National automation sync",
                    "lead": "Strategic command",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "scheduled",
                    "source": "supreme",
                }
            ],
            "command_nodes": ["Kyiv HQ", "Operational HQ"],
            "integration_channels": ["Strategic Net"],
            "recommended_actions": ["Broadcast automation readiness summary."],
        },
        "automation_theater_command": {
            "status": "synchronised_command",
            "command_tracks": [
                {
                    "name": "Theatre automation sync",
                    "lead": "Mission control",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "scheduled",
                    "source": "theater",
                }
            ],
            "coordinating_theaters": ["East"],
            "command_channels": ["Theatre Net"],
        },
        "automation_joint_operations": {
            "status": "coalition_ready",
            "joint_operation_tracks": [
                {
                    "name": "Coalition automation corridor",
                    "lead": "Coalition liaison",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 6.0,
                    "status": "scheduled",
                    "source": "joint",
                }
            ],
            "coalition_partners": ["Allied HQ"],
            "integration_channels": ["Coalition Net"],
        },
        "automation_campaign_orchestration": {
            "status": "coordinated",
            "orchestration_tracks": [
                {
                    "name": "Campaign automation plan",
                    "lead": "Campaign lead",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 5.5,
                    "status": "scheduled",
                    "source": "campaign",
                }
            ],
            "integration_channels": ["Campaign Net"],
        },
        "automation_battle_management": {
            "status": "mission_ready",
            "coordination_tracks": [
                {
                    "name": "Battle automation",
                    "lead": "Fires lead",
                    "mode": "autonomous",
                    "readiness": "ready",
                    "window_hours": 5.0,
                    "status": "scheduled",
                    "source": "battle",
                }
            ],
        },
        "automation_mission_control": {
            "status": "mission_ready",
            "mission_channels": ["Mission Control Net"],
        },
        "automation_overwatch": {
            "status": "mission_ready",
            "monitoring_channels": ["Overwatch Log"],
        },
        "automation_guardrails": {
            "status": "monitored",
            "monitoring_channels": ["Guardrail Log"],
        },
        "automation_playbook": {
            "status": "mission_ready",
            "automation_channels": ["Automation Net"],
            "automation_tracks": ["Intel sync", "Support automation"],
        },
        "automation_autonomy": {"status": "mission_ready"},
        "automation_failsafes": {"status": "secured"},
        "automation_validation": {"status": "mission_ready"},
        "automation_deployment": {"status": "mission_ready"},
        "frontline_support": {
            "status": "reinforced",
            "priority_units": ["92nd Brigade"],
        },
        "resource_sustainment": {
            "status": "steady",
            "resource_needs": ["Ammunition"],
            "allocation_plan": ["Convoy"],
        },
        "response_readiness": {"level": "reinforced"},
        "response_pressure": {"status": "cleared"},
        "mission_assurance": {"status": "assured"},
        "operational_resilience": {"status": "resilient"},
        "operational_continuity": {"status": "sustained"},
        "operational_governance": {"governance_score": 86},
        "command_alignment": {"status": "aligned"},
        "command_directives": {"status": "steady"},
        "operational_risks": {"severity_score": 42, "risks": ["Routine"]},
        "operational_recovery": {"status": "stabilise", "dependencies": ["Comms"]},
    }

    convergence = intel_brief._derive_automation_strategic_convergence(brief)
    assert convergence is not None
    assert convergence.get("status") in {"mission_ready", "strategic_alignment"}
    score = convergence.get("strategic_convergence_score")
    assert isinstance(score, (int, float)) and score >= 90
    tracks = convergence.get("cross_domain_tracks")
    assert isinstance(tracks, list) and tracks
    nodes = convergence.get("national_command_nodes")
    assert isinstance(nodes, list) and len(nodes) >= 2


def test_gather_intelligence_brief_adds_automation_campaign_orchestration(monkeypatch):
    now = datetime(2024, 10, 1, 12, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    monkeypatch.setattr(intel_brief, "_derive_automation_playbook", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_guardrails", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_mission_control", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_autonomy", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_failsafes", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_validation", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_deployment", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_overwatch", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_battle_management", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_joint_operations", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_theater_command", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_supreme_command", lambda brief: {})
    monkeypatch.setattr(
        intel_brief, "_derive_automation_strategic_convergence", lambda brief: {}
    )

    campaign_payload = {
        "status": "coordinated",
        "campaign_orchestration_score": 88.4,
        "campaign_window_hours": 4.5,
        "orchestration_tracks": [
            {
                "name": "Automation campaign sync",
                "lead": "Mission control",
                "mode": "autonomous",
                "readiness": "ready",
                "window_hours": 4.5,
                "status": "scheduled",
                "source": "automation",
            }
        ],
        "integration_partners": ["Brigade Liaison"],
        "recommended_actions": [
            "Confirm automation campaign window with Ukrainian liaison team."
        ],
    }

    monkeypatch.setattr(
        intel_brief,
        "_derive_automation_campaign_orchestration",
        lambda brief: campaign_payload,
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    campaign = brief.get("automation_campaign_orchestration")
    assert campaign == campaign_payload

    insight = brief.get("insights", {}).get("automation_campaign_orchestration", {})
    assert insight.get("status") == campaign_payload["status"]
    assert (
        insight.get("campaign_orchestration_score")
        == campaign_payload["campaign_orchestration_score"]
    )
    assert (
        insight.get("campaign_window_hours")
        == campaign_payload["campaign_window_hours"]
    )
    assert (
        insight.get("orchestration_track_count")
        == len(campaign_payload["orchestration_tracks"])
    )
    assert (
        insight.get("integration_partner_count")
        == len(campaign_payload["integration_partners"])
    )

    recommendations = brief.get("recommendations", [])
    assert any("campaign" in rec.lower() for rec in recommendations)


def test_gather_intelligence_brief_adds_automation_joint_operations(monkeypatch):
    now = datetime(2024, 10, 1, 12, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    monkeypatch.setattr(intel_brief, "_derive_automation_playbook", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_guardrails", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_mission_control", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_autonomy", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_failsafes", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_validation", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_deployment", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_overwatch", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_battle_management", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_campaign_orchestration", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_theater_command", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_supreme_command", lambda brief: {})
    monkeypatch.setattr(
        intel_brief, "_derive_automation_strategic_convergence", lambda brief: {}
    )

    joint_payload = {
        "status": "coalition_ready",
        "joint_operations_score": 89.2,
        "joint_window_hours": 6.0,
        "joint_operation_tracks": [
            {
                "name": "Coalition automation sync",
                "lead": "Mission control",
                "mode": "autonomous",
                "readiness": "ready",
                "window_hours": 6.0,
                "status": "scheduled",
                "source": "automation",
            }
        ],
        "coalition_partners": ["Allied Command"],
        "integration_channels": ["Mission Control Net"],
        "support_cells": ["Support Cell"],
        "recommended_actions": [
            "Confirm coalition automation briefing window with allied liaison team."
        ],
    }

    monkeypatch.setattr(
        intel_brief,
        "_derive_automation_joint_operations",
        lambda brief: joint_payload,
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    payload = brief.get("automation_joint_operations")
    assert payload == joint_payload

    insight = brief.get("insights", {}).get("automation_joint_operations", {})
    assert insight.get("status") == joint_payload["status"]
    assert (
        insight.get("joint_operations_score")
        == joint_payload["joint_operations_score"]
    )
    assert (
        insight.get("joint_window_hours")
        == joint_payload["joint_window_hours"]
    )
    assert (
        insight.get("joint_operation_track_count")
        == len(joint_payload["joint_operation_tracks"])
    )
    assert (
        insight.get("coalition_partner_count")
        == len(joint_payload["coalition_partners"])
    )


def test_gather_intelligence_brief_adds_automation_theater_command(monkeypatch):
    now = datetime(2024, 10, 1, 12, tzinfo=UTC)
    monkeypatch.setattr(intel_brief, "_utcnow", lambda: now)
    monkeypatch.setattr(intel_brief, "_recent_documents", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "_recent_clusters", lambda *args, **kwargs: [])
    monkeypatch.setattr(intel_brief, "score_clusters", lambda clusters: [])
    monkeypatch.setattr(intel_brief, "meta_analysis", lambda hours: {})

    monkeypatch.setattr(intel_brief, "_derive_automation_playbook", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_guardrails", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_mission_control", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_autonomy", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_failsafes", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_validation", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_deployment", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_overwatch", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_battle_management", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_joint_operations", lambda brief: {})
    monkeypatch.setattr(intel_brief, "_derive_automation_campaign_orchestration", lambda brief: {})

    theater_payload = {
        "status": "synchronised_command",
        "theater_command_score": 87.6,
        "command_window_hours": 5.5,
        "command_tracks": [
            {
                "name": "Theatre automation sync",
                "lead": "Mission control",
                "mode": "autonomous",
                "readiness": "ready",
                "window_hours": 5.5,
                "status": "scheduled",
                "source": "campaign",
            }
        ],
        "coordinating_theaters": ["East", "South"],
        "command_channels": ["Mission Control Net", "Coalition Ops Net"],
        "coalition_commanders": ["Coalition lead"],
        "recommended_actions": [
            "Confirm theatre automation brief with coalition command."
        ],
    }

    monkeypatch.setattr(
        intel_brief,
        "_derive_automation_theater_command",
        lambda brief: theater_payload,
    )

    supreme_payload = {
        "status": "strategic_sync",
        "supreme_command_score": 92.4,
        "command_window_hours": 4.0,
        "command_tracks": [
            {
                "name": "National automation sync",
                "lead": "Strategic command",
                "mode": "autonomous",
                "readiness": "ready",
                "window_hours": 4.0,
                "status": "scheduled",
                "source": "supreme",
            }
        ],
        "command_nodes": ["Kyiv HQ", "Field HQ"],
        "integration_channels": ["Strategic Net"],
        "recommended_actions": ["Confirm supreme automation release window."],
    }

    monkeypatch.setattr(
        intel_brief,
        "_derive_automation_supreme_command",
        lambda brief: supreme_payload,
    )

    strategic_payload = {
        "status": "strategic_alignment",
        "strategic_convergence_score": 91.8,
        "next_convergence_window_hours": 3.5,
        "cross_domain_tracks": [
            {
                "name": "Strategic automation bridge",
                "lead": "National automation cell",
                "mode": "autonomous",
                "readiness": "ready",
                "window_hours": 3.5,
                "status": "scheduled",
                "source": "strategic",
            }
        ],
        "national_command_nodes": ["Kyiv HQ"],
        "coalition_partners": ["Coalition HQ"],
        "strategic_channels": ["Strategic Net"],
        "recommended_actions": [
            "Align national automation convergence briefing with coalition."],
    }

    monkeypatch.setattr(
        intel_brief,
        "_derive_automation_strategic_convergence",
        lambda brief: strategic_payload,
    )

    brief = intel_brief.gather_intelligence_brief(hours=6, activity_limit=5)

    payload = brief.get("automation_theater_command")
    assert payload == theater_payload

    insight = brief.get("insights", {}).get("automation_theater_command", {})
    assert insight.get("status") == theater_payload["status"]
    assert (
        insight.get("theater_command_score")
        == theater_payload["theater_command_score"]
    )
    assert (
        insight.get("command_window_hours")
        == theater_payload["command_window_hours"]
    )
    assert (
        insight.get("command_track_count")
        == len(theater_payload["command_tracks"])
    )
    assert (
        insight.get("coordinating_theater_count")
        == len(theater_payload["coordinating_theaters"])
    )

    supreme = brief.get("automation_supreme_command")
    assert supreme == supreme_payload

    supreme_insight = brief.get("insights", {}).get("automation_supreme_command", {})
    assert supreme_insight.get("status") == supreme_payload["status"]
    assert (
        supreme_insight.get("supreme_command_score")
        == supreme_payload["supreme_command_score"]
    )
    assert (
        supreme_insight.get("command_window_hours")
        == supreme_payload["command_window_hours"]
    )
    assert (
        supreme_insight.get("command_track_count")
        == len(supreme_payload["command_tracks"])
    )
    assert (
        supreme_insight.get("command_node_count")
        == len(supreme_payload["command_nodes"])
    )

    strategic = brief.get("automation_strategic_convergence")
    assert strategic == strategic_payload

    strategic_insight = brief.get("insights", {}).get("automation_strategic_convergence", {})
    assert strategic_insight.get("status") == strategic_payload["status"]
    assert (
        strategic_insight.get("strategic_convergence_score")
        == strategic_payload["strategic_convergence_score"]
    )
    assert (
        strategic_insight.get("next_convergence_window_hours")
        == strategic_payload["next_convergence_window_hours"]
    )
    assert (
        strategic_insight.get("cross_domain_track_count")
        == len(strategic_payload["cross_domain_tracks"])
    )
    assert (
        strategic_insight.get("national_node_count")
        == len(strategic_payload["national_command_nodes"])
    )

    recommendations = brief.get("recommendations", [])
    assert any("theatre" in rec.lower() for rec in recommendations)

    recommendations = brief.get("recommendations", [])
    assert any("coalition" in rec.lower() or "joint" in rec.lower() for rec in recommendations)

    assert any("convergence" in rec.lower() for rec in recommendations)


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
