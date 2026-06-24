"""Smoke tests for lightweight API health and readiness behavior.

These tests intentionally avoid the prediction pipeline, MongoDB queries, and
optional ML dependencies so first-run API checks remain fast and safe.
"""

from __future__ import annotations

import unittest

from app.api import main
from app.api.schemas import HealthStatus, ReadinessStatus, ServiceIndex


class ApiHealthTests(unittest.TestCase):
    """Verify API health helpers stay usable in minimal environments."""

    def test_index_lists_user_friendly_routes(self) -> None:
        payload = main.index()

        self.assertIsInstance(payload, ServiceIndex)
        self.assertEqual(payload.status, "ok")
        self.assertEqual(payload.health, "/healthz")
        self.assertEqual(payload.readiness, "/readyz")
        self.assertIn("GET /detections/{area}", payload.endpoints)

    def test_healthz_is_no_dependency_liveness_check(self) -> None:
        payload = main.healthz()

        self.assertIsInstance(payload, HealthStatus)
        self.assertEqual(payload.status, "ok")

    def test_readyz_reports_safe_configuration_summary(self) -> None:
        payload = main.readyz()

        self.assertIsInstance(payload, ReadinessStatus)
        self.assertEqual(payload.status, "ok")
        self.assertIsInstance(payload.data_dir, str)
        self.assertIsInstance(payload.data_dir_exists, bool)
        self.assertIsInstance(payload.database_name, str)
        self.assertIsInstance(payload.sentinel_configured, bool)

    def test_prediction_route_is_registered_without_importing_pipeline(self) -> None:
        routes = {getattr(route, "path", None) for route in main.app.routes}

        self.assertIn("/healthz", routes)
        self.assertIn("/readyz", routes)
        self.assertIn("/predict/{area}", routes)


if __name__ == "__main__":
    unittest.main()
