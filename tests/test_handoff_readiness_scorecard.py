"""Tests for handoff readiness scorecard generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.handoff_readiness_scorecard import (
    build_handoff_readiness_scorecard,
    render_markdown,
    write_outputs,
)


class HandoffReadinessScorecardTests(unittest.TestCase):
    """Verify deterministic scorecard behavior for handoff diagnostics."""

    def _ready_payloads(self) -> dict[str, dict[str, object]]:
        return {
            "provenance-validation-matrix.json": {"status": "ready"},
            "evidence-checklist.json": {"status": "ready"},
            "handoff-validation-receipt.json": {"status": "ready", "blockers": []},
            "artifact-gap-report.json": {"status": "ready", "missing_expected": []},
        }

    def test_ready_scorecard_scores_full_weight(self) -> None:
        scorecard = build_handoff_readiness_scorecard(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            payloads=self._ready_payloads(),
        )
        markdown = render_markdown(scorecard)

        self.assertEqual(scorecard["status"], "ready")
        self.assertEqual(scorecard["score"], 100.0)
        self.assertEqual(scorecard["blockers"], [])
        self.assertIn("# Handoff Readiness Scorecard", markdown)
        self.assertIn("without asserting real-world truth", scorecard["safe_scope"])

    def test_missing_artifact_blocks_and_lowers_score(self) -> None:
        payloads = self._ready_payloads()
        payloads.pop("handoff-validation-receipt.json")
        scorecard = build_handoff_readiness_scorecard(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            payloads=payloads,
        )

        self.assertEqual(scorecard["status"], "blocked")
        self.assertLess(scorecard["score"], 100.0)
        self.assertTrue(any("Validation receipt" in blocker for blocker in scorecard["blockers"]))

    def test_warning_category_requires_review(self) -> None:
        payloads = self._ready_payloads()
        payloads["evidence-checklist.json"] = {"status": "ready", "warnings": ["manual review accepted"]}
        scorecard = build_handoff_readiness_scorecard(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            payloads=payloads,
        )

        self.assertEqual(scorecard["status"], "needs_review")
        self.assertEqual(scorecard["blockers"], [])
        self.assertTrue(any("Evidence completeness" in warning for warning in scorecard["warnings"]))

    def test_fallback_payload_supports_existing_validation_output(self) -> None:
        payloads = self._ready_payloads()
        payloads.pop("handoff-validation-receipt.json")
        payloads["reviewer-handoff-validation.json"] = {"valid": True}
        scorecard = build_handoff_readiness_scorecard(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            payloads=payloads,
        )

        validation_row = next(row for row in scorecard["categories"] if row["name"] == "validation")
        self.assertEqual(validation_row["status"], "ready")
        self.assertEqual(validation_row["source_artifact"], "reviewer-handoff-validation.json")

    def test_writers_create_markdown_and_json(self) -> None:
        scorecard = build_handoff_readiness_scorecard(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            payloads=self._ready_payloads(),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "handoff-readiness-scorecard.md"
            json_path = Path(temp_dir) / "handoff-readiness-scorecard.json"

            write_outputs(scorecard, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Handoff Readiness Scorecard", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(parsed["score"], 100.0)


if __name__ == "__main__":
    unittest.main()
