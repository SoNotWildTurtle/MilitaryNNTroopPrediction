"""Static coverage for the reviewer workflow status index.

The status index is documentation-only, so these tests keep the reviewer map
aligned with the hosted workflows and local reproduction commands without
calling external services, live feeds, model inference, or deployment systems.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reviewer_workflow_status_index.md"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"


class ReviewerWorkflowStatusIndexTests(unittest.TestCase):
    """Ensure the reviewer workflow status guide stays useful and safe-scoped."""

    def test_status_matrix_names_hosted_checks_and_local_reproduction(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        self.assertIn("Status matrix", content)
        self.assertIn("`CI`", content)
        self.assertIn("`Analytical Framing Audit`", content)
        self.assertIn("`Handoff Validation Receipt`", content)
        self.assertIn("make verify ARTIFACT_DIR=ci_artifacts/local-review", content)
        self.assertIn("python -m app.cli.analytical_framing_audit", content)
        self.assertIn("make handoff-validation-receipt ARTIFACT_DIR=ci_artifacts", content)

    def test_status_index_preserves_scope_and_merge_blocker_language(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        self.assertIn("does not claim that analytical estimates are true", content)
        self.assertIn("does not validate model quality", content)
        self.assertIn("unavailable artifact", content)
        self.assertIn("unresolved review thread", content)
        self.assertIn("merge blocker", content)

    def test_failure_triage_prefers_narrow_reproduction_without_bypassing_checks(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        self.assertIn("Prefer the narrowest failing check first", content)
        self.assertIn("make ci-triage", content)
        self.assertIn("failing job log", content)
        self.assertIn("Avoid bypassing failures", content)
        self.assertIn("strictly validated", content)

    def test_readme_and_changelog_link_the_status_index(self) -> None:
        readme = README.read_text(encoding="utf-8")
        changelog = CHANGELOG.read_text(encoding="utf-8")

        self.assertIn("docs/reviewer_workflow_status_index.md", readme)
        self.assertIn("reviewer workflow status index", changelog)


if __name__ == "__main__":
    unittest.main()
