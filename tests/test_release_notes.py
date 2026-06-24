"""Tests for diagnostic release notes generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.release_notes import build_release_notes, render_markdown, write_outputs


class ReleaseNotesTests(unittest.TestCase):
    """Verify release notes are deterministic and useful for reviewers."""

    def test_ready_notes_summarize_health_and_artifacts(self) -> None:
        notes = build_release_notes(
            health_results=[
                {"name": "python", "status": "ok", "detail": "Python works", "remediation": ""},
                {"name": "data_dir", "status": "ok", "detail": "Data directory works", "remediation": ""},
            ],
            manifest={
                "file_count": 2,
                "total_size_bytes": 123,
                "missing_expected": [],
                "files": [
                    {
                        "path": "release-bundle-index.html",
                        "size_bytes": 50,
                        "description": "Reviewer landing page.",
                    },
                    {
                        "path": "openapi-summary.md",
                        "size_bytes": 73,
                        "description": "API summary.",
                    },
                ],
            },
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        markdown = render_markdown(notes)

        self.assertEqual(notes["readiness"], "ready")
        self.assertEqual(notes["health_summary"], {"ok": 2, "warn": 0, "fail": 0})
        self.assertIn("Release diagnostics passed", markdown)
        self.assertIn("release-bundle-index.html", markdown)
        self.assertIn("Publish or attach", notes["next_step"])

    def test_notes_prioritize_failures_over_warnings(self) -> None:
        notes = build_release_notes(
            health_results=[
                {"name": "optional_deps", "status": "warn", "detail": "Optional missing", "remediation": "Install optional deps"},
                {"name": "core_deps", "status": "fail", "detail": "FastAPI missing", "remediation": "Install core deps"},
            ],
            manifest={"file_count": 0, "total_size_bytes": 0, "missing_expected": [], "files": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(notes["readiness"], "blocked")
        self.assertEqual(notes["priority_checks"][0]["name"], "core_deps")
        self.assertIn("Resolve `core_deps`", notes["next_step"])

    def test_writers_create_markdown_and_json(self) -> None:
        notes = build_release_notes(
            health_results=[],
            manifest={"file_count": 0, "total_size_bytes": 0, "missing_expected": ["openapi.json"], "files": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "release-notes.md"
            json_path = Path(temp_dir) / "release-notes.json"

            write_outputs(notes, markdown_path, json_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Release Notes", markdown)
        self.assertEqual(parsed["readiness"], "review")
        self.assertIn("openapi.json", markdown)


if __name__ == "__main__":
    unittest.main()
