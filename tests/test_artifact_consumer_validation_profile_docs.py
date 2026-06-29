"""Static regression coverage for artifact consumer validation profile guidance.

The validation profile is documentation-only, so these tests keep downstream consumer
expectations aligned with safe handoff promotion, additive schema handling, and
reviewer-visible blocker reporting without calling external services.
"""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "artifact_consumer_validation_profile.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def normalized_text(value: str) -> str:
    """Normalize prose while preserving required behavioral phrase checks."""

    normalized = value.lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", normalized).strip()


def assert_normalized_contains(
    test_case: unittest.TestCase,
    needle: str,
    haystack: str,
) -> None:
    """Assert prose contains a phrase without coupling to line wrapping."""

    test_case.assertIn(normalized_text(needle), normalized_text(haystack))


class ArtifactConsumerValidationProfileDocsTests(unittest.TestCase):
    """Ensure the consumer validation profile stays complete and safe-scoped."""

    def test_validation_levels_are_documented(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for term in [
            "`fail`",
            "`warn`",
            "`info`",
            "Stop merge/readiness promotion",
            "display the limitation before summaries",
            "advisory metadata",
            "not the certainty of any estimate",
            "human analytical review",
        ]:
            with self.subTest(term=term):
                assert_normalized_contains(self, term, content)

    def test_hard_fail_conditions_prioritize_required_evidence(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for term in [
            "required hosted check",
            "final PR head SHA",
            "workflow-gate-summary.json",
            "triage-summary.json",
            "artifact-manifest.json",
            "SHA-256 evidence",
            "artifact-gap-report.json",
            "artifact-provenance-ledger.json",
            "provenance-validation-matrix.json",
            "merge_blockers",
            "required_actions",
            "target-branch mismatch",
        ]:
            with self.subTest(term=term):
                assert_normalized_contains(self, term, content)

    def test_warning_conditions_allow_additive_schema_evolution(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for term in [
            "optional artifacts",
            "optional fields",
            "null",
            "missing",
            "empty",
            "timestamps",
            "hosted check freshness",
            "JSON contract behavior remains intact",
            "isolated output directory",
            "new additive JSON key",
            "preserved or ignored safely",
        ]:
            with self.subTest(term=term):
                assert_normalized_contains(self, term, content)

    def test_consumer_output_contract_keeps_blockers_visible(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for field in [
            "profile_name",
            "profile_version",
            "artifact_dir",
            "source_artifacts",
            "failures",
            "warnings",
            "info",
            "safe_scope",
            "unknown_fields_preserved",
            "final_head_sha_reviewed",
        ]:
            with self.subTest(field=field):
                self.assertIn(field, content)

        for phrase in [
            "shown before summaries",
            "source artifact names",
            "provenance labels",
            "safe-scope text",
        ]:
            with self.subTest(phrase=phrase):
                assert_normalized_contains(self, phrase, content)

    def test_safe_scope_and_related_docs_remain_discoverable(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for term in [
            "analytical estimates",
            "not proof that external conditions are known",
            "Synthetic fixtures",
            "static previews",
            "API examples",
            "docs/artifact_consumer_compatibility.md",
            "docs/workflow_gate_summary_schema.md",
            "docs/triage_summary_schema.md",
            "docs/provenance_validation_matrix_schema.md",
            "docs/review_blocker_decision_tree.md",
            "docs/final_merge_evidence_packet.md",
            "make ci-report",
            "make workflow-gate-summary",
            "make triage-summary",
            "make artifact-gap-report",
            "make provenance-ledger",
            "make provenance-validation-matrix",
        ]:
            with self.subTest(term=term):
                assert_normalized_contains(self, term, content)

    def test_changelog_references_profile(self) -> None:
        changelog = CHANGELOG.read_text(encoding="utf-8")

        assert_normalized_contains(self, "artifact consumer validation profile", changelog)

    def test_rollback_and_compatibility_are_narrow(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for phrase in [
            "documentation-only",
            "changes no runtime behavior",
            "public API",
            "generated schema",
            "artifact filename",
            "hosted workflow",
            "required check",
            "Rollback is a normal",
            "migration note",
            "additive or breaking",
            "rollback path",
        ]:
            with self.subTest(phrase=phrase):
                assert_normalized_contains(self, phrase, content)


if __name__ == "__main__":
    unittest.main()
