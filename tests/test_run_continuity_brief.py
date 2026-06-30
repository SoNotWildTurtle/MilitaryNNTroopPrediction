"""Tests for the run continuity brief CLI."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.run_continuity_brief import FOCUS_AREAS, build_run_continuity_brief, render_markdown, write_outputs


class RunContinuityBriefTests(unittest.TestCase):
    """Verify deterministic next-increment planning behavior."""

    def test_ready_brief_recommends_reviewable_focus(self) -> None:
        report = build_run_continuity_brief(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            changelog_text=(
                "# Changelog\n\n"
                "## Unreleased\n\n"
                "- Added automation planning docs for next-run decisions.\n"
                "- Added merge evidence template and validation coverage.\n"
            ),
            goals_text=(
                "1. Provide interactive maps and alerting for real-time troop monitoring.\n"
                "2. Create tools to visualize predictions and track changes over time.\n"
                "3. Provide a simple GUI to record whether predictions are correct.\n"
                "4. Automate periodic model retraining as new data is ingested.\n"
            ),
            decision_register_text="# Next Run Decision Register\n\nRecord blocker-first decisions.\n",
        )

        markdown = render_markdown(report)
        focus_area = report["recommended_next_increment"]["focus_area"]

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["schema_version"], "1.0")
        self.assertIn(focus_area, FOCUS_AREAS)
        self.assertGreaterEqual(report["focus_findings"][0]["score"], report["focus_findings"][-1]["score"])
        self.assertIn("Run Continuity Brief", markdown)
        self.assertIn("lawful defensive analytical repository maintenance", report["safe_scope"])

    def test_missing_inputs_block_new_increment_selection(self) -> None:
        report = build_run_continuity_brief(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            changelog_text="# Changelog\n\n## Unreleased\n\n",
            goals_text="No numbered roadmap here.\n",
            decision_register_text="",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(len(report["blockers"]), 3)
        self.assertIn("Resolve continuity blockers", report["next_action"])

    def test_writers_create_markdown_and_json(self) -> None:
        report = build_run_continuity_brief(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            changelog_text="# Changelog\n\n## Unreleased\n\n- Added validation evidence.\n",
            goals_text="1. Automate validation evidence capture.\n",
            decision_register_text="decision register exists",
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "brief.md"
            json_path = Path(temp_dir) / "brief.json"

            write_outputs(report, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Run Continuity Brief", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")
        self.assertIn("recommended_next_increment", parsed)


if __name__ == "__main__":
    unittest.main()
