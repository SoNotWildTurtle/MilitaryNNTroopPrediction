"""Static coverage for implementation acceptance handoff CI bundle wiring."""

from __future__ import annotations

from pathlib import Path
import unittest


class AcceptanceHandoffCiBundleTests(unittest.TestCase):
    """Keep acceptance handoff artifacts discoverable in CI diagnostics."""

    def setUp(self) -> None:
        self.script = Path("scripts/ci_report.sh").read_text(encoding="utf-8")

    def test_ci_report_builds_checklist_before_handoff(self) -> None:
        checklist_command = "app.cli.implementation_acceptance_checklist"
        handoff_command = "app.cli.implementation_acceptance_handoff"

        self.assertIn(checklist_command, self.script)
        self.assertIn(handoff_command, self.script)
        self.assertLess(self.script.index(checklist_command), self.script.index(handoff_command))
        self.assertIn('--decision-record-path "${ARTIFACT_DIR}/run-decision-record.json"', self.script)
        self.assertIn('--checklist-json "${ARTIFACT_DIR}/implementation-acceptance-checklist.json"', self.script)

    def test_ci_report_publishes_handoff_outputs_and_help(self) -> None:
        expected_paths = [
            "implementation-acceptance-checklist.md",
            "implementation-acceptance-checklist.json",
            "implementation-acceptance-handoff.md",
            "implementation-acceptance-handoff.json",
            "implementation-acceptance-checklist-help.txt",
            "implementation-acceptance-handoff-help.txt",
        ]

        for path in expected_paths:
            with self.subTest(path=path):
                self.assertIn(path, self.script)

    def test_summary_explains_safe_reviewer_scope(self) -> None:
        self.assertIn("completed-evidence handoff readiness summary", self.script)
        self.assertIn("reviewer merge evidence", self.script)
        self.assertIn("safe JSONL/CSV fixture records", self.script)


if __name__ == "__main__":
    unittest.main()
