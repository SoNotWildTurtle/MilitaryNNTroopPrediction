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
