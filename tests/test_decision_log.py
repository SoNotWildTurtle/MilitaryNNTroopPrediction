"""Tests for analytical decision log generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.decision_log import build_decision_log, render_markdown, write_outputs


class DecisionLogTests(unittest.TestCase):
    """Verify deterministic analytical decision log behavior."""

    def _write_ready_bundle(self, artifact_dir: Path) -> None:
        payloads = {
            "handoff-readiness-scorecard.json": {"status": "ready", "score": 100.0},
            "handoff-validation-receipt.json": {"status": "ready", "blockers": []},
            "provenance-validation-matrix.json": {"status": "ready", "rows": []},
            "evidence-checklist.json": {"status": "ready", "warnings": []},
            "handoff-integrity-report.json": {"status": "ready", "blockers": []},
            "uncertainty-review-packet.json": {"status": "ready", "review_items": []},
            "artifact-manifest.json": {"status": "ready", "file_count": 7, "files": []},
        }
        for filename, payload in payloads.items():
            (artifact_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    def test_ready_bundle_returns_ready_decision(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            self._write_ready_bundle(artifact_dir)

            log = build_decision_log(
                artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            markdown = render_markdown(log)

        self.assertEqual(log["decision"], "ready")
        self.assertEqual(log["blockers"], [])
        self.assertIn("Analytical Decision Log", markdown)
        self.assertIn("without making operational targeting claims", log["safe_scope"])

    def test_missing_validation_receipt_blocks_decision(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            self._write_ready_bundle(artifact_dir)
            (artifact_dir / "handoff-validation-receipt.json").unlink()

            log = build_decision_log(artifact_dir)

        self.assertEqual(log["decision"], "blocked")
        self.assertTrue(any("handoff-validation-receipt.json" in item for item in log["blockers"]))

    def test_warning_artifact_requires_review(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            self._write_ready_bundle(artifact_dir)
            (artifact_dir / "uncertainty-review-packet.json").write_text(
                json.dumps({"status": "ready", "limitations": ["synthetic examples only"]}),
                encoding="utf-8",
            )

            log = build_decision_log(artifact_dir)

        self.assertEqual(log["decision"], "needs_review")
        self.assertTrue(any("uncertainty-review-packet.json" in item for item in log["warnings"]))

    def test_writers_create_markdown_and_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir) / "artifacts"
            artifact_dir.mkdir()
            self._write_ready_bundle(artifact_dir)
            markdown_path = Path(temp_dir) / "decision-log.md"
            json_path = Path(temp_dir) / "decision-log.json"
            log = build_decision_log(
                artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

            write_outputs(log, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Analytical Decision Log", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(parsed["decision"], "ready")


if __name__ == "__main__":
    unittest.main()
