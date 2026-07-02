"""Static regression coverage for evolving workflow concurrency guidance.

The workflow policy is documentation and CI-configuration oriented. These tests keep
concurrency changes discoverable, reversible, safe-scoped, and tied to required
hosted-check evidence without calling external services, live data sources, model
inference, or deployment workflows.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "evolving_workflow_concurrency.md"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RECEIPT_WORKFLOW = ROOT / ".github" / "workflows" / "handoff-validation-receipt.yml"


class EvolvingWorkflowConcurrencyDocsTests(unittest.TestCase):
    """Ensure the evolving workflow concurrency policy remains low-risk."""

    def test_documents_conservative_pull_request_concurrency_policy(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for phrase in [
            "conservative GitHub Actions concurrency controls",
            "preserving existing workflow names",
            "required checks",
            "branch-protection expectations",
            "cancel-in-progress",
            "pull_request",
            "push runs to `main` are not cancelled",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_workflows_use_same_ref_concurrency_without_renaming_jobs(self) -> None:
        for workflow_path, workflow_name in [
            (CI_WORKFLOW, "name: CI"),
            (RECEIPT_WORKFLOW, "name: Handoff Validation Receipt"),
        ]:
            content = workflow_path.read_text(encoding="utf-8")
            with self.subTest(workflow=workflow_path.name):
                self.assertIn(workflow_name, content)
                self.assertIn("concurrency:", content)
                self.assertIn("group: ${{ github.workflow }}-${{ github.ref }}", content)
                self.assertIn("cancel-in-progress: ${{ github.event_name == 'pull_request' }}", content)

    def test_documents_reviewer_evidence_and_merge_blockers(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        for phrase in [
            "final head SHA",
            "required workflow name and conclusion",
            "same PR branch",
            "final head SHA completed successfully",
            "Missing, skipped, unavailable, wrong-head, or failed required validation remains a merge blocker",
            "artifact names still produced",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, content)

    def test_documents_compatibility_rollback_and_safe_scope(self) -> None:
        content = DOC.read_text(encoding="utf-8")
        lower = content.lower()

        for phrase in [
            "does not change Python runtime behavior",
            "prediction APIs",
            "generated artifact schemas",
            "Rollback by reverting",
            "does not fetch live data",
            "run model inference",
            "perform targeting",
            "not operational tasking",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), lower)


if __name__ == "__main__":
    unittest.main()
