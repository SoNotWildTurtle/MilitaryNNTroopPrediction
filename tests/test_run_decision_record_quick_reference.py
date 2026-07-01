"""Static checks for the run decision record quick-reference guide."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RunDecisionRecordQuickReferenceTests(unittest.TestCase):
    def test_quick_reference_links_primary_handoff_documents(self) -> None:
        guide = (ROOT / "docs" / "run_decision_record_quick_reference.md").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "docs/run_continuity_brief.md",
            "docs/run_decision_record.md",
            "docs/run_decision_record_schema.md",
            "docs/implementation_acceptance_checklist.md",
            "docs/implementation_acceptance_schema.md",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)

    def test_quick_reference_preserves_merge_blocker_and_rollback_guidance(self) -> None:
        guide = (ROOT / "docs" / "run_decision_record_quick_reference.md").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "required_evidence_before_merge",
            "validation_plan",
            "merge_blockers",
            "compatibility_notes",
            "rollback_notes",
            "final head SHA",
            "unavailable required validation",
            "Revert only this file",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)

    def test_quick_reference_keeps_safe_analytical_scope_visible(self) -> None:
        guide = (ROOT / "docs" / "run_decision_record_quick_reference.md").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "does not collect live data",
            "run detection",
            "run prediction",
            "repository-maintenance evidence",
            "must not be presented as operational targeting guidance",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)


if __name__ == "__main__":
    unittest.main()
