"""Static coverage for CI handoff gap-review artifact wiring."""

from __future__ import annotations

from pathlib import Path
import unittest


class CiReportHandoffGapStaticTests(unittest.TestCase):
    """Ensure ci_report publishes reviewer evidence after its inputs exist."""

    def test_ci_report_generates_review_after_required_inputs(self) -> None:
        script = Path("scripts/ci_report.sh").read_text(encoding="utf-8")

        help_file = "handoff-gap-report-review-help.txt"
        gap_command = (
            "-m app.cli.artifact_gap_report --artifact-dir \"${ARTIFACT_DIR}\" "
            "--json-path \"${ARTIFACT_DIR}/artifact-gap-report.json\""
        )
        enriched_handoff = "--artifact-manifest-json \"${ARTIFACT_DIR}/artifact-manifest.json\""
        review_command = (
            "-m app.cli.handoff_gap_report_review "
            "--handoff-json \"${ARTIFACT_DIR}/implementation-acceptance-handoff.json\""
        )
        review_json = "handoff-gap-report-review.json"
        summary_token = "handoff-gap-report-review.md/json"

        self.assertIn(help_file, script)
        self.assertIn(enriched_handoff, script)
        self.assertIn(review_command, script)
        self.assertIn(review_json, script)
        self.assertIn(summary_token, script)
        self.assertLess(script.index(gap_command), script.index(review_command))
        self.assertLess(script.index(enriched_handoff), script.index(review_command))
        self.assertLess(script.index(review_command), script.rfind("artifact_manifest --artifact-dir"))


if __name__ == "__main__":
    unittest.main()
