"""Tests for release bundle index generation."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.release_bundle_index import render_html, write_html


class ReleaseBundleIndexTests(unittest.TestCase):
    """Verify the release bundle HTML is useful for reviewers."""

    def test_render_html_links_key_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.json").write_text(
                '{"status":"pass","checks":[{"name":"doctor","status":"pass"}]}\n',
                encoding="utf-8",
            )
            (artifact_dir / "doctor-minimal.json").write_text(
                '{"checks":[{"name":"python","status":"pass"}]}\n',
                encoding="utf-8",
            )
            (artifact_dir / "openapi-summary.md").write_text("# API\n", encoding="utf-8")
            (artifact_dir / "dashboard-mockup.html").write_text("<h1>Mockup</h1>\n", encoding="utf-8")
            (artifact_dir / "summary.txt").write_text("bundle summary\n", encoding="utf-8")

            html_text = render_html(artifact_dir)

        self.assertIn("Release bundle index", html_text)
        self.assertIn("Release readiness summary", html_text)
        self.assertIn('href="openapi-summary.md"', html_text)
        self.assertIn('href="dashboard-mockup.html"', html_text)
        self.assertIn("bundle summary", html_text)
        self.assertIn("PASS", html_text)

    def test_write_html_creates_parent_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "index.html"
            write_html("<html></html>\n", output_path)
            written = output_path.read_text(encoding="utf-8")

        self.assertEqual(written, "<html></html>\n")


if __name__ == "__main__":
    unittest.main()
