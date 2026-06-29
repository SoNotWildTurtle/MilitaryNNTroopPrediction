from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "automation_pr_evidence_template.md"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"


class AutomationPREvidenceTemplateDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = DOC_PATH.read_text(encoding="utf-8")
        cls.changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

    def test_template_contains_required_pr_body_sections(self):
        required_phrases = [
            "## Summary",
            "## Implementation details",
            "## Analytical and UX rationale",
            "## Validation evidence",
            "## Final diff review",
            "## Risks and compatibility",
            "## Rollback",
            "## Dependencies and follow-up",
            "final head SHA",
            "target branch",
            "known limitations",
            "Best next step",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_template_preserves_required_hosted_checks_and_blockers(self):
        required_phrases = [
            "CI",
            "Analytical Framing Audit",
            "Handoff Validation Receipt",
            "Missing, queued, stale, skipped, cancelled, failed, or wrong-head hosted validation remains a blocker",
            "precise failing job",
            "schema field",
            "artifact path",
            "brittle assertion",
            "compatibility condition",
            "narrowest relevant command",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_template_keeps_safe_analytical_scope(self):
        required_phrases = [
            "analytical estimates",
            "synthetic fixtures",
            "static previews",
            "reviewer handoff evidence",
            "not operational targeting advice",
            "real-world certainty",
            "does not run prediction workflows",
            "does not fetch live data",
            "unsafe operational instructions",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_template_links_to_existing_runbooks_without_replacing_them(self):
        required_docs = [
            "docs/automation_run_preflight.md",
            "docs/validation_evidence_crosswalk.md",
            "docs/hosted_check_evidence_log.md",
            "docs/merge_readiness_record_template.md",
            "docs/post_merge_verification_receipt.md",
        ]
        for doc_path in required_docs:
            with self.subTest(doc_path=doc_path):
                self.assertIn(doc_path, self.doc)

    def test_template_documents_narrow_reruns_and_rollback(self):
        required_phrases = [
            "python -m unittest tests.test_automation_pr_evidence_template_docs",
            "make ci-triage",
            "make workflow-gate-summary",
            "make triage-summary",
            "make handoff-validation-receipt",
            "make verify",
            "documentation/test/changelog revert",
            "should not remove existing PR workflows",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_changelog_references_template(self):
        self.assertIn("automation pr evidence template", self.changelog.lower())
        self.assertIn("final head sha", self.changelog.lower())
        self.assertIn("required hosted checks", self.changelog.lower())


if __name__ == "__main__":
    unittest.main()
