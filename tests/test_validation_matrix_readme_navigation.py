from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"


class ValidationMatrixReadmeNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = README_PATH.read_text(encoding="utf-8")
        cls.changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

    def test_structure_lists_validation_failure_matrix(self):
        self.assertIn("docs/validation_failure_reproduction_matrix.md", self.readme)
        self.assertIn("failure-to-rerun matrix", self.readme)
        self.assertIn("hosted CI, CLI, schema, artifact, documentation", self.readme)
        self.assertIn("analytical-framing blockers", self.readme)

    def test_fast_first_run_routes_failed_validation_to_matrix(self):
        fast_first_run_section = self.readme.split("### Fast first run", 1)[1].split(
            "For a guided local setup path", 1
        )[0]
        required_phrases = [
            "docs/ci_troubleshooting.md",
            "docs/validation_failure_reproduction_matrix.md",
            "narrowest safe rerun",
            "docs/reviewer_handoff_navigation.md",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, fast_first_run_section)

    def test_validation_matrix_navigation_preserves_safe_scope(self):
        lowered = self.readme.lower()
        self.assertIn("safe pre-pr pass", lowered)
        self.assertIn("analytical-framing failure", lowered)
        self.assertIn("safe demo records", lowered)
        self.assertIn("must not be presented as operational truth", lowered)
        self.assertIn("does not validate operational truth or imply certainty", lowered)

    def test_changelog_mentions_readme_navigation(self):
        lowered = self.changelog.lower()
        self.assertIn("readme navigation", lowered)
        self.assertIn("validation_failure_reproduction_matrix.md", lowered)
        self.assertIn("narrowest safe rerun", lowered)
        self.assertIn("without duplicating existing guidance", lowered)


if __name__ == "__main__":
    unittest.main()
