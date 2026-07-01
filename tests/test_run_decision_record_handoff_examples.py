"""Static checks for run decision record handoff examples."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RunDecisionRecordHandoffExamplesTests(unittest.TestCase):
    def test_examples_preserve_required_merge_evidence_fields(self) -> None:
        guide = (ROOT / "docs" / "run_decision_record_handoff_examples.md").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "Selected candidate:",
            "Final head SHA:",
            "Required hosted checks:",
            "Local validation:",
            "Merge blockers:",
            "Compatibility impact:",
            "Rollback:",
            "Next follow-up:",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)

    def test_examples_keep_blocked_handoff_and_repair_guidance_visible(self) -> None:
        guide = (ROOT / "docs" / "run_decision_record_handoff_examples.md").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "Current blocker:",
            "Narrow reproduction:",
            "Root cause:",
            "Repair plan:",
            "without bypassing checks",
            "leave PR open until required checks pass",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)

    def test_examples_keep_additive_scope_and_safe_framing_visible(self) -> None:
        guide = (ROOT / "docs" / "run_decision_record_handoff_examples.md").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "additive navigation only",
            "documentation and static regression coverage only",
            "backwards compatible",
            "repository-maintenance evidence only",
            "do not imply certainty from incomplete validation",
            "no accidental deletions",
            "generated artifacts",
            "secrets",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)


if __name__ == "__main__":
    unittest.main()
