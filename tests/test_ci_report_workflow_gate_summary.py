"""Static regression tests for workflow gate summary CI bundle wiring.

These tests inspect the diagnostic bundle shell script as text so they remain
safe, offline, and independent of GitHub Actions, MongoDB, ML dependencies, or
live prediction workflows.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CI_REPORT = ROOT / "scripts" / "ci_report.sh"


class CiReportWorkflowGateSummaryTests(unittest.TestCase):
    """Keep workflow gate summary artifacts visible in diagnostics bundles."""

    def test_ci_report_exports_workflow_gate_summary_outputs(self) -> None:
        content = CI_REPORT.read_text(encoding="utf-8")

        self.assertIn("app.cli.workflow_gate_summary", content)
        self.assertIn("workflow-gate-summary.md", content)
        self.assertIn("workflow-gate-summary.json", content)

    def test_ci_report_captures_workflow_gate_summary_help(self) -> None:
        content = CI_REPORT.read_text(encoding="utf-8")

        self.assertIn("workflow-gate-summary-help.txt", content)
        self.assertIn("--help >", content)

    def test_ci_report_summary_explains_safe_gate_artifact(self) -> None:
        content = CI_REPORT.read_text(encoding="utf-8")

        self.assertIn("workflow gate summary", content.lower())
        self.assertIn("required hosted workflow gate map", content.lower())
        self.assertIn("merge-blocker meaning", content.lower())


if __name__ == "__main__":
    unittest.main()
