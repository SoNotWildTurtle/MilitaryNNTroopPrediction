"""Static coverage for CI handoff gap-report review artifact wiring."""

from __future__ import annotations

from pathlib import Path
import unittest


class CiReportHandoffGapStaticTests(unittest.TestCase):
    """Ensure ci_report publishes reviewer evidence for handoff gap status."""

    def test_ci_report_generates_handoff_gap_review_after_required_inputs(self) -> None:
        script = Path("scripts/ci_report.sh").read_text(encoding="utf-8")

        handoff_help = "handoff-gap-report-review-help.txt"
        manifest = "artifact-manifest.json"
        gap_report = "artifact-gap-report.json"
        enriched_handoff = "--artifact-manifest-json \"${ARTIFACT_DIR}/artifact-manifest.json\""
        review_command = "-m app.cli.handoff_gap_report_review"
        review_json = "handoff-gap-report-review.json"
        summary_token = "handoff-gap-report-review.md/json"

        self.assertIn(handoff_help, script)
        self.assertIn(enriched_handoff, script)
        self.assertIn(review_command, script)
        self.assertIn(review_json, script)
        self.assertIn(summary_token, script)
        self.assertLess(script.rfind(manifest), script.rfind(review_command))
        self.assertLess(script.rfind(gap_report), script.rfind(review_command))
        self.assertLess(script.rfind(enriched_handoff), script.rfind(review_command))


if __name__ == "__main__":
    unittest.main()
