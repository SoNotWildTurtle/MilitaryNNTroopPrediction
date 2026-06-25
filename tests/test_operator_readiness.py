"""Tests for operator readiness checklist generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.operator_readiness import build_checklist, render_markdown, write_outputs


class OperatorReadinessTests(unittest.TestCase):
    """Verify operator-facing handoff checks are deterministic and useful."""

    def test_ready_bundle_reports_shareable_next_step(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.json").write_text(
                json.dumps({"results": [{"name": "python", "status": "ok", "detail": "Python works"}]}),
                encoding="utf-8",
            )
            for name in [
                "release-bundle-index.html",
                "release-health.md",
                "release-notes.md",
                "reviewer-handoff.md",
                "triage-summary.md",
                "artifact-manifest.md",
                "dashboard-mockup.html",
                "openapi-summary.md",
            ]:
                (artifact_dir / name).write_text("ok", encoding="utf-8")

            checklist = build_checklist(artifact_dir, generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
            markdown = render_markdown(checklist)

        self.assertEqual(checklist["readiness"], "ready")
        self.assertEqual(checklist["missing_artifacts"], [])
        self.assertIn("Share release-notes.md", checklist["next_step"])
        self.assertIn("# Operator Readiness Checklist", markdown)
        self.assertIn("release-bundle-index.html", markdown)

    def test_missing_artifacts_downgrade_ready_status_to_review(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.json").write_text(
                json.dumps({"results": [{"name": "python", "status": "ok", "detail": "Python works"}]}),
                encoding="utf-8",
            )

            checklist = build_checklist(artifact_dir, generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))

        self.assertEqual(checklist["readiness"], "review")
        self.assertIn("release-bundle-index.html", checklist["missing_artifacts"])
        self.assertIn("Run make ci-report", checklist["next_step"])

    def test_health_failure_marks_checklist_blocked(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.json").write_text(
                json.dumps({"results": [{"name": "core_deps", "status": "fail", "detail": "FastAPI missing"}]}),
                encoding="utf-8",
            )

            checklist = build_checklist(artifact_dir, generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))

        self.assertEqual(checklist["readiness"], "blocked")
        self.assertIn("core_deps: FastAPI missing", checklist["health_notes"])

    def test_writers_create_markdown_and_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            checklist = build_checklist(artifact_dir, generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
            markdown_path = artifact_dir / "operator-readiness.md"
            json_path = artifact_dir / "operator-readiness.json"

            write_outputs(checklist, markdown_path, json_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Operator Readiness Checklist", markdown)
        self.assertEqual(parsed["readiness"], "review")


if __name__ == "__main__":
    unittest.main()
