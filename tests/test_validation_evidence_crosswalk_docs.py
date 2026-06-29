from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "validation_evidence_crosswalk.md"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"


class ValidationEvidenceCrosswalkDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = DOC_PATH.read_text(encoding="utf-8")
        cls.changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

    def test_crosswalk_maps_reviewer_questions_to_evidence(self):
        required_phrases = [
            "Reviewer question",
            "Primary local command",
            "Hosted evidence to capture",
            "Artifact or document to inspect",
            "Merge blocker if missing or stale",
            "final head SHA",
            "required_checks",
            "local_validation",
            "artifacts_reviewed",
            "diff_review",
            "compatibility_impact",
            "rollback_path",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_crosswalk_preserves_required_workflow_names_and_commands(self):
        required_phrases = [
            "CI",
            "Analytical Framing Audit",
            "Handoff Validation Receipt",
            "make doctor",
            "make test",
            "make ci-report",
            "make validate-handoff",
            "make workflow-gate-summary",
            "make triage-summary",
            "make handoff-validation-receipt",
            "python -m unittest tests.test_validation_evidence_crosswalk_docs",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_crosswalk_keeps_safe_scope_and_blocker_discipline(self):
        required_phrases = [
            "analytical estimates",
            "not operational targeting instructions or certainty",
            "synthetic fixtures",
            "A missing hosted conclusion",
            "unresolved review thread",
            "Do not bypass failing workflows",
            "preserving existing files, schemas, commands, and unknown JSON fields",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_crosswalk_links_to_existing_guidance_without_replacing_it(self):
        required_docs = [
            "docs/validation_failure_reproduction_matrix.md",
            "docs/workflow_gate_review_runbook.md",
            "docs/hosted_check_evidence_log.md",
            "docs/artifact_consumer_compatibility.md",
            "docs/artifact_consumer_validation_profile.md",
            "docs/post_merge_verification_receipt.md",
        ]
        for doc_path in required_docs:
            with self.subTest(doc_path=doc_path):
                self.assertIn(doc_path, self.doc)

    def test_changelog_references_crosswalk(self):
        self.assertIn("validation evidence crosswalk", self.changelog.lower())
        self.assertIn("reviewer questions", self.changelog.lower())
        self.assertIn("hosted check evidence", self.changelog.lower())


if __name__ == "__main__":
    unittest.main()
