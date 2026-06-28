"""Tests for operator exception register generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.operator_exception_register import (
    build_exception_register,
    render_markdown,
    render_text,
    write_outputs,
)


class OperatorExceptionRegisterTests(unittest.TestCase):
    """Verify deterministic exception register behavior for handoff diagnostics."""

    def _write_ready_bundle(self, artifact_dir: Path) -> None:
        payloads = {
            "decision-log.json": {"decision": "ready", "blockers": [], "warnings": []},
            "handoff-closeout-summary.json": {"closeout_status": "ready", "blockers": [], "warnings": []},
            "handoff-validation-receipt.json": {"status": "ready", "blockers": [], "warnings": []},
            "handoff-readiness-scorecard.json": {"status": "ready", "score": 100},
            "provenance-validation-matrix.json": {"status": "ready", "warnings": []},
            "evidence-checklist.json": {"status": "ready", "blockers": []},
            "handoff-integrity-report.json": {"status": "ready", "warnings": []},
            "artifact-manifest.json": {"status": "ready", "files": []},
        }
        for filename, payload in payloads.items():
            (artifact_dir / filename).write_text(json.dumps(payload), encoding="utf-8")

    def test_ready_bundle_has_no_exceptions(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            self._write_ready_bundle(artifact_dir)

            register = build_exception_register(
                artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            markdown = render_markdown(register)
            text = render_text(register)

        self.assertEqual(register["status"], "ready")
        self.assertEqual(register["exception_count"], 0)
        self.assertIn("No generated exceptions", markdown)
        self.assertIn("Exceptions=READY", text)
        self.assertIn("no operational certainty claimed", text)

    def test_missing_artifact_becomes_blocker(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            self._write_ready_bundle(artifact_dir)
            (artifact_dir / "decision-log.json").unlink()

            register = build_exception_register(artifact_dir)

        self.assertEqual(register["status"], "blocked")
        self.assertEqual(register["counts"]["blocker"], 1)
        self.assertTrue(any(entry["kind"] == "missing_artifact" for entry in register["entries"]))
        self.assertTrue(any("decision-log.json" in entry["artifact_path"] for entry in register["entries"]))

    def test_warnings_include_owner_hints(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            self._write_ready_bundle(artifact_dir)
            (artifact_dir / "provenance-validation-matrix.json").write_text(
                json.dumps({"status": "ready", "warnings": ["provenance label requires manual review"]}),
                encoding="utf-8",
            )

            register = build_exception_register(artifact_dir)

        self.assertEqual(register["status"], "needs_review")
        self.assertEqual(register["counts"]["warning"], 1)
        self.assertEqual(register["entries"][0]["owner_hint"], "data/provenance reviewer")
        self.assertIn("accepted limitation", register["next_action"])

    def test_blocker_and_warning_counts_are_prioritized(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            self._write_ready_bundle(artifact_dir)
            (artifact_dir / "evidence-checklist.json").write_text(
                json.dumps({"status": "blocked", "blockers": ["evidence checklist missing validation receipt"]}),
                encoding="utf-8",
            )
            (artifact_dir / "handoff-integrity-report.json").write_text(
                json.dumps({"status": "needs_review", "warnings": ["uncertainty packet not attached"]}),
                encoding="utf-8",
            )

            register = build_exception_register(artifact_dir)
            markdown = render_markdown(register)

        self.assertEqual(register["status"], "blocked")
        self.assertEqual(register["counts"]["blocker"], 1)
        self.assertEqual(register["counts"]["warning"], 1)
        self.assertIn("analytical evidence reviewer", markdown)
        self.assertIn("analytical methods reviewer", markdown)

    def test_writers_create_markdown_json_and_text(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir) / "artifacts"
            artifact_dir.mkdir()
            self._write_ready_bundle(artifact_dir)
            markdown_path = Path(temp_dir) / "exceptions.md"
            json_path = Path(temp_dir) / "exceptions.json"
            text_path = Path(temp_dir) / "exceptions.txt"
            register = build_exception_register(
                artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

            write_outputs(register, markdown_path, json_path, text_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            text = text_path.read_text(encoding="utf-8")

        self.assertIn("# Operator Exception Register", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(parsed["status"], "ready")
        self.assertIn("Exceptions=READY", text)


if __name__ == "__main__":
    unittest.main()
