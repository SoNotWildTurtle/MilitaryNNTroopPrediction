"""Static coverage for the hosted check evidence log runbook."""

from __future__ import annotations

from pathlib import Path
import unittest


class HostedCheckEvidenceLogDocsTests(unittest.TestCase):
    """Keep hosted validation evidence capture discoverable and merge-safe."""

    def setUp(self) -> None:
        self.doc = Path("docs/hosted_check_evidence_log.md").read_text(encoding="utf-8")

    def test_log_template_covers_required_hosted_checks(self) -> None:
        for check_name in (
            "CI",
            "Analytical Framing Audit",
            "Handoff Validation Receipt",
        ):
            with self.subTest(check=check_name):
                self.assertIn(check_name, self.doc)

        for workflow_path in (
            ".github/workflows/ci.yml",
            ".github/workflows/analytical-framing-audit.yml",
            ".github/workflows/handoff-validation-receipt.yml",
        ):
            with self.subTest(workflow=workflow_path):
                self.assertIn(workflow_path, self.doc)

    def test_template_requires_final_head_sha_and_explicit_conclusions(self) -> None:
        required_phrases = (
            "Final PR head SHA",
            "Run URL",
            "Run conclusion",
            "Job conclusion",
            "same final PR head SHA",
            "outdated SHA",
        )
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_runbook_preserves_safe_analytical_framing(self) -> None:
        for phrase in (
            "analytical estimates",
            "does not prove operational accuracy",
            "targeting certainty",
            "operational truth",
            "local tests",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.doc)

    def test_changelog_records_the_template(self) -> None:
        changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")

        self.assertIn("docs/hosted_check_evidence_log.md", changelog)
        self.assertIn("hosted check evidence", changelog.lower())
        self.assertIn("final head SHA", changelog)


if __name__ == "__main__":
    unittest.main()
