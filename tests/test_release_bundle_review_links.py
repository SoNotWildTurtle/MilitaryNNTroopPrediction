"""Regression checks for release bundle review guide discoverability.

These tests keep the reviewer handoff guide linked from the primary onboarding
surfaces without invoking shell commands, network access, or optional runtime
components.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
CONTRIBUTING = ROOT / "CONTRIBUTING.md"
COMMON_TASKS = ROOT / "docs" / "common_tasks.md"
RELEASE_REVIEW = ROOT / "docs" / "release_bundle_review.md"


class ReleaseBundleReviewLinkTests(unittest.TestCase):
    """Keep generated bundle review guidance easy to find."""

    def test_review_guide_documents_primary_bundle_entrypoint(self) -> None:
        content = RELEASE_REVIEW.read_text(encoding="utf-8")

        self.assertIn("ci_artifacts/release-bundle-index.html", content)
        self.assertIn("triage-summary.md", content)
        self.assertIn("artifact-manifest.md", content)
        self.assertIn("make ci-triage", content)
        self.assertIn("make verify", content)

    def test_primary_onboarding_docs_link_to_review_guide(self) -> None:
        for path in (README, CONTRIBUTING, COMMON_TASKS):
            with self.subTest(path=path):
                content = path.read_text(encoding="utf-8")
                self.assertIn("docs/release_bundle_review.md", content)


if __name__ == "__main__":
    unittest.main()
