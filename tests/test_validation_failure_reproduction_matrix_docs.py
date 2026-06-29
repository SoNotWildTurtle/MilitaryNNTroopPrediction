from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "validation_failure_reproduction_matrix.md"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"


class ValidationFailureReproductionMatrixDocsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = DOC_PATH.read_text(encoding="utf-8")
        cls.changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

    def test_matrix_covers_required_failure_classes(self):
        required_phrases = [
            "Python import, syntax, or packaging failure",
            "Unit or regression test failure",
            "CLI smoke failure",
            "Schema or artifact validation failure",
            "Analytical framing audit failure",
            "Handoff validation receipt failure",
            "Documentation static regression failure",
            "Release bundle or manifest failure",
            "Environment or optional dependency warning",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_matrix_preserves_blocker_and_rerun_discipline(self):
        required_phrases = [
            "final head SHA",
            "narrowest relevant slice",
            "Never treat a missing hosted conclusion",
            "unresolved review thread",
            "stale head SHA",
            "Do not convert hard failures into warnings",
            "strict behavior checks",
        ]
        lowered = self.doc.lower()
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), lowered)

    def test_matrix_includes_review_evidence_fields(self):
        required_fields = [
            "final_head_sha",
            "target_branch",
            "workflow_name",
            "run_url",
            "narrow_rerun",
            "broad_rerun",
            "artifacts_reviewed",
            "blocker_status",
            "compatibility_impact",
            "rollback_path",
        ]
        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, self.doc)

    def test_matrix_keeps_safe_analytical_scope_and_rollback(self):
        required_phrases = [
            "analytical estimates",
            "synthetic placeholders",
            "does not certify operational certainty",
            "guidance-only",
            "Roll back by reverting the documentation and its static regression test",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_changelog_mentions_matrix(self):
        self.assertIn("validation failure reproduction matrix", self.changelog.lower())
        self.assertIn("narrowest safe local rerun", self.changelog.lower())


if __name__ == "__main__":
    unittest.main()
