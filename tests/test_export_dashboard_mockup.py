"""Tests for the static dashboard mockup exporter."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.api.examples import SAMPLE_AREA, sample_payload_bundle
from app.cli.export_dashboard_mockup import render_dashboard_html, write_dashboard_html


class ExportDashboardMockupTests(unittest.TestCase):
    def test_render_dashboard_contains_routes_and_sample_area(self) -> None:
        html = render_dashboard_html(sample_payload_bundle())

        self.assertIn("Analytical API dashboard preview", html)
        self.assertIn(SAMPLE_AREA, html)
        self.assertIn("GET /healthz", html)
        self.assertIn("GET /readyz", html)
        self.assertIn("GET /detections/{area}?limit=10", html)
        self.assertIn("GET /predictions/{area}?limit=10", html)
        self.assertIn("sample-detection-001", html)
        self.assertIn("sample-prediction-001", html)

    def test_write_dashboard_creates_parent_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "dashboard.html"

            write_dashboard_html(sample_payload_bundle(), output_path)

            self.assertTrue(output_path.exists())
            self.assertIn("Static mockup", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
