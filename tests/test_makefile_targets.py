"""Regression tests for documented Makefile workflow targets.

These tests parse the Makefile as text so they stay lightweight and do not invoke
shell commands, network access, ML dependencies, MongoDB, or live prediction code.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"


def read_makefile() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


class MakefileWorkflowTests(unittest.TestCase):
    """Keep contributor task-runner docs and targets from drifting."""

    def test_verify_target_is_available_in_help_and_phony(self) -> None:
        content = read_makefile()

        self.assertIn("make verify", content)
        self.assertRegex(content, r"(?m)^\.PHONY: .*\bverify\b")
        self.assertRegex(content, r"(?m)^verify: .*\bdoctor\b.*\btest\b.*\bci-report\b")
        self.assertRegex(content, r"(?m)^verify: .*\bvalidate-handoff\b")

    def test_verify_target_points_reviewers_to_release_bundle_index(self) -> None:
        content = read_makefile()

        verify_block = re.search(r"(?ms)^verify:.*?(?=^ci-triage:)", content)
        self.assertIsNotNone(verify_block)
        assert verify_block is not None
        self.assertIn("release-bundle-index.html", verify_block.group(0))

    def test_core_validation_targets_stay_lightweight(self) -> None:
        content = read_makefile()

        self.assertIn("app.cli.doctor --skip-optional --skip-mongo --json", content)
        self.assertIn("bash scripts/test.sh", content)
        self.assertIn("bash scripts/ci_report.sh", content)

    def test_decision_log_target_is_documented_and_exported(self) -> None:
        content = read_makefile()

        self.assertRegex(content, r"(?m)^\.PHONY: .*\bdecision-log\b")
        self.assertIn("make decision-log", content)
        self.assertRegex(content, r"(?m)^decision-log:")
        self.assertIn("app.cli.decision_log", content)
        self.assertIn("$(ARTIFACT_DIR)/decision-log.md", content)
        self.assertIn("$(ARTIFACT_DIR)/decision-log.json", content)

    def test_handoff_validation_receipt_target_is_documented_and_exported(self) -> None:
        content = read_makefile()

        self.assertRegex(content, r"(?m)^\.PHONY: .*\bhandoff-validation-receipt\b")
        self.assertIn("make handoff-validation-receipt", content)
        self.assertRegex(content, r"(?m)^handoff-validation-receipt:")
        self.assertIn("app.cli.handoff_validation_receipt", content)
        self.assertIn("$(ARTIFACT_DIR)/handoff-validation-receipt.md", content)
        self.assertIn("$(ARTIFACT_DIR)/handoff-validation-receipt.json", content)
        self.assertIn("handoff validation receipt", content.lower())

    def test_workflow_gate_summary_target_is_documented_and_exported(self) -> None:
        content = read_makefile()

        self.assertRegex(content, r"(?m)^\.PHONY: .*\bworkflow-gate-summary\b")
        self.assertIn("make workflow-gate-summary", content)
        self.assertRegex(content, r"(?m)^workflow-gate-summary:")
        self.assertIn("app.cli.workflow_gate_summary", content)
        self.assertIn("$(ARTIFACT_DIR)/workflow-gate-summary.md", content)
        self.assertIn("$(ARTIFACT_DIR)/workflow-gate-summary.json", content)
        self.assertIn("workflow gate summary", content.lower())


if __name__ == "__main__":
    unittest.main()
