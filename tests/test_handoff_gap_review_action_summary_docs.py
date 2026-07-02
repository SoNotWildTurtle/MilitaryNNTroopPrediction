"""Static coverage for the handoff gap-review action summary guide."""

from __future__ import annotations

from pathlib import Path
import unittest


DOC_PATH = Path("docs/handoff_gap_review_action_summary.md")


class HandoffGapReviewActionSummaryDocTests(unittest.TestCase):
    """Keep reviewer action-summary guidance safe, actionable, and offline scoped."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.markdown = DOC_PATH.read_text(encoding="utf-8")

    def test_documents_action_priority_contract_and_blockers(self) -> None:
        self.assertIn("# Handoff Gap Review Action Summary", self.markdown)
        self.assertIn("reviewer_next_actions[]", self.markdown)
        self.assertIn("reviewer_action_summary", self.markdown)
        self.assertIn("priority=blocking", self.markdown)
        self.assertIn("Unknown future priority", self.markdown)
        self.assertIn("unavailable validation", self.markdown)
        self.assertIn("review_status_summary.merge_blocker_count", self.markdown)
        self.assertIn("review_status_summary.blocking_target_count", self.markdown)

    def test_documents_machine_readable_action_counts(self) -> None:
        self.assertIn("reviewer_action_summary.action_count", self.markdown)
        self.assertIn("reviewer_action_summary.priority_counts.blocking", self.markdown)
        self.assertIn("reviewer_action_summary.priority_counts.review", self.markdown)
        self.assertIn("reviewer_action_summary.unknown_priorities", self.markdown)
        self.assertIn("reviewer_action_summary.first_blocking_action", self.markdown)
        self.assertIn("missing `reviewer_action_summary`", self.markdown)

    def test_documents_narrow_reruns_before_broad_validation(self) -> None:
        self.assertIn("implementation_acceptance_handoff", self.markdown)
        self.assertIn("artifact_gap_report", self.markdown)
        self.assertIn("handoff_gap_report_review", self.markdown)
        self.assertIn("--strict", self.markdown)
        self.assertIn("same artifact directory", self.markdown)
        self.assertIn("final head SHA", self.markdown)

    def test_preserves_safe_analytical_scope_and_rollback(self) -> None:
        self.assertIn("does not collect live data", self.markdown)
        self.assertIn("does not prove a prediction", self.markdown)
        self.assertIn("operational targeting guidance", self.markdown)
        self.assertIn("Rollback by reverting the CLI, guide, changelog, and tests", self.markdown)
        self.assertIn("does not change prediction APIs", self.markdown)


if __name__ == "__main__":
    unittest.main()
