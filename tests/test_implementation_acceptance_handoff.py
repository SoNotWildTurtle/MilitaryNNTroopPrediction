"""Tests for offline implementation acceptance evidence handoff generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.implementation_acceptance_checklist import build_acceptance_checklist
from app.cli.implementation_acceptance_handoff import (
    SAFE_SCOPE,
    build_acceptance_handoff,
    render_markdown,
    write_outputs,
)


class ImplementationAcceptanceHandoffTests(unittest.TestCase):
    """Verify deterministic completed-evidence handoff behavior."""

    def _completed_checklist(self) -> dict:
        checklist = build_acceptance_checklist(
            {
                "selected_candidate": {
                    "candidate_id": "candidate-07",
                    "title": "Persist completed acceptance evidence",
                    "focus_area": "operator_handoff",
                    "status": "recommended",
                }
            },
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        completed_rows = []
        for entry in checklist["gate_evidence_manifest"]:
            completed = dict(entry)
            completed["evidence_status"] = "verified"
            completed["evidence_sources"] = [f"https://example.invalid/evidence/{entry['gate_id']}"]
            completed["reviewer_notes"] = "Verified in final-head-SHA review evidence."
            completed["missing_evidence_blocks_merge"] = False
            completed_rows.append(completed)
        checklist["gate_evidence_manifest"] = completed_rows
        return checklist

    def test_completed_manifest_is_preserved_and_marked_ready(self) -> None:
        handoff = build_acceptance_handoff(
            self._completed_checklist(),
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        markdown = render_markdown(handoff)

        self.assertEqual(handoff["schema_version"], "1.0")
        self.assertEqual(handoff["status"], "ready_for_review")
        self.assertEqual(handoff["candidate"]["candidate_id"], "candidate-07")
        self.assertEqual(handoff["merge_blockers"], [])
        self.assertTrue(handoff["gate_evidence_readiness_summary"]["ready_for_merge_evidence_review"])
        self.assertEqual(handoff["gate_evidence_readiness_summary"]["missing_blocking_gate_ids"], [])
        self.assertEqual(len(handoff["completed_gate_evidence_manifest"]), 6)
        self.assertIn("Completed gate evidence manifest", markdown)
        self.assertIn("Ready for merge evidence review: True", markdown)
        self.assertIn(SAFE_SCOPE, markdown)

    def test_missing_blocking_evidence_remains_a_merge_blocker(self) -> None:
        checklist = self._completed_checklist()
        checklist["gate_evidence_manifest"][0]["evidence_sources"] = []
        checklist["gate_evidence_manifest"][0]["missing_evidence_blocks_merge"] = True
        handoff = build_acceptance_handoff(
            checklist,
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(handoff["status"], "blocked_missing_evidence")
        self.assertIn("scope-framing", handoff["gate_evidence_readiness_summary"]["missing_blocking_gate_ids"])
        self.assertTrue(any("scope-framing" in blocker for blocker in handoff["merge_blockers"]))

    def test_empty_or_invalid_source_is_blocked_safely(self) -> None:
        handoff = build_acceptance_handoff(generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        markdown = render_markdown(handoff)

        self.assertEqual(handoff["status"], "blocked_missing_evidence")
        self.assertIn("No gate_evidence_manifest rows", handoff["merge_blockers"][0])
        self.assertFalse(handoff["gate_evidence_readiness_summary"]["ready_for_merge_evidence_review"])
        self.assertIn("not operational tasking", markdown)

    def test_writers_create_markdown_and_json_outputs(self) -> None:
        handoff = build_acceptance_handoff(
            self._completed_checklist(),
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "handoff.md"
            json_path = Path(temp_dir) / "handoff.json"
            write_outputs(handoff, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Implementation Acceptance Evidence Handoff", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(parsed["status"], "ready_for_review")
        self.assertEqual(parsed["gate_evidence_readiness_summary"]["ready_blocking_rows"], 6)
        self.assertIn("rollback", parsed["rollback_notes"].lower())


if __name__ == "__main__":
    unittest.main()
