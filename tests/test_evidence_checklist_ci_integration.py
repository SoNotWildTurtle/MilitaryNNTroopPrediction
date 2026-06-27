"""Integration contract tests for evidence checklist release-bundle wiring."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class EvidenceChecklistCiIntegrationTests(unittest.TestCase):
    """Keep user-facing task runner and CI bundle wiring aligned."""

    def test_makefile_exposes_evidence_checklist_target(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertIn("evidence-checklist", makefile)
        self.assertIn("python3 -m app.cli.evidence_checklist", makefile.replace("$(PYTHON_BIN)", "python3"))
        self.assertIn("evidence-checklist.md", makefile)
        self.assertIn("evidence-checklist.json", makefile)

    def test_ci_report_generates_evidence_checklist_outputs(self) -> None:
        ci_report = (ROOT / "scripts" / "ci_report.sh").read_text(encoding="utf-8")

        self.assertIn("app.cli.evidence_checklist --help", ci_report)
        self.assertIn("app.cli.evidence_checklist --artifact-dir", ci_report)
        self.assertIn("evidence-checklist.md", ci_report)
        self.assertIn("evidence-checklist.json", ci_report)


if __name__ == "__main__":
    unittest.main()
