"""Regression checks for CI troubleshooting documentation.

These tests keep the hosted/local validation path discoverable without invoking
GitHub Actions, shell commands, network access, or heavy optional dependencies.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
COMMON_TASKS = ROOT / "docs" / "common_tasks.md"
CI_TROUBLESHOOTING = ROOT / "docs" / "ci_troubleshooting.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


class CITroubleshootingDocsTests(unittest.TestCase):
    """Keep CI failure recovery guidance aligned with contributor workflows."""

    def test_troubleshooting_guide_covers_reproducible_ci_path(self) -> None:
        content = CI_TROUBLESHOOTING.read_text(encoding="utf-8")

        self.assertIn("make verify ARTIFACT_DIR=ci_artifacts/local-ci", content)
        self.assertIn("ci_artifacts/local-ci/release-bundle-index.html", content)
        self.assertIn(".github/workflows/ci.yml", content)
        self.assertIn("requirements-core.txt", content)
        self.assertIn("scripts/ci_report.sh", content)

    def test_workflow_and_docs_reference_same_validation_entrypoint(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        guide = CI_TROUBLESHOOTING.read_text(encoding="utf-8")

        self.assertIn("make verify ARTIFACT_DIR=ci_artifacts", workflow)
        self.assertIn("make verify", guide)

    def test_primary_contributor_docs_link_to_troubleshooting_guide(self) -> None:
        for path in (README, CONTRIBUTING, COMMON_TASKS):
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertIn("docs/ci_troubleshooting.md", content)


if __name__ == "__main__":
    unittest.main()
