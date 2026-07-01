"""Static regression checks for run decision record schema docs."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RunDecisionRecordSchemaDocumentationTests(unittest.TestCase):
    def test_schema_contract_documents_required_fields_and_producer(self) -> None:
        schema_doc = (ROOT / "docs" / "run_decision_record_schema.md").read_text(encoding="utf-8")

        required_phrases = [
            "# Run Decision Record JSON Schema Contract",
            "python -m app.cli.next_increment_candidates",
            "--decision-record-path /tmp/run-decision-record.json",
            "schema_version` is currently `1.0`",
            "ready_for_implementation",
            "selected_candidate",
            "alternatives_considered",
            "required_evidence_before_merge",
            "validation_plan",
            "merge_blockers",
            "safe_scope",
            "compatibility_notes",
            "rollback_notes",
            "next_follow_up_candidate",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, schema_doc)

    def test_schema_contract_preserves_merge_blocker_and_safety_framing(self) -> None:
        schema_doc = (ROOT / "docs" / "run_decision_record_schema.md").read_text(encoding="utf-8")

        required_phrases = [
            "final_head_sha",
            "hosted_required_checks",
            "local_validation_commands",
            "diff_review_for_deletions_secrets_generated_artifacts_and_unsupported_claims",
            "safe_analytical_framing_confirmation",
            "Missing evidence remains a merge blocker",
            "not a substitute for hosted checks",
            "Compatibility and Rollback",
            "Safe analytical framing",
            "not operational tasking",
            "proof that a prediction is true",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, schema_doc)


if __name__ == "__main__":
    unittest.main()
