"""Static regression coverage for review blocker decision guidance.

These tests keep the blocker decision tree aligned with the repository's safe,
additive review process without calling hosted CI APIs, model inference, live data
sources, or external services.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "review_blocker_decision_tree.md"


class ReviewBlockerDecisionTreeDocsTests(unittest.TestCase):
    """Ensure blocker triage guidance stays complete and safety framed."""

    def test_documents_all_merge_blocker_classes(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for state in [
            "blocked_ci",
            "blocked_review",
            "blocked_scope",
            "needs_handoff_update",
            "ready_to_merge",
        ]:
            with self.subTest(state=state):
                self.assertIn(state, content)

    def test_includes_narrow_reproduction_commands(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for command in [
            "make doctor",
            "python -m compileall app tests",
            "python -m unittest discover -s tests -p 'test_*.py'",
            "make workflow-gate-summary",
            "make handoff-validation-receipt",
            "make triage-summary",
            "make verify",
        ]:
            with self.subTest(command=command):
                self.assertIn(command, content)

    def test_preserves_final_diff_and_handoff_evidence(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        required_terms = [
            "final head SHA",
            "required hosted workflows",
            "review threads",
            "branch protection",
            "Final diff summary",
            "Compatibility impact",
            "rollback path",
            "known limitations",
            "Safe analytical framing confirmation",
        ]
        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_keeps_safe_analytical_scope(self) -> None:
        content = DOC.read_text(encoding="utf-8").lower()

        self.assertIn("does not fetch live data", content)
        self.assertIn("perform targeting", content)
        self.assertIn("analytical estimates", content)
        self.assertIn("uncertainty", content)
        self.assertIn("operational targeting", content)
        self.assertIn("synthetic fixture", content)

    def test_documents_compatibility_and_rollback_limits(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        self.assertIn("changes no runtime behavior", content)
        self.assertIn("APIs", content)
        self.assertIn("schemas", content)
        self.assertIn("workflows", content)
        self.assertIn("Rollback is a normal documentation/test revert", content)


if __name__ == "__main__":
    unittest.main()
