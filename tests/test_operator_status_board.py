"""Tests for operator status board generation."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.operator_status_board import (
    build_status_board,
    render_markdown,
    write_json,
    write_markdown,
)


class OperatorStatusBoardTests(unittest.TestCase):
    """Verify operator status boards summarize diagnostic bundles safely."""

    def test_build_status_board_summarizes_ready_bundle(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            files = [
                {"path": "release-bundle-index.html", "size_bytes": 10, "sha256": "a" * 64},
                {"path": "reviewer-handoff.md", "size_bytes": 11, "sha256": "b" * 64},
                {"path": "operator-readiness.md", "size_bytes": 12, "sha256": "c" * 64},
                {"path": "automation-plan.md", "size_bytes": 13, "sha256": "d" * 64},
                {"path": "artifact-gap-report.md", "size_bytes": 14, "sha256": "e" * 64},
                {"path": "release-health.md", "size_bytes": 15, "sha256": "f" * 64},
                {"path": "triage-summary.md", "size_bytes": 16, "sha256": "0" * 64},
                {"path": "artifact-manifest.md", "size_bytes": 17, "sha256": "1" * 64},
                {"path": "dashboard-mockup.html", "size_bytes": 18, "sha256": "2" * 64},
            ]
            (artifact_dir / "artifact-manifest.json").write_text(
                json.dumps({"missing_expected": [], "files": files}),
                encoding="utf-8",
            )
            (artifact_dir / "reviewer-handoff.json").write_text(
                json.dumps({"review_status": "ready", "release_status": "pass", "recommended_rerun": "make verify"}),
                encoding="utf-8",
            )
            (artifact_dir / "release-health.json").write_text('{"status":"pass"}\n', encoding="utf-8")
            (artifact_dir / "artifact-gap-report.json").write_text('{"status":"pass"}\n', encoding="utf-8")

            board = build_status_board(artifact_dir)
            markdown = render_markdown(board)

        self.assertEqual(board["review_status"], "ready")
        self.assertEqual(board["release_status"], "pass")
        self.assertEqual(board["severity"], "ready")
        self.assertEqual(board["recommended_rerun"], "make verify")
        self.assertEqual(board["missing_expected"], [])
        self.assertTrue(all(item["present"] for item in board["key_artifacts"]))
        self.assertIn("Operator status board", markdown)
        self.assertIn("READY", markdown)
        self.assertIn("Open release-bundle-index.html first", markdown)
        self.assertIn("0 missing expected artifact", board["copyable_status"])

    def test_build_status_board_flags_missing_artifacts_and_uses_triage_rerun(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "custom-manifest.json").write_text(
                json.dumps(
                    {
                        "missing_expected": ["openapi.json", "dashboard-mockup.html"],
                        "files": [
                            {"path": "release-health.md", "size_bytes": 1, "sha256": "a" * 64},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            (artifact_dir / "custom-triage.json").write_text(
                json.dumps({"recommended_command": "make dashboard"}),
                encoding="utf-8",
            )

            board = build_status_board(
                artifact_dir,
                manifest_path=artifact_dir / "custom-manifest.json",
                triage_path=artifact_dir / "custom-triage.json",
            )
            markdown = render_markdown(board)

        self.assertEqual(board["review_status"], "unknown")
        self.assertEqual(board["release_status"], "unknown")
        self.assertEqual(board["severity"], "unknown")
        self.assertEqual(board["recommended_rerun"], "make dashboard")
        self.assertEqual(len(board["missing_expected"]), 2)
        self.assertIn("2 MISSING", markdown)
        self.assertIn("Regenerate the diagnostics bundle", markdown)
        self.assertIn("dashboard-mockup.html", markdown)

    def test_gap_report_can_escalate_ready_handoff(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "reviewer-handoff.json").write_text('{"review_status":"ready"}\n', encoding="utf-8")
            (artifact_dir / "artifact-gap-report.json").write_text('{"status":"failed"}\n', encoding="utf-8")

            board = build_status_board(artifact_dir)

        self.assertEqual(board["review_status"], "needs_attention")
        self.assertEqual(board["severity"], "blocked")

    def test_build_status_board_has_safe_defaults_without_inputs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            board = build_status_board(Path(temp_dir))
            markdown = render_markdown(board)

        self.assertEqual(board["review_status"], "unknown")
        self.assertEqual(board["release_status"], "unknown")
        self.assertEqual(board["recommended_rerun"], "make verify")
        self.assertIn("UNKNOWN", markdown)
        self.assertIn("Resolve missing artifacts or warnings", markdown)
        self.assertIn("Safe operating scope", markdown)

    def test_writers_create_parent_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "nested"
            markdown_path = output_dir / "operator-status-board.md"
            json_path = output_dir / "operator-status-board.json"
            board = {
                "generated_at": "now",
                "artifact_dir": "ci_artifacts",
                "severity": "ready",
                "review_status": "ready",
                "release_status": "pass",
                "recommended_rerun": "make verify",
                "missing_expected": [],
                "key_artifacts": [],
                "task_rows": [],
                "copyable_status": "ready",
            }

            write_markdown("# Status\n", markdown_path)
            write_json(board, json_path)

            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "# Status\n")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["review_status"], "ready")


if __name__ == "__main__":
    unittest.main()
