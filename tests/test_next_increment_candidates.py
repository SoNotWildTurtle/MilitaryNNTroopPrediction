"""Tests for offline next-increment candidate generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.next_increment_candidates import build_candidate_recipes, render_markdown, write_outputs


class NextIncrementCandidateTests(unittest.TestCase):
    """Verify deterministic, non-operational candidate selection behavior."""

    def test_recommends_roadmap_area_with_limited_recent_overlap(self) -> None:
        report = build_candidate_recipes(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            changelog_text=(
                "# Changelog\n\n"
                "## Unreleased\n\n"
                "- Added automation planning docs for next-run decisions.\n"
                "- Added merge evidence template and validation coverage.\n"
            ),
            goals_text=(
                "1. Provide a simple GUI to record whether predictions are correct.\n"
                "2. Offer a user-friendly mobile or PC app delivering early warning alerts.\n"
                "3. Create tools to visualize predictions and track changes over time.\n"
                "4. Provide an interactive setup CLI to write environment variables into a .env file.\n"
            ),
        )

        recommended = report["recommended_candidate"]
        markdown = render_markdown(report)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["schema_version"], "1.0")
        self.assertIsNotNone(recommended)
        self.assertEqual(recommended["status"], "recommended")
        self.assertGreater(recommended["roadmap_matches"], 0)
        self.assertIn("Candidate matrix", markdown)
        self.assertIn("lawful defensive analytical repository maintenance", report["safe_scope"])
        self.assertIn("python -m unittest discover", recommended["validation_commands"])

    def test_recent_overlap_marks_candidate_for_manual_watch(self) -> None:
        report = build_candidate_recipes(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            changelog_text=(
                "# Changelog\n\n"
                "## Unreleased\n\n"
                "- Added setup quickstart guide and environment configure docs.\n"
                "- Added setup doctor recovery hints for install failures.\n"
            ),
            goals_text=(
                "1. Provide an interactive setup CLI to write environment variables into a .env file.\n"
                "2. Provide start scripts to automate MongoDB startup, YOLO training and detection.\n"
            ),
        )

        setup_candidates = [
            candidate for candidate in report["candidate_recipes"] if candidate["focus_area"] == "setup_validation"
        ]

        self.assertEqual(len(setup_candidates), 1)
        self.assertEqual(setup_candidates[0]["status"], "watch")
        self.assertIn("inspect prior PRs", setup_candidates[0]["rationale"])

    def test_missing_inputs_block_candidate_selection(self) -> None:
        report = build_candidate_recipes(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            changelog_text="# Changelog\n\n## Unreleased\n\n",
            goals_text="No numbered roadmap items here.\n",
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(len(report["blockers"]), 2)

    def test_writers_create_markdown_and_json(self) -> None:
        report = build_candidate_recipes(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            changelog_text="# Changelog\n\n## Unreleased\n\n- Added validation evidence.\n",
            goals_text="1. Automate validation evidence capture.\n",
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "candidates.md"
            json_path = Path(temp_dir) / "candidates.json"

            write_outputs(report, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Next Increment Candidates", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")
        self.assertIn("candidate_recipes", parsed)


if __name__ == "__main__":
    unittest.main()
