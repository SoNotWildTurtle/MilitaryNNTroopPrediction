"""Static regression coverage for artifact consumer compatibility guidance.

The guide is documentation-only, so these tests keep downstream artifact consumer
expectations aligned with additive schema evolution, safe analytical framing, and
reviewer handoff workflows without calling external services, live data sources,
model inference, or deployment workflows.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "artifact_consumer_compatibility.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def normalized_text(value: str) -> str:
    """Return text normalized for prose checks while preserving behavior checks.

    These documentation tests should fail when required guidance disappears, but they
    should not fail because a human-facing guide changes harmless capitalization,
    wraps a line differently, or uses punctuation such as a hyphen or underscore in a
    heading, filename-adjacent phrase, or PR-head-SHA phrase.
    """

    normalized = value.lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def assert_normalized_contains(
    test_case: unittest.TestCase,
    needle: str,
    haystack: str,
) -> None:
    """Assert that prose contains a phrase without brittle formatting coupling."""

    test_case.assertIn(normalized_text(needle), normalized_text(haystack))


class ArtifactConsumerCompatibilityDocsTests(unittest.TestCase):
    """Ensure downstream artifact consumer guidance stays complete and safe-scoped."""

    def test_safe_scope_and_analytical_limits_are_explicit(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for phrase in [
            "deterministic local/ci evidence",
            "not live collection",
            "model inference",
            "operational targeting",
            "analytical estimates",
            "does not prove real-world conditions",
            "model quality",
            "tactical certainty",
            "operational truth",
            "synthetic fixtures",
            "static previews",
            "reviewer handoff material",
        ]:
            with self.subTest(phrase=phrase):
                assert_normalized_contains(self, phrase, content)

    def test_consumer_rules_preserve_additive_schema_compatibility(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for term in [
            "`schema_version`",
            "Preserve unknown fields",
            "Do not fail merely because a JSON object contains a new additive key",
            "Validate required fields by meaning",
            "Prefer JSON for automation and Markdown for human review",
            "Keep generated artifact paths configurable",
            "Surface uncertainty and validation limits",
            "null",
            "missing optional fields",
            "empty optional lists",
        ]:
            with self.subTest(term=term):
                assert_normalized_contains(self, term, content)

    def test_recommended_parsing_order_mentions_core_handoff_artifacts(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for artifact in [
            "release-bundle-index.html",
            "artifact-manifest.json",
            "artifact-gap-report.json",
            "artifact-provenance-ledger.json",
            "provenance-validation-matrix.json",
            "workflow-gate-summary.json",
            "triage-summary.json",
            "reviewer-handoff.json",
            "reviewer-handoff-validation.json",
            "operator-readiness.json",
            "operator-status-board.json",
            "operator-next-steps.json",
            "operator-exception-register.json",
            "handoff-validation-receipt.json",
            "post_merge_verification_receipt.md",
        ]:
            with self.subTest(artifact=artifact):
                self.assertIn(artifact, content)

    def test_merge_blockers_and_wrong_head_checks_are_documented(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for blocker in [
            "missing",
            "empty",
            "stale",
            "queued",
            "skipped",
            "cancelled",
            "unavailable",
            "failed",
            "wrong-head",
            "merge blockers",
            "final pr head sha",
            "required hosted gate",
        ]:
            with self.subTest(blocker=blocker):
                assert_normalized_contains(self, blocker, content)

    def test_related_docs_and_narrow_commands_remain_discoverable(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for term in [
            "docs/reviewer_handoff_navigation.md",
            "docs/workflow_gate_summary_schema.md",
            "docs/triage_summary_schema.md",
            "docs/provenance_validation_matrix_schema.md",
            "docs/artifact_provenance_ledger.md",
            "docs/artifact_gap_report.md",
            "docs/review_blocker_decision_tree.md",
            "docs/final_merge_evidence_packet.md",
            "make ci-report",
            "make manifest",
            "make artifact-gap-report",
            "make provenance-ledger",
            "make provenance-validation-matrix",
            "make workflow-gate-summary",
            "make triage-summary",
        ]:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_documents_compatibility_rollback_migration_and_changelog(self) -> None:
        doc = DOC.read_text(encoding="utf-8")
        changelog = CHANGELOG.read_text(encoding="utf-8")

        self.assertIn("changes no runtime behavior", doc)
        self.assertIn("public API", doc)
        self.assertIn("generated schema", doc)
        self.assertIn("artifact filename", doc)
        self.assertIn("hosted workflow", doc)
        self.assertIn("Rollback is a normal", doc)
        self.assertIn("migration note", doc)
        self.assertIn("old and new field names", doc)
        self.assertIn("additive, deprecated, or breaking", doc)
        assert_normalized_contains(self, "artifact consumer compatibility", changelog)


if __name__ == "__main__":
    unittest.main()
