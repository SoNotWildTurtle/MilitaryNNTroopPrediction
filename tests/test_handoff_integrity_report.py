"""Tests for handoff integrity report generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.handoff_integrity_report import (
    build_handoff_integrity_report,
    main,
    render_markdown,
    write_outputs,
)


class HandoffIntegrityReportTests(unittest.TestCase):
    """Verify handoff integrity artifacts stay deterministic and safe."""

    def test_missing_artifact_and_failed_health_block_report(self) -> None:
        report = build_handoff_integrity_report(
            release_health_payload={"checks": [{"name": "core_deps", "status": "fail"}]},
            manifest={
                "file_count": 2,
                "missing_expected": ["openapi.json"],
                "files": [
                    {"path": "release-health.json"},
                    {"path": "reviewer-handoff.json"},
                ],
            },
            reviewer_handoff={"status": "ready"},
            operator_next_steps={"status": "ready"},
            uncertainty_packet={"status": "blocked"},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        markdown = render_markdown(report)
        categories = [finding["category"] for finding in report["findings"]]

        self.assertEqual(report["status"], "blocked")
        self.assertIn("missing_review_artifact", categories)
        self.assertIn("manifest_completeness", categories)
        self.assertIn("release_health", categories)
        self.assertIn("handoff_alignment", categories)
        self.assertIn("make ci-report", report["next_validation_steps"])
        self.assertIn("Do not use this report for targeting", markdown)

    def test_ready_report_uses_safe_review_steps(self) -> None:
        report = build_handoff_integrity_report(
            release_health_payload={"checks": [{"name": "python", "status": "pass"}]},
            manifest={
                "file_count": 5,
                "missing_expected": [],
                "files": [
                    {"path": "release-health.json"},
                    {"path": "reviewer-handoff.json"},
                    {"path": "operator-next-steps.json"},
                    {"path": "uncertainty-review-packet.json"},
                ],
            },
            reviewer_handoff={"status": "ready"},
            operator_next_steps={"status": "ready"},
            uncertainty_packet={"status": "ready"},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        markdown = render_markdown(report)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["findings"], [])
        self.assertIn("make verify", report["next_validation_steps"])
        self.assertIn("No cross-artifact integrity gaps", markdown)
        self.assertIn("analytical estimates", markdown)

    def test_status_misalignment_warns_without_blocking(self) -> None:
        report = build_handoff_integrity_report(
            release_health_payload={"checks": [{"name": "optional_deps", "status": "warn"}]},
            manifest={
                "file_count": 5,
                "missing_expected": [],
                "files": [
                    {"path": "release-health.json"},
                    {"path": "reviewer-handoff.json"},
                    {"path": "operator-next-steps.json"},
                    {"path": "uncertainty-review-packet.json"},
                ],
            },
            reviewer_handoff={"status": "ready"},
            operator_next_steps={"status": "ready"},
            uncertainty_packet={"status": "review_warnings"},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(report["status"], "review_warnings")
        self.assertTrue(any(finding["severity"] == "medium" for finding in report["findings"]))

    def test_writers_create_markdown_and_json(self) -> None:
        report = build_handoff_integrity_report(
            release_health_payload=[],
            manifest={"file_count": 0, "missing_expected": [], "files": []},
            reviewer_handoff={},
            operator_next_steps={},
            uncertainty_packet={},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "handoff-integrity-report.md"
            json_path = Path(temp_dir) / "handoff-integrity-report.json"

            write_outputs(report, markdown_path, json_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Handoff Integrity Report", markdown)
        self.assertEqual(parsed["status"], "blocked")
        self.assertIn("privacy_and_safety_notes", parsed)

    def test_cli_reads_artifact_directory_defaults(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.json").write_text(
                '{"checks":[{"name":"python","status":"pass"}]}',
                encoding="utf-8",
            )
            (artifact_dir / "artifact-manifest.json").write_text(
                json.dumps(
                    {
                        "file_count": 4,
                        "missing_expected": [],
                        "files": [
                            {"path": "release-health.json"},
                            {"path": "reviewer-handoff.json"},
                            {"path": "operator-next-steps.json"},
                            {"path": "uncertainty-review-packet.json"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (artifact_dir / "reviewer-handoff.json").write_text('{"status":"ready"}', encoding="utf-8")
            (artifact_dir / "operator-next-steps.json").write_text('{"status":"ready"}', encoding="utf-8")
            (artifact_dir / "uncertainty-review-packet.json").write_text('{"status":"ready"}', encoding="utf-8")

            exit_code = main(["--artifact-dir", str(artifact_dir)])

            parsed = json.loads((artifact_dir / "handoff-integrity-report.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(parsed["status"], "ready")


if __name__ == "__main__":
    unittest.main()
