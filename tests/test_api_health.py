"""Smoke tests for lightweight API health and readiness behavior.

These tests intentionally avoid the prediction pipeline, MongoDB queries, and
optional ML dependencies so first-run API checks remain fast and safe.
"""

from __future__ import annotations

import unittest

from app.api import main


class ApiHealthTests(unittest.TestCase):
    """Verify API health helpers stay usable in minimal environments."""

    def test_index_lists_user_friendly_routes(self) -> None:
        payload = main.index()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["health"], "/healthz")
        self.assertEqual(payload["readiness"], "/readyz")
        self.assertIn("GET /detections/{area}", payload["endpoints"])

    def test_healthz_is_no_dependency_liveness_check(self) -> None:
        self.assertEqual(main.healthz(), {"status": "ok"})

    def test_readyz_reports_safe_configuration_summary(self) -> None:
        payload = main.readyz()

        self.assertEqual(payload["status"], "ok")
        self.assertIn("data_dir", payload)
        self.assertIn("data_dir_exists", payload)
        self.assertIn("database_name", payload)
        self.assertIn("sentinel_configured", payload)
        self.assertIsInstance(payload["sentinel_configured"], bool)

    def test_prediction_route_is_registered_without_importing_pipeline(self) -> None:
        routes = {getattr(route, "path", None) for route in main.app.routes}

        self.assertIn("/healthz", routes)
        self.assertIn("/readyz", routes)
        self.assertIn("/predict/{area}", routes)


if __name__ == "__main__":
    unittest.main()
