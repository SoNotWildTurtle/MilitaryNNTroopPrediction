"""Static regression coverage for README preflight navigation.

The automation preflight handbook is documentation-only, so these tests keep the
primary repository entry points aligned with failure-first hosted validation,
review handoff, and safe analytical framing guidance without calling external
services, live data sources, model inference, or deployment workflows.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"


class ReadmePreflightNavigationTests(unittest.TestCase):
    """Ensure README keeps the automation preflight handbook discoverable."""

    def test_structure_lists_preflight_handbook_near_reviewer_guidance(self) -> None:
        content = README.read_text(encoding="utf-8")

        self.assertIn("docs/automation_run_preflight.md", content)
        self.assertIn("docs/reviewer_handoff_navigation.md", content)
        self.assertLess(
            content.index("docs/automation_run_preflight.md"),
            content.index("docs/reviewer_handoff_navigation.md"),
        )

        for phrase in [
            "start-of-run checklist",
            "default branch",
            "open PRs",
            "hosted checks",
            "narrow reruns",
            "additive scope",
            "merge readiness",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_fast_first_run_points_to_preflight_before_ci_troubleshooting(self) -> None:
        content = README.read_text(encoding="utf-8")

        self.assertIn("before opening or merging recurring maintenance work", content)
        self.assertLess(
            content.index("docs/automation_run_preflight.md"),
            content.index("docs/ci_troubleshooting.md"),
        )

    def test_changelog_records_readme_navigation_update(self) -> None:
        changelog = CHANGELOG.read_text(encoding="utf-8").lower()

        for phrase in [
            "readme navigation",
            "docs/automation_run_preflight.md",
            "primary setup and structure surfaces",
            "static regression coverage",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, changelog)


if __name__ == "__main__":
    unittest.main()
