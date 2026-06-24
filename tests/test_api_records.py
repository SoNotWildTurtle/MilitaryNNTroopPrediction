"""Endpoint-level tests for MongoDB-backed analytical API records.

These tests mock the database-facing movement history helpers so the API record
routes can be validated without a running MongoDB server or optional ML stack.
"""

from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from bson import ObjectId

from app.api import main


class ApiRecordEndpointTests(unittest.TestCase):
    """Verify analytical record routes return JSON-safe, public API payloads."""

    def test_detections_endpoint_serializes_mocked_mongo_records(self) -> None:
        mongo_id = ObjectId()
        timestamp = datetime(2026, 6, 24, 12, 0, tzinfo=timezone.utc)

        with patch.object(
            main,
            "recent_detections",
            return_value=[
                {
                    "_id": mongo_id,
                    "area": "training-range-alpha",
                    "label": "vehicle",
                    "confidence": 0.91,
                    "timestamp": timestamp,
                    "bbox": (10, 20, 30, 40),
                }
            ],
        ) as mocked_recent:
            payload = main.detections("training-range-alpha", limit=5)

        mocked_recent.assert_called_once_with("training-range-alpha", 5)
        self.assertEqual(len(payload), 1)
        record = payload[0]
        self.assertNotIn("_id", record)
        self.assertEqual(record["id"], str(mongo_id))
        self.assertEqual(record["area"], "training-range-alpha")
        self.assertEqual(record["timestamp"], timestamp.isoformat())
        self.assertEqual(record["bbox"], [10, 20, 30, 40])

    def test_predictions_endpoint_serializes_nested_mocked_records(self) -> None:
        mongo_id = ObjectId()
        nested_id = ObjectId()

        with patch.object(
            main,
            "recent_predictions",
            return_value=[
                {
                    "_id": mongo_id,
                    "area": "training-range-bravo",
                    "trajectory": {
                        "next_point": (44.1, -82.2),
                        "source_detection_id": nested_id,
                    },
                    "scores": [0.7, 0.2, 0.1],
                }
            ],
        ) as mocked_recent:
            payload = main.predictions("training-range-bravo", limit=3)

        mocked_recent.assert_called_once_with("training-range-bravo", 3)
        self.assertEqual(len(payload), 1)
        record = payload[0]
        self.assertEqual(record["id"], str(mongo_id))
        self.assertEqual(record["trajectory"]["next_point"], [44.1, -82.2])
        self.assertEqual(record["trajectory"]["source_detection_id"], str(nested_id))
        self.assertEqual(record["scores"], [0.7, 0.2, 0.1])

    def test_record_routes_are_registered_with_limit_validation_metadata(self) -> None:
        route_limits = {}
        for route in main.app.routes:
            path = getattr(route, "path", "")
            if path in {"/detections/{area}", "/predictions/{area}"}:
                limit_param = next(
                    param for param in route.dependant.query_params if param.name == "limit"
                )
                route_limits[path] = (limit_param.field_info.ge, limit_param.field_info.le)

        self.assertEqual(route_limits["/detections/{area}"], (1, 100))
        self.assertEqual(route_limits["/predictions/{area}"], (1, 100))


if __name__ == "__main__":
    unittest.main()
