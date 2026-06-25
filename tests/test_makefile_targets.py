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
        self.assertRegex(content, r"(?m)^verify: doctor test ci-report$")

    def test_verify_target_points_reviewers_to_release_bundle_index(self) -> None:
        content = read_makefile()

        verify_block = re.search(r"(?ms)^verify:.*?(?=^ci-report:)", content)
        self.assertIsNotNone(verify_block)
        assert verify_block is not None
        self.assertIn("release-bundle-index.html", verify_block.group(0))

    def test_core_validation_targets_stay_lightweight(self) -> None:
        content = read_makefile()

        self.assertIn("app.cli.doctor --skip-optional --skip-mongo --json", content)
        self.assertIn("bash scripts/test.sh", content)
        self.assertIn("bash scripts/ci_report.sh", content)


if __name__ == "__main__":
    unittest.main()
