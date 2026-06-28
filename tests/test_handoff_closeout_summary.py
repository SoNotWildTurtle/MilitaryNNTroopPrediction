"""Tests for handoff closeout summary generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.handoff_closeout_summary import (
    build_closeout_summary,
    render_markdown,
    render_text,
    write_outputs,
)


class HandoffCloseoutSummaryTests(unittest.TestCase):
    """Verify deterministic closeout behavior for generated handoff artifacts."""

    def _write_ready_bundle(self, artifact_dir: Path) -> None:
        payloads = {
            "decision-log.json": {"decision": "ready", "blockers": [], "warnings": []},
            "handoff-validation-receipt.json": {"status": "ready", "blockers": []},
            "handoff-readiness-scorecard.json": {"status": "ready", "score": 100},
            "artifact-manifest.json": {"status": "ready", "file_count": 4, "files": []},
        }
        for filename, payload in payloads.items():
            (artifact_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    def test_ready_bundle_returns_ready_closeout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            self._write_ready_bundle(artifact_dir)

            summary = build_closeout_summary(
                artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            markdown = render_markdown(summary)
            text = render_text(summary)

        self.assertEqual(summary["closeout_status"], "ready")
        self.assertEqual(summary["blockers"], [])
        self.assertIn("Handoff Closeout Summary", markdown)
        self.assertIn("Closeout=READY", text)
        self.assertIn("no operational certainty claimed", text)

    def test_missing_decision_log_blocks_closeout(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            self._write_ready_bundle(artifact_dir)
            (artifact_dir / "decision-log.json").unlink()

            summary = build_closeout_summary(artifact_dir)

        self.assertEqual(summary["closeout_status"], "blocked")
        self.assertTrue(any("decision-log.json" in item for item in summary["blockers"]))

    def test_warning_receipt_requires_review(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            self._write_ready_bundle(artifact_dir)
            (artifact_dir / "handoff-validation-receipt.json").write_text(
                json.dumps({"status": "ready", "warnings": ["manual reviewer signoff pending"]}),
                encoding="utf-8",
            )

            summary = build_closeout_summary(artifact_dir)

        self.assertEqual(summary["closeout_status"], "needs_review")
        self.assertTrue(any("handoff-validation-receipt.json" in item for item in summary["warnings"]))

    def test_writers_create_markdown_json_and_text(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir) / "artifacts"
            artifact_dir.mkdir()
            self._write_ready_bundle(artifact_dir)
            markdown_path = Path(temp_dir) / "closeout.md"
            json_path = Path(temp_dir) / "closeout.json"
            text_path = Path(temp_dir) / "closeout.txt"
            summary = build_closeout_summary(
                artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

            write_outputs(summary, markdown_path, json_path, text_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            text = text_path.read_text(encoding="utf-8")

        self.assertIn("# Handoff Closeout Summary", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(parsed["closeout_status"], "ready")
        self.assertIn("Closeout=READY", text)


if __name__ == "__main__":
    unittest.main()
