"""Static checks for the post-merge verification receipt."""

from __future__ import annotations

from pathlib import Path
import unittest


class PostMergeVerificationReceiptDocsTests(unittest.TestCase):
    """Keep post-merge verification guidance discoverable and safe-scoped."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = Path("docs/post_merge_verification_receipt.md").read_text(encoding="utf-8")

    def test_receipt_records_target_branch_and_merge_commit(self) -> None:
        for phrase in (
            "Target branch",
            "Expected PR head SHA before merge",
            "Resulting merge commit SHA",
            "Verified on target branch",
            "Open stacked PRs after merge",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.receipt)

    def test_receipt_preserves_required_hosted_check_names(self) -> None:
        for check_name in ("CI", "Analytical Framing Audit", "Handoff Validation Receipt"):
            with self.subTest(check_name=check_name):
                self.assertIn(check_name, self.receipt)

    def test_receipt_documents_merge_blockers_and_no_bypass_policy(self) -> None:
        for phrase in (
            "Missing required hosted validation",
            "unresolved review threads",
            "branch-protection blockers",
            "stale final head SHA",
            "remain merge blockers",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.receipt)

    def test_receipt_keeps_safe_analytical_framing_and_rollback(self) -> None:
        for phrase in (
            "does not certify predictive accuracy",
            "analytical estimates",
            "synthetic placeholders",
            "narrow revert PR",
            "Avoid history rewrites",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.receipt)


if __name__ == "__main__":
    unittest.main()
