"""Regression tests for the handoff validation receipt CI workflow.

These tests parse static workflow/docs text so they stay lightweight and do not
invoke network access, live data collection, model inference, deployment, or
operational workflows.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "handoff-validation-receipt.yml"
DOC = ROOT / "docs" / "handoff_validation_receipt_workflow.md"


class HandoffValidationReceiptWorkflowTests(unittest.TestCase):
    """Keep the focused receipt workflow aligned with reviewer handoff expectations."""

    def test_workflow_runs_focused_receipt_validation(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("name: Handoff Validation Receipt", content)
        self.assertIn("python -m unittest tests.test_handoff_validation_receipt", content)
        self.assertIn("make ci-report ARTIFACT_DIR=ci_artifacts", content)
        self.assertIn("python -m app.cli.handoff_validation_receipt", content)
        self.assertIn("ci_artifacts/handoff-validation-receipt.md", content)
        self.assertIn("ci_artifacts/handoff-validation-receipt.json", content)
        self.assertIn("actions/upload-artifact@v4", content)
        self.assertIn("handoff-validation-receipt", content)

    def test_workflow_preserves_uncertainty_scope_assertion(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("claim of predictive certainty", content)
        self.assertIn("Assert receipt artifacts exist", content)
        self.assertIn("test -s ci_artifacts/handoff-validation-receipt.md", content)
        self.assertIn("test -s ci_artifacts/handoff-validation-receipt.json", content)

    def test_workflow_documentation_covers_reproduction_review_and_rollback(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        self.assertIn("Local reproduction", content)
        self.assertIn("Review guidance", content)
        self.assertIn("Compatibility and rollback", content)
        self.assertIn("python -m unittest tests.test_handoff_validation_receipt", content)
        self.assertIn("python -m app.cli.handoff_validation_receipt", content)
        self.assertIn("does not run collection, live feeds, prediction", content)


if __name__ == "__main__":
    unittest.main()
