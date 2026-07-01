"""Static coverage for handoff manifest status review guidance."""

from __future__ import annotations

from pathlib import Path
import unittest


DOC_PATH = Path("docs/handoff_manifest_status_review.md")
README_PATH = Path("README.md")
CHANGELOG_PATH = Path("CHANGELOG.md")


class HandoffManifestStatusReviewDocTests(unittest.TestCase):
    """Keep manifest-backed handoff status guidance discoverable and safe."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc = DOC_PATH.read_text(encoding="utf-8")
        cls.readme = README_PATH.read_text(encoding="utf-8")
        cls.changelog = CHANGELOG_PATH.read_text(encoding="utf-8")

    def test_document_defines_safe_default_statuses_and_inputs(self) -> None:
        required_tokens = [
            "presence_status: not_checked",
            "integrity_status: not_checked",
            "implementation-acceptance-handoff.json",
            "artifact-manifest.json",
            "artifact-gap-report.json",
            "python -m app.cli.implementation_acceptance_handoff",
            "python -m app.cli.artifact_manifest",
            "python -m app.cli.artifact_gap_report",
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, self.doc)

    def test_document_preserves_strict_reviewer_status_vocabulary(self) -> None:
        required_statuses = [
            "`presence_status` | `not_checked`",
            "`presence_status` | `present`",
            "`presence_status` | `missing`",
            "`integrity_status` | `not_checked`",
            "`integrity_status` | `hash_recorded`",
            "`integrity_status` | `needs_review`",
        ]
        for status in required_statuses:
            with self.subTest(status=status):
                self.assertIn(status, self.doc)

    def test_document_keeps_blockers_rollback_and_safe_scope_visible(self) -> None:
        required_tokens = [
            "Block merge when",
            "required hosted checks for the final head SHA",
            "does not change generated predictions",
            "model training",
            "live data ingestion",
            "prediction validation",
            "operational certainty",
            "Rollback by reverting this documentation and its static coverage",
        ]
        for token in required_tokens:
            with self.subTest(token=token):
                self.assertIn(token, self.doc)

    def test_primary_navigation_surfaces_link_the_guide(self) -> None:
        self.assertIn("docs/handoff_manifest_status_review.md", self.readme)
        self.assertIn("docs/handoff_manifest_status_review.md", self.changelog)
        self.assertIn("manifest-backed presence/integrity review", self.changelog)


if __name__ == "__main__":
    unittest.main()
