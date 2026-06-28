"""Static regression tests for workflow gate review guidance."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "workflow_gate_review_runbook.md"


class WorkflowGateReviewRunbookTests(unittest.TestCase):
    """Keep hosted validation gate handoff guidance safe and actionable."""

    def test_runbook_exists_and_names_required_gates(self) -> None:
        content = RUNBOOK.read_text(encoding="utf-8")

        self.assertIn("Workflow Gate Review Runbook", content)
        self.assertIn("`CI`", content)
        self.assertIn("`Analytical Framing Audit`", content)
        self.assertIn("`Handoff Validation Receipt`", content)

    def test_runbook_preserves_safe_analytical_scope(self) -> None:
        content = RUNBOOK.read_text(encoding="utf-8").lower()

        self.assertIn("not validate model quality", content)
        self.assertIn("operational targeting", content)
        self.assertIn("estimates with uncertainty", content)
        self.assertIn("not certainty", content)

    def test_runbook_requires_current_green_head_sha_before_merge(self) -> None:
        content = RUNBOOK.read_text(encoding="utf-8")

        self.assertIn("final PR head SHA", content)
        self.assertIn("complete, green", content)
        self.assertIn("Do not merge", content)
        self.assertIn("repository policy permits it", content)

    def test_runbook_lists_local_reproduction_commands(self) -> None:
        content = RUNBOOK.read_text(encoding="utf-8")

        self.assertIn("make verify ARTIFACT_DIR=ci_artifacts/local-review", content)
        self.assertIn("python -m app.cli.analytical_framing_audit", content)
        self.assertIn("make handoff-validation-receipt ARTIFACT_DIR=ci_artifacts", content)
        self.assertIn("python -m app.cli.workflow_gate_summary", content)


if __name__ == "__main__":
    unittest.main()
