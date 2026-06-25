"""Regression tests for the release bundle review guide."""

from __future__ import annotations

from pathlib import Path
import unittest


class ReleaseBundleReviewDocsTests(unittest.TestCase):
    """Keep the reviewer workflow aligned with generated artifacts."""

    def test_review_guide_links_triage_and_landing_page(self) -> None:
        text = Path("docs/release_bundle_review.md").read_text(encoding="utf-8")

        self.assertIn("ci_artifacts/release-bundle-index.html", text)
        self.assertIn("triage-summary.md", text)
        self.assertIn("make ci-triage", text)
        self.assertIn("make verify", text)
        self.assertIn("artifact-manifest.md", text)

    def test_review_guide_preserves_safe_scope(self) -> None:
        text = Path("docs/release_bundle_review.md").read_text(encoding="utf-8")

        self.assertIn("defensive, analytical software validation", text)
        self.assertIn("does not run prediction models", text)
        self.assertIn("synthetic", text)


if __name__ == "__main__":
    unittest.main()
