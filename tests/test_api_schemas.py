"""Tests for API response models and public record serialization."""

from __future__ import annotations

import unittest
from datetime import datetime
from typing import get_args, get_origin

from app.api import main
from app.api.schemas import (
    AnalyticalRecord,
    HealthStatus,
    PredictionStatus,
    ReadinessStatus,
    ServiceIndex,
    public_record,
)


class ApiSchemaTests(unittest.TestCase):
    """Validate typed response models and JSON-safe record conversion."""

    def test_health_endpoints_have_response_models(self) -> None:
        response_models = {
            getattr(route, "path", None): getattr(route, "response_model", None)
            for route in main.app.routes
        }

        self.assertIs(response_models["/"], ServiceIndex)
        self.assertIs(response_models["/healthz"], HealthStatus)
        self.assertIs(response_models["/readyz"], ReadinessStatus)
        self.assertIs(response_models["/predict/{area}"], PredictionStatus)

        detections_model = response_models["/detections/{area}"]
        predictions_model = response_models["/predictions/{area}"]
        self.assertIs(get_origin(detections_model), list)
        self.assertEqual(get_args(detections_model), (AnalyticalRecord,))
        self.assertIs(get_origin(predictions_model), list)
        self.assertEqual(get_args(predictions_model), (AnalyticalRecord,))

    def test_public_record_renames_mongo_id_and_preserves_extra_fields(self) -> None:
        raw = {
            "_id": "abc123",
            "area": "training-area",
            "score": 0.87,
            "timestamp": datetime(2026, 1, 2, 3, 4, 5),
            "nested": {"seen_at": datetime(2026, 1, 2, 3, 4, 5)},
        }

        payload = public_record(raw)

        self.assertNotIn("_id", payload)
        self.assertEqual(payload["id"], "abc123")
        self.assertEqual(payload["area"], "training-area")
        self.assertEqual(payload["timestamp"], "2026-01-02T03:04:05")
        self.assertEqual(payload["nested"]["seen_at"], "2026-01-02T03:04:05")

    def test_analytical_record_accepts_forward_compatible_fields(self) -> None:
        record = AnalyticalRecord(id="abc123", area="training-area", score=0.87)

        self.assertEqual(record.id, "abc123")
        self.assertEqual(getattr(record, "area"), "training-area")
        self.assertEqual(getattr(record, "score"), 0.87)


if __name__ == "__main__":
    unittest.main()
