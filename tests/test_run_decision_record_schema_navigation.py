"""Static checks for run decision record documentation links."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RunDecisionRecordSchemaNavigationTests(unittest.TestCase):
    def test_changelog_records_schema_navigation_increment(self) -> None:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("run decision record schema contract", changelog)
        self.assertIn("merge-evidence expectations", changelog)
        self.assertIn("rollback path", changelog)

    def test_schema_contract_and_overview_remain_discoverable(self) -> None:
        schema_doc = (ROOT / "docs" / "run_decision_record_schema.md").read_text(encoding="utf-8")
        overview_doc = (ROOT / "docs" / "run_decision_record.md").read_text(encoding="utf-8")

        for phrase in [
            "# Run Decision Record JSON Schema Contract",
            "required_evidence_before_merge",
            "validation_plan",
            "merge_blockers",
        ]:
            with self.subTest(schema_phrase=phrase):
                self.assertIn(phrase, schema_doc)

        for phrase in [
            "# Run decision record",
            "--decision-record-path",
            "required_evidence_before_merge",
            "compatibility_notes",
            "rollback_notes",
        ]:
            with self.subTest(overview_phrase=phrase):
                self.assertIn(phrase, overview_doc)


if __name__ == "__main__":
    unittest.main()
