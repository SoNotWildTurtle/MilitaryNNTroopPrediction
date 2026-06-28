"""Tests for CI triage summary generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.triage_summary import SCHEMA_VERSION, build_triage_summary, render_markdown, write_outputs


class TriageSummaryTests(unittest.TestCase):
    """Verify generated triage guidance is deterministic and actionable."""

    def test_failures_prioritize_narrow_rerun_target(self) -> None:
        summary = build_triage_summary(
            health_results=[
                {"name": "python", "status": "ok", "detail": "Python works", "remediation": ""},
                {
                    "name": "core_deps",
                    "status": "fail",
                    "detail": "FastAPI is missing",
                    "remediation": "Install core dependencies",
                },
            ],
            manifest={"file_count": 2, "missing_expected": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        markdown = render_markdown(summary)

        self.assertEqual(summary["status"], "blocked")
        self.assertEqual(summary["next_step"], "make install-core")
        self.assertEqual(summary["health_summary"], {"ok": 1, "warn": 0, "fail": 1})
        self.assertEqual(summary["merge_blockers"], ["Failing health check: core_deps"])
        self.assertIn("failing health check: core_deps", markdown)
        self.assertIn("Failing health check: core_deps", markdown)
        self.assertIn("make install-core", markdown)

    def test_aggregate_health_payload_preserves_triage_counts(self) -> None:
        summary = build_triage_summary(
            health_results={
                "status": "review_warnings",
                "checks": [
                    {"name": "python", "status": "pass", "detail": "Python works", "remediation": ""},
                    {"name": "optional_deps", "status": "warn", "detail": "Optional missing", "remediation": ""},
                ],
            },
            manifest={"file_count": 3, "missing_expected": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(summary["status"], "review")
        self.assertEqual(summary["health_summary"], {"ok": 1, "warn": 1, "fail": 0})
        self.assertIn("optional_deps", render_markdown(summary))

    def test_missing_artifacts_map_to_specific_targets(self) -> None:
        summary = build_triage_summary(
            health_results=[{"name": "python", "status": "ok", "detail": "Python works", "remediation": ""}],
            manifest={"file_count": 1, "missing_expected": ["openapi.json", "dashboard-mockup.html"]},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        targets = [action["target"] for action in summary["recommended_actions"]]

        self.assertEqual(summary["status"], "incomplete")
        self.assertEqual(targets, ["make openapi", "make dashboard"])
        self.assertEqual(
            summary["merge_blockers"],
            ["Missing expected artifact: openapi.json", "Missing expected artifact: dashboard-mockup.html"],
        )
        self.assertIn("openapi.json", render_markdown(summary))

    def test_warnings_keep_summary_in_review_state(self) -> None:
        summary = build_triage_summary(
            health_results=[{"name": "optional_deps", "status": "warn", "detail": "Optional GIS missing", "remediation": ""}],
            manifest={"file_count": 3, "missing_expected": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(summary["status"], "review")
        self.assertEqual(summary["merge_blockers"], [])
        self.assertIn("release-health.md", summary["next_step"])
        self.assertIn("optional_deps", render_markdown(summary))

    def test_schema_and_source_artifacts_are_machine_readable(self) -> None:
        summary = build_triage_summary(
            health_results=[{"name": "python", "status": "pass", "detail": "Python works", "remediation": ""}],
            manifest={"file_count": 4, "missing_expected": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            artifact_dir=Path("ci_artifacts/local-review"),
            health_json_path=Path("ci_artifacts/local-review/release-health.json"),
            manifest_json_path=Path("ci_artifacts/local-review/artifact-manifest.json"),
        )

        markdown = render_markdown(summary)

        self.assertEqual(summary["schema_version"], SCHEMA_VERSION)
        self.assertEqual(summary["status_explanation"], "No failing health checks or missing expected artifacts were reported by the local diagnostics inputs.")
        self.assertEqual(summary["source_artifacts"]["artifact_dir"], "ci_artifacts/local-review")
        self.assertEqual(summary["source_artifacts"]["health_check_count"], 1)
        self.assertEqual(summary["source_artifacts"]["missing_expected_count"], 0)
        self.assertIn("Schema: `triage-summary/v1`", markdown)
        self.assertIn("Artifact directory: `ci_artifacts/local-review`", markdown)
        self.assertIn("Open triage-summary.md before raw logs", markdown)

    def test_writers_create_markdown_and_json(self) -> None:
        summary = build_triage_summary(
            health_results=[],
            manifest={"file_count": 0, "missing_expected": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "triage-summary.md"
            json_path = Path(temp_dir) / "triage-summary.json"

            write_outputs(summary, markdown_path, json_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# CI Triage Summary", markdown)
        self.assertEqual(parsed["status"], "ready")
        self.assertEqual(parsed["schema_version"], SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
