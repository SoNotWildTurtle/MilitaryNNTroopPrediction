"""Regression tests for the analytical framing audit CI workflow.

These tests parse static workflow/docs text so they stay lightweight and do not
invoke network access, live data collection, model inference, deployment, or
operational workflows.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "analytical-framing-audit.yml"
DOC = ROOT / "docs" / "analytical_framing_audit_workflow.md"


class AnalyticalFramingAuditWorkflowTests(unittest.TestCase):
    """Keep the focused audit workflow aligned with safe reviewer expectations."""

    def test_workflow_runs_focused_audit_validation(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("name: Analytical Framing Audit", content)
        self.assertIn("python -m unittest tests.test_analytical_framing_audit", content)
        self.assertIn("python -m app.cli.analytical_framing_audit", content)
        self.assertIn("ci_artifacts/analytical-framing-audit.md", content)
        self.assertIn("ci_artifacts/analytical-framing-audit.json", content)
        self.assertIn("actions/upload-artifact@v4", content)
        self.assertIn("analytical-framing-audit", content)

    def test_workflow_uses_safe_synthetic_seed(self) -> None:
        content = WORKFLOW.read_text(encoding="utf-8").lower()

        self.assertIn("analytical estimates", content)
        self.assertIn("synthetic examples", content)
        self.assertIn("operational certainty", content)
        self.assertIn("framing-audit-seed", content)

    def test_workflow_documentation_covers_reproduction_and_rollback(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        self.assertIn("Local reproduction", content)
        self.assertIn("Review guidance", content)
        self.assertIn("Compatibility and rollback", content)
        self.assertIn("python -m unittest tests.test_analytical_framing_audit", content)
        self.assertIn("python -m app.cli.analytical_framing_audit", content)
        self.assertIn("does not run collection, prediction, targeting", content)


if __name__ == "__main__":
    unittest.main()
