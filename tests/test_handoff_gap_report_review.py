"""Tests for offline handoff gap-report review generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.handoff_gap_report_review import (
    SAFE_SCOPE,
    build_gap_report_review,
    main,
    render_markdown,
    strict_validation_passed,
    write_outputs,
)


class HandoffGapReportReviewTests(unittest.TestCase):
    """Verify deterministic gap-report cross-check behavior."""

    def _handoff(self) -> dict:
        return {
            "schema_version": "1.3",
            "release_bundle_target_projection": {
                "targets": [
                    {
                        "path": "ci_artifacts/run-decision-record.json",
                        "role": "decision_record",
                        "presence_status": "present",
                        "integrity_status": "hash_recorded",
                    },
                    {
                        "path": "ci_artifacts/implementation-acceptance-handoff.json",
                        "role": "acceptance_handoff",
                        "presence_status": "present",
                        "integrity_status": "hash_recorded",
                    },
                    {
                        "path": "ci_artifacts/suspicious-note.md",
                        "role": "review_note",
                        "presence_status": "present",
                        "integrity_status": "needs_review",
                    },
                    {"path": "", "role": "ignored_empty_path"},
                ],
            },
        }

    def _clear_gap_report(self) -> dict:
        return {
            "schema_version": "1.0",
            "missing_expected_files": [],
            "suspicious_artifacts": [],
        }

    def _blocking_gap_report(self) -> dict:
        return {
            "schema_version": "1.0",
            "missing_expected_files": [
                {"path": "ci_artifacts/implementation-acceptance-handoff.json", "reason": "not regenerated"},
            ],
            "suspicious_artifacts": [
                {"path": "ci_artifacts/suspicious-note.md", "reason": "unexpected manual output"},
            ],
        }

    def test_clear_gap_report_marks_targets_ready_for_review(self) -> None:
        review = build_gap_report_review(
            self._handoff(),
            self._clear_gap_report(),
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        markdown = render_markdown(review)

        self.assertEqual(review["schema_version"], "1.0")
        self.assertEqual(review["status"], "ready_for_review")
        self.assertEqual(review["target_count"], 3)
        self.assertTrue(review["artifact_gap_report_supplied"])
        self.assertEqual(review["gap_summary"]["blocking_target_count"], 0)
        self.assertTrue(strict_validation_passed(review))
        self.assertTrue(all(target["gap_status"] == "gap_clear" for target in review["reviewed_targets"]))
        self.assertIn("Artifact gap report supplied: True", markdown)
        self.assertIn("gap_clear", markdown)
        self.assertIn(SAFE_SCOPE, markdown)

    def test_gap_report_missing_and_suspicious_targets_block_review(self) -> None:
        review = build_gap_report_review(
            self._handoff(),
            self._blocking_gap_report(),
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        statuses = {target["path"]: target["gap_status"] for target in review["reviewed_targets"]}
        markdown = render_markdown(review)

        self.assertEqual(review["status"], "blocked_gap_report_review")
        self.assertEqual(statuses["ci_artifacts/run-decision-record.json"], "gap_clear")
        self.assertEqual(statuses["ci_artifacts/implementation-acceptance-handoff.json"], "missing_in_gap_report")
        self.assertEqual(statuses["ci_artifacts/suspicious-note.md"], "suspicious_in_gap_report")
        self.assertEqual(review["gap_summary"]["missing_path_count"], 1)
        self.assertEqual(review["gap_summary"]["suspicious_path_count"], 1)
        self.assertEqual(review["gap_summary"]["blocking_target_count"], 2)
        self.assertEqual(len(review["merge_blockers"]), 2)
        self.assertFalse(strict_validation_passed(review))
        self.assertIn("missing_in_gap_report", markdown)
        self.assertIn("suspicious_in_gap_report", markdown)
        self.assertIn("not operational tasking", markdown)

    def test_missing_inputs_block_safely(self) -> None:
        review = build_gap_report_review(generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        markdown = render_markdown(review)

        self.assertEqual(review["status"], "blocked_gap_report_review")
        self.assertFalse(review["artifact_gap_report_supplied"])
        self.assertEqual(review["target_count"], 0)
        self.assertTrue(any("No release bundle target paths" in blocker for blocker in review["merge_blockers"]))
        self.assertTrue(any("No parseable artifact gap report" in blocker for blocker in review["merge_blockers"]))
        self.assertFalse(strict_validation_passed(review))
        self.assertIn("No release bundle targets", markdown)

    def test_writers_create_markdown_and_json_outputs(self) -> None:
        review = build_gap_report_review(
            self._handoff(),
            self._clear_gap_report(),
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "review.md"
            json_path = Path(temp_dir) / "review.json"
            write_outputs(review, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Handoff Gap Report Review", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(parsed["status"], "ready_for_review")
        self.assertEqual(parsed["gap_summary"]["blocking_target_count"], 0)
        self.assertIn("rollback", parsed["rollback_notes"].lower())

    def test_strict_cli_fails_when_gap_report_is_missing(self) -> None:
        exit_code = main(["--no-markdown", "--no-json", "--strict"])

        self.assertEqual(exit_code, 1)

    def test_strict_cli_passes_for_clear_gap_report(self) -> None:
        with TemporaryDirectory() as temp_dir:
            handoff_path = Path(temp_dir) / "implementation-acceptance-handoff.json"
            gap_path = Path(temp_dir) / "artifact-gap-report.json"
            handoff_path.write_text(json.dumps(self._handoff()), encoding="utf-8")
            gap_path.write_text(json.dumps(self._clear_gap_report()), encoding="utf-8")
            exit_code = main([
                "--handoff-json",
                str(handoff_path),
                "--artifact-gap-report-json",
                str(gap_path),
                "--no-markdown",
                "--no-json",
                "--strict",
            ])

        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
