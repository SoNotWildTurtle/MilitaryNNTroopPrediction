"""Reusable sample API payloads for docs, dashboards, and integration tests.

These fixtures are intentionally synthetic and non-operational. They help API
consumers build against stable response shapes without connecting to MongoDB,
running ML models, or using live imagery.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List

from .schemas import public_records

SAMPLE_AREA = "training-range-alpha"
SAMPLE_TIMESTAMP = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc).isoformat()

SAMPLE_DETECTIONS: List[Dict[str, Any]] = [
    {
        "_id": "sample-detection-001",
        "area": SAMPLE_AREA,
        "label": "vehicle",
        "confidence": 0.91,
        "bbox": [10, 20, 30, 40],
        "timestamp": SAMPLE_TIMESTAMP,
        "source": "synthetic_fixture",
        "notes": "Safe placeholder record for dashboard and API client development.",
    }
]

SAMPLE_PREDICTIONS: List[Dict[str, Any]] = [
    {
        "_id": "sample-prediction-001",
        "area": SAMPLE_AREA,
        "trajectory": {
            "current_point": [44.1000, -82.2000],
            "next_point": [44.1015, -82.1980],
            "source_detection_id": "sample-detection-001",
        },
        "scores": [0.7, 0.2, 0.1],
        "timestamp": SAMPLE_TIMESTAMP,
        "source": "synthetic_fixture",
    }
]


def sample_detection_records() -> List[Dict[str, Any]]:
    """Return public JSON-safe detection sample records."""

    return public_records(deepcopy(SAMPLE_DETECTIONS))


def sample_prediction_records() -> List[Dict[str, Any]]:
    """Return public JSON-safe prediction sample records."""

    return public_records(deepcopy(SAMPLE_PREDICTIONS))


def sample_payload_bundle() -> Dict[str, Any]:
    """Return example payloads for the documented public API endpoints."""

    return {
        "metadata": {
            "description": "Synthetic API response examples for client and dashboard development.",
            "area": SAMPLE_AREA,
            "generated_from": "app.api.examples",
        },
        "endpoints": {
            "GET /healthz": {"status": "ok"},
            "GET /readyz": {
                "status": "ok",
                "data_dir": "data",
                "data_dir_exists": True,
                "database_name": "troop_db",
                "sentinel_configured": False,
            },
            "GET /detections/{area}?limit=10": sample_detection_records(),
            "GET /predictions/{area}?limit=10": sample_prediction_records(),
            "POST /predict/{area}": {"status": "ok"},
        },
    }
