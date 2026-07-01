"""Static regression checks for strict implementation acceptance handoff docs."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StrictHandoffDocumentationTests(unittest.TestCase):
    def test_schema_contract_documents_strict_mode(self) -> None:
        schema_doc = (ROOT / "docs" / "implementation_acceptance_schema.md").read_text(encoding="utf-8")

        required_phrases = [
            "## Strict handoff validation mode",
            "python -m app.cli.implementation_acceptance_handoff",
            "--strict",
            "returns exit status `0` only when",
            "returns exit status `1`",
            "merge_blockers",
            "gate_evidence_readiness_summary.ready_for_merge_evidence_review",
            "hosted checks",
            "review-thread status",
            "final diff review",
            "Compatibility and Rollback",
            "Safe analytical framing",
            "not operational tasking",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, schema_doc)

    def test_changelog_records_strict_mode_follow_up(self) -> None:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

        self.assertIn("Documented strict `implementation_acceptance_handoff --strict` validation mode", changelog)
        self.assertIn("offline exit-code contract", changelog)
        self.assertIn("safe analytical limits", changelog)


if __name__ == "__main__":
    unittest.main()
