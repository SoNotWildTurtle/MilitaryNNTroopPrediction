"""Static regression coverage for automation run preflight guidance.

The handbook is documentation-only, so these tests keep recurring maintenance
runs aligned with hosted validation, safe analytical framing, and additive change
expectations without calling external services, live data sources, model
inference, or deployment workflows.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "automation_run_preflight.md"
CHANGELOG = ROOT / "CHANGELOG.md"


class AutomationRunPreflightDocsTests(unittest.TestCase):
    """Ensure the automation preflight handbook stays complete and safe-scoped."""

    def test_preflight_covers_required_repo_inspection_order(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for term in [
            "default branch",
            "latest default-branch commit SHA",
            "open pull requests",
            "stacked",
            "recent merged pull requests",
            "changelog entries",
            "open issues",
            "review comments",
            "final diff",
        ]:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_required_hosted_checks_and_blockers_are_documented(self) -> None:
        content = DOC.read_text(encoding="utf-8")
        content_lower = content.lower()

        for check in [
            "`CI`",
            "`Analytical Framing Audit`",
            "`Handoff Validation Receipt`",
        ]:
            with self.subTest(check=check):
                self.assertIn(check, content)

        for blocker in [
            "missing",
            "queued",
            "stale",
            "unavailable",
            "skipped",
            "cancelled",
            "failed",
            "wrong-head",
            "merge blocker",
        ]:
            with self.subTest(blocker=blocker):
                self.assertIn(blocker, content_lower)

    def test_routes_to_existing_runbooks_and_narrow_targets(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for term in [
            "docs/reviewer_workflow_status_index.md",
            "docs/workflow_gate_review_runbook.md",
            "docs/reviewer_handoff_navigation.md",
            "docs/final_merge_evidence_packet.md",
            "docs/merge_readiness_record_template.md",
            "docs/review_blocker_decision_tree.md",
            "docs/artifact_gap_report.md",
            "docs/artifact_provenance_ledger.md",
            "docs/operator_status_board.md",
            "docs/analytical_framing_audit_workflow.md",
            "make workflow-gate-summary",
            "make ci-triage",
            "make validate-handoff",
            "make ci-report",
            "make triage-summary",
        ]:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_preserves_additive_scope_and_safe_analytical_framing(self) -> None:
        content = DOC.read_text(encoding="utf-8").lower()

        for phrase in [
            "does not fetch live data",
            "run model inference",
            "perform targeting",
            "analytical estimates",
            "synthetic fixtures",
            "static previews",
            "uncertainty",
            "validation limits",
            "not a bypass",
            "operational targeting advice",
            "proof of real-world conditions",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_documents_compatibility_rollback_and_changelog(self) -> None:
        doc = DOC.read_text(encoding="utf-8")
        changelog = CHANGELOG.read_text(encoding="utf-8").lower()

        self.assertIn("changes no runtime behavior", doc)
        self.assertIn("APIs", doc)
        self.assertIn("schemas", doc)
        self.assertIn("generated artifact names", doc)
        self.assertIn("Rollback is a normal documentation/test/changelog revert", doc)
        self.assertIn("automation run preflight", changelog)


if __name__ == "__main__":
    unittest.main()
