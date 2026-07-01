"""Static checks for the run decision record documentation index."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RunDecisionRecordNavigationTests(unittest.TestCase):
    def test_index_links_the_complete_decision_record_document_family(self) -> None:
        guide = (ROOT / "docs" / "run_decision_record_navigation.md").read_text(
            encoding="utf-8"
        )

        for path in [
            "docs/run_continuity_brief.md",
            "docs/run_decision_record.md",
            "docs/run_decision_record_schema.md",
            "docs/run_decision_record_quick_reference.md",
            "docs/run_decision_record_handoff_examples.md",
        ]:
            with self.subTest(path=path):
                self.assertIn(path, guide)
                self.assertTrue((ROOT / path).exists())

    def test_index_preserves_merge_evidence_and_blocker_language(self) -> None:
        guide = (ROOT / "docs" / "run_decision_record_navigation.md").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "final head SHA",
            "hosted checks",
            "local validation",
            "merge blockers",
            "compatibility",
            "rollback",
            "next follow-up",
            "required hosted checks are unavailable",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)

    def test_index_keeps_additive_scope_and_safe_analytical_framing_visible(self) -> None:
        guide = (ROOT / "docs" / "run_decision_record_navigation.md").read_text(
            encoding="utf-8"
        )

        for phrase in [
            "additive documentation",
            "does not change CLI behavior",
            "API contracts",
            "generated diagnostics",
            "repository-maintenance evidence",
            "must not be presented as real-world certainty",
            "operational targeting",
            "predictive truth",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, guide)


if __name__ == "__main__":
    unittest.main()
