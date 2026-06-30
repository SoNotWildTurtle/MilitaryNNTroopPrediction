"""Tests for offline implementation acceptance checklist generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.implementation_acceptance_checklist import (
    SAFE_SCOPE,
    build_acceptance_checklist,
    render_markdown,
    write_outputs,
)


class ImplementationAcceptanceChecklistTests(unittest.TestCase):
    """Verify deterministic, non-operational acceptance evidence behavior."""

    def test_builds_checklist_from_decision_record_candidate(self) -> None:
        checklist = build_acceptance_checklist(
            {
                "schema_version": "1.0",
                "selected_candidate": {
                    "candidate_id": "candidate-03",
                    "title": "Add uncertainty review handoff evidence",
                    "focus_area": "uncertainty_review",
                    "status": "recommended",
                    "suggested_artifact": "uncertainty review packet",
                    "rationale": "Roadmap demand exists with limited recent overlap.",
                    "validation_commands": ["python -m unittest tests.test_uncertainty_review"],
                },
                "merge_blockers": ["Hosted checks unavailable for the final head SHA."],
            },
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(checklist["schema_version"], "1.0")
        self.assertEqual(checklist["status"], "ready_for_review_planning")
        self.assertEqual(checklist["candidate"]["candidate_id"], "candidate-03")
        self.assertIn("avoid wording", " ".join(checklist["focus_gate_hints"]))
        self.assertIn("Hosted checks unavailable", checklist["merge_blockers"][0])
        self.assertIn("not operational tasking", checklist["safe_scope"])
        self.assertIn("final_head_sha", checklist["handoff_fields_to_capture"])

    def test_defaults_to_safe_general_handoff_without_candidate_context(self) -> None:
        checklist = build_acceptance_checklist(generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        markdown = render_markdown(checklist)

        self.assertEqual(checklist["status"], "needs_candidate_context")
        self.assertEqual(checklist["candidate"]["focus_area"], "general_handoff")
        self.assertIn("Hosted required checks must pass", checklist["merge_blockers"][0])
        self.assertIn("Safe analytical scope", markdown)
        self.assertIn(SAFE_SCOPE, markdown)

    def test_acceptance_gates_preserve_required_review_evidence(self) -> None:
        checklist = build_acceptance_checklist(
            {
                "recommended_candidate": {
                    "candidate_id": "candidate-02",
                    "title": "Add artifact provenance validation evidence",
                    "focus_area": "artifact_provenance",
                    "status": "recommended",
                }
            },
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        gate_ids = {gate["gate_id"] for gate in checklist["acceptance_gates"]}

        self.assertIn("scope-framing", gate_ids)
        self.assertIn("artifact-provenance", gate_ids)
        self.assertIn("rollback-recovery", gate_ids)
        self.assertTrue(all(gate["blocking_if_missing"] for gate in checklist["acceptance_gates"]))
        self.assertTrue(any("manifest" in hint for hint in checklist["focus_gate_hints"]))

    def test_writers_create_markdown_and_json_outputs(self) -> None:
        checklist = build_acceptance_checklist(
            {
                "selected_candidate": {
                    "candidate_id": "candidate-04",
                    "title": "Add operator handoff readiness evidence",
                    "focus_area": "operator_handoff",
                    "status": "recommended",
                }
            },
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "acceptance.md"
            json_path = Path(temp_dir) / "acceptance.json"
            write_outputs(checklist, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Implementation Acceptance Checklist", markdown)
        self.assertIn("operator handoff", markdown.lower())
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")
        self.assertEqual(parsed["candidate"]["candidate_id"], "candidate-04")
        self.assertIn("revert", parsed["rollback_notes"].lower())


if __name__ == "__main__":
    unittest.main()
