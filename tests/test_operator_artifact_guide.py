"""Tests for operator artifact guide generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.operator_artifact_guide import build_operator_artifact_guide, render_markdown, write_outputs


class OperatorArtifactGuideTests(unittest.TestCase):
    """Verify operator artifact guidance is deterministic and useful."""

    def test_failures_prioritize_triage_summary(self) -> None:
        guide = build_operator_artifact_guide(
            health_results=[
                {"name": "python", "status": "ok", "detail": "Python works", "remediation": ""},
                {"name": "core_deps", "status": "fail", "detail": "FastAPI is missing", "remediation": "Install core"},
            ],
            manifest={
                "artifact_dir": "ci_artifacts",
                "file_count": 2,
                "missing_expected": [],
                "files": [
                    {"path": "release-bundle-index.html", "size_bytes": 120, "sha256": "abc"},
                    {"path": "triage-summary.md", "size_bytes": 80, "sha256": "def"},
                ],
            },
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        markdown = render_markdown(guide)

        self.assertEqual(guide["health_summary"], {"ok": 1, "warn": 0, "fail": 1})
        self.assertIn("triage-summary.md", guide["recommended_first_step"])
        self.assertIn("release-bundle-index.html", markdown)
        self.assertIn("| `triage-summary.md` | yes | maintainers |", markdown)

    def test_missing_artifacts_prioritize_manifest_review(self) -> None:
        guide = build_operator_artifact_guide(
            health_results=[{"name": "python", "status": "ok", "detail": "Python works", "remediation": ""}],
            manifest={
                "artifact_dir": "ci_artifacts",
                "file_count": 1,
                "missing_expected": ["dashboard-mockup.html"],
                "files": [{"path": "artifact-manifest.md", "size_bytes": 64, "sha256": "abc"}],
            },
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertIn("artifact-manifest.md", guide["recommended_first_step"])
        self.assertIn("dashboard-mockup.html", guide["missing_expected"])
        self.assertIn("missing", render_markdown(guide))

    def test_ready_bundle_starts_with_landing_page(self) -> None:
        guide = build_operator_artifact_guide(
            health_results=[{"name": "python", "status": "ok", "detail": "Python works", "remediation": ""}],
            manifest={
                "artifact_dir": "ci_artifacts",
                "file_count": 1,
                "missing_expected": [],
                "files": [{"path": "release-bundle-index.html", "size_bytes": 120, "sha256": "abc"}],
            },
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertIn("release-bundle-index.html", guide["recommended_first_step"])
        self.assertEqual(guide["artifact_menu"][0]["path"], "release-bundle-index.html")

    def test_writers_create_markdown_and_json(self) -> None:
        guide = build_operator_artifact_guide(
            health_results=[],
            manifest={"artifact_dir": "ci_artifacts", "file_count": 0, "missing_expected": [], "files": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "operator-artifact-guide.md"
            json_path = Path(temp_dir) / "operator-artifact-guide.json"

            write_outputs(guide, markdown_path, json_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Operator Artifact Guide", markdown)
        self.assertEqual(parsed["safe_scope"], guide["safe_scope"])


if __name__ == "__main__":
    unittest.main()
