"""Static regression coverage for reviewer handoff navigation.

The navigation map is documentation-only, so these tests keep the reviewer
routing layer aligned with existing hosted checks, diagnostic artifacts, and safe
analytical framing without calling external services, live data sources, model
inference, or deployment workflows.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reviewer_handoff_navigation.md"
CHANGELOG = ROOT / "CHANGELOG.md"
README = ROOT / "README.md"


class ReviewerHandoffNavigationDocsTests(unittest.TestCase):
    """Ensure the reviewer navigation guide remains complete and safe-scoped."""

    def test_routes_core_hosted_checks_and_review_guides(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for term in [
            "`CI`",
            "`Analytical Framing Audit`",
            "`Handoff Validation Receipt`",
            "docs/reviewer_workflow_status_index.md",
            "docs/workflow_gate_review_runbook.md",
            "docs/review_blocker_decision_tree.md",
            "docs/merge_readiness_record_template.md",
            "docs/final_merge_evidence_packet.md",
        ]:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_routes_artifact_contract_and_bundle_guidance(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for term in [
            "docs/workflow_gate_summary_schema.md",
            "docs/triage_summary_schema.md",
            "docs/artifact_provenance_ledger.md",
            "docs/artifact_gap_report.md",
            "docs/operator_status_board.md",
            "diagnostic bundle landing page",
            "evidence checklist",
            "release notes",
        ]:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_prefers_narrow_local_reruns_before_broad_validation(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for command in [
            "make workflow-gate-summary",
            "make triage-summary",
            "make validate-handoff",
            "make ci-report",
            "make ci-triage",
            "make handoff-validation-receipt",
            "python -m app.cli.analytical_framing_audit --artifact-dir ci_artifacts",
            "make provenance-ledger",
            "make artifact-gap-report",
            "make operator-status-board",
        ]:
            with self.subTest(command=command):
                self.assertIn(command, content)

    def test_preserves_merge_blocker_and_safe_framing_language(self) -> None:
        content = DOC.read_text(encoding="utf-8").lower()

        for phrase in [
            "does not fetch live data",
            "perform targeting",
            "analytical estimates",
            "uncertainty",
            "validation limits",
            "merge blocker",
            "operational targeting advice",
            "proof of real-world conditions",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_documents_compatibility_and_links_from_handoff_surfaces(self) -> None:
        doc = DOC.read_text(encoding="utf-8")
        changelog = CHANGELOG.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        self.assertIn("changes no runtime behavior", doc)
        self.assertIn("APIs", doc)
        self.assertIn("schemas", doc)
        self.assertIn("generated artifact names", doc)
        self.assertIn("Rollback is a normal documentation/test/README/changelog revert", doc)
        self.assertIn("reviewer handoff navigation", changelog.lower())
        self.assertIn("docs/reviewer_handoff_navigation.md", readme)


if __name__ == "__main__":
    unittest.main()
