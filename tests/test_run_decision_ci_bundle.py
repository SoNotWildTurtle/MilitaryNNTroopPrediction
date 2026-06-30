"""Static tests for run-decision artifact bundle wiring."""

from __future__ import annotations

from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CI_REPORT = REPOSITORY_ROOT / "scripts" / "ci_report.sh"
RUN_DECISION_DOC = REPOSITORY_ROOT / "docs" / "run_decision_ci_bundle.md"


class RunDecisionCiBundleTests(unittest.TestCase):
    """Ensure run-decision handoff artifacts stay in the diagnostics bundle."""

    def test_ci_report_exports_next_increment_and_decision_record_artifacts(self) -> None:
        script = CI_REPORT.read_text(encoding="utf-8")

        self.assertIn("-m app.cli.next_increment_candidates", script)
        self.assertIn("next-increment-candidates.md", script)
        self.assertIn("next-increment-candidates.json", script)
        self.assertIn("run-decision-record.json", script)
        self.assertIn("next-increment-candidates-help.txt", script)
        self.assertLess(
            script.index("run-decision-record.json"),
            script.index("release-bundle-index.html"),
            "run-decision evidence should be generated before bundle indexing and manifest capture",
        )

    def test_summary_names_run_decision_artifacts_and_safe_scope(self) -> None:
        script = CI_REPORT.read_text(encoding="utf-8")

        self.assertIn("offline roadmap/changelog candidate recipes", script)
        self.assertIn("merge evidence, validation, blocker, rollback, and follow-up fields", script)
        self.assertIn("diagnostic artifact bundle", script)

    def test_documentation_captures_reproduction_review_and_rollback(self) -> None:
        document = RUN_DECISION_DOC.read_text(encoding="utf-8")

        self.assertIn("make ci-report", document)
        self.assertIn("--decision-record-path", document)
        self.assertIn("release-bundle-index.html", document)
        self.assertIn("artifact-manifest.json", document)
        self.assertIn("not operational tasking", document.lower())
        self.assertIn("Roll back", document)
        self.assertIn("additive", document)


if __name__ == "__main__":
    unittest.main()
