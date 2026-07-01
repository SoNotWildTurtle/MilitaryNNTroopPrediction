"""Static coverage for release bundle target handoff profile guidance."""

from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "release_bundle_target_handoff_profile.md"
CHANGELOG_FRAGMENT_PATH = REPO_ROOT / "changelog.d" / "release_bundle_target_handoff_profile.md"


class ReleaseBundleTargetHandoffProfileDocsTests(unittest.TestCase):
    """Keep release-bundle target handoff guidance discoverable and safety-framed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")
        cls.changelog_text = CHANGELOG_FRAGMENT_PATH.read_text(encoding="utf-8")

    def test_preservation_rules_keep_additive_json_compatible(self) -> None:
        required_phrases = (
            "Preserve every `release_bundle_targets` entry",
            "Preserve the original `path`, `role`, and `review_purpose` values exactly",
            "Preserve unknown future keys as additive metadata",
            "Do not treat the existence of a target as evidence",
        )

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc_text)

    def test_handoff_projection_documents_reviewer_routing_fields(self) -> None:
        required_fields = (
            "`path`",
            "`role`",
            "`review_purpose`",
            "`presence_status`",
            "`integrity_status`",
            "artifact manifest",
        )

        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, self.doc_text)

    def test_validation_checklist_preserves_merge_blockers(self) -> None:
        required_phrases = (
            "final head SHA evidence",
            "hosted required-check conclusions",
            "review-thread status",
            "target-branch correctness",
            "final diff review",
            "stacked dependency order",
            "Required hosted checks remain the source of validation status",
        )

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc_text)

    def test_safe_scope_rejects_operational_or_certainty_claims(self) -> None:
        required_phrases = (
            "navigation metadata only",
            "do not validate model quality",
            "prove predictions",
            "identify real-world troop movement",
            "operational use",
        )

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc_text)

    def test_changelog_fragment_mentions_profile_and_scope(self) -> None:
        self.assertIn("release bundle target handoff profile", self.changelog_text.lower())
        self.assertIn("safe analytical framing", self.changelog_text.lower())
        self.assertIn("does not change prediction", self.changelog_text.lower())


if __name__ == "__main__":
    unittest.main()
