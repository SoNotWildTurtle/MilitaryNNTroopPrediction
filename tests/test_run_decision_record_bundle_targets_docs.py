"""Static coverage for run decision record bundle target guidance."""

from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = REPO_ROOT / "docs" / "run_decision_record_bundle_targets.md"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"


class RunDecisionRecordBundleTargetsDocsTests(unittest.TestCase):
    """Keep decision-record bundle handoff docs discoverable and safety-framed."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8")
        cls.changelog_text = CHANGELOG_PATH.read_text(encoding="utf-8")

    def test_primary_artifact_targets_are_documented(self) -> None:
        required_targets = (
            "next-increment-candidates.md",
            "next-increment-candidates.json",
            "run-decision-record.json",
            "implementation-acceptance-checklist.json",
            "implementation-acceptance-handoff.json",
            "release-bundle-index.html",
            "artifact-manifest.json",
            "artifact-provenance-ledger.json",
        )

        for target in required_targets:
            with self.subTest(target=target):
                self.assertIn(target, self.doc_text)

    def test_review_order_preserves_merge_blockers_and_safe_scope(self) -> None:
        required_phrases = (
            "final head SHA",
            "hosted required-check conclusions",
            "unresolved review-thread status",
            "branch-stack/base correctness",
            "final diff safety review",
            "not live intelligence or operational truth",
            "Do not merge a PR solely because these artifacts exist",
        )

        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc_text)

    def test_local_reproduction_commands_are_narrow_and_offline(self) -> None:
        self.assertIn("python -m app.cli.next_increment_candidates", self.doc_text)
        self.assertIn("--decision-record-path", self.doc_text)
        self.assertIn("python -m app.cli.implementation_acceptance_checklist", self.doc_text)
        self.assertIn("python -m app.cli.implementation_acceptance_handoff", self.doc_text)
        self.assertIn("bash scripts/ci_report.sh", self.doc_text)

    def test_changelog_mentions_bundle_target_guidance(self) -> None:
        self.assertIn("run decision record bundle target", self.changelog_text.lower())
        self.assertIn("safe analytical framing", self.changelog_text.lower())


if __name__ == "__main__":
    unittest.main()
