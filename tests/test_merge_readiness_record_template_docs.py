"""Static regression coverage for merge readiness record guidance.

These tests keep the merge-readiness template aligned with the repository's
safe, additive review process without calling hosted CI APIs, model inference,
live data sources, or external services.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "merge_readiness_record_template.md"


class MergeReadinessRecordTemplateDocsTests(unittest.TestCase):
    """Ensure the copyable merge record stays complete and safety framed."""

    def test_template_captures_required_merge_evidence(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        required_terms = [
            "Pull request",
            "Target branch",
            "Base SHA reviewed",
            "Final head SHA reviewed",
            "Merge method expected",
            "Required hosted checks on final head SHA",
            "Workflow run URLs",
            "Local validation evidence",
            "Diagnostics bundle reviewed",
            "Final diff review",
            "Review state",
            "Compatibility impact",
            "Rollback path",
            "Safe analytical framing confirmed",
        ]
        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_template_keeps_unavailable_validation_blocking(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        self.assertIn("blocked_ci", content)
        self.assertIn("unavailable", content)
        self.assertIn("Do not treat a local-only pass", content)
        self.assertIn("replace required hosted checks", content)

    def test_template_preserves_safe_analytical_scope(self) -> None:
        content = DOC.read_text(encoding="utf-8").lower()

        self.assertIn("does not collect live data", content)
        self.assertIn("perform targeting", content)
        self.assertIn("analytical estimates", content)
        self.assertIn("uncertainty", content)
        self.assertIn("operational targeting", content)

    def test_template_documents_all_decision_states_and_rollback(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for state in [
            "ready_to_merge",
            "blocked_ci",
            "blocked_review",
            "blocked_scope",
            "needs_handoff_update",
        ]:
            with self.subTest(state=state):
                self.assertIn(state, content)
        self.assertIn("Rollback is a normal documentation revert", content)


if __name__ == "__main__":
    unittest.main()
