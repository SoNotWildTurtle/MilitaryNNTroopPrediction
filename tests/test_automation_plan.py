"""Tests for additive automation plan generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.automation_plan import Goal, build_automation_plan, load_goals, render_markdown, write_outputs


class AutomationPlanTests(unittest.TestCase):
    """Verify automation planning is deterministic, safe-scoped, and actionable."""

    def test_blocked_triage_prioritizes_validation_before_feature_work(self) -> None:
        plan = build_automation_plan(
            goals=[Goal(1, "Automate the full data ingestion and prediction cycle with a pipeline script.")],
            triage={
                "status": "blocked",
                "next_step": "make install-core",
                "health_summary": {"ok": 1, "warn": 0, "fail": 1},
                "recommended_actions": [{"reason": "failing health check: core_deps", "target": "make install-core"}],
            },
            manifest={"file_count": 3, "missing_expected": []},
            handoff={"review_status": "needs_attention", "recommended_rerun": "make verify"},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        markdown = render_markdown(plan)

        self.assertEqual(plan["status"], "needs_validation")
        self.assertEqual(plan["priority"], "stabilize diagnostics before feature work")
        self.assertEqual(plan["next_action"], "make install-core")
        self.assertIn("make install-core", plan["validation_commands"])
        self.assertIn("failing health check: core_deps", markdown)

    def test_ready_plan_selects_highest_scoring_additive_goal(self) -> None:
        plan = build_automation_plan(
            goals=[
                Goal(1, "Compile historical and recent troop movement data."),
                Goal(2, "Provide an interactive CLI dashboard using Rich for common tasks."),
                Goal(3, "Track unit identities over time for per-unit trajectory prediction."),
            ],
            triage={"status": "ready", "health_summary": {"ok": 4, "warn": 0, "fail": 0}},
            manifest={"file_count": 10, "missing_expected": []},
            handoff={"review_status": "ready", "recommended_rerun": "make verify"},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(plan["status"], "ready_for_additive_iteration")
        self.assertEqual(plan["top_goals"][0]["number"], 2)
        self.assertIn("goal 2", plan["next_action"])
        self.assertIn("Additive guardrails", render_markdown(plan))

    def test_missing_artifacts_boost_automation_and_dashboard_goals(self) -> None:
        plan = build_automation_plan(
            goals=[
                Goal(4, "Highlight differences between modern and Soviet-era tactics."),
                Goal(5, "Create tools to visualize predictions and track changes over time."),
                Goal(6, "Automate periodic model retraining as new data is ingested."),
            ],
            triage={"status": "incomplete", "next_step": "make dashboard", "health_summary": {"ok": 3, "warn": 0, "fail": 0}},
            manifest={"file_count": 4, "missing_expected": ["dashboard-mockup.html"]},
            handoff={"review_status": "needs_attention", "recommended_rerun": "make verify"},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        goal_numbers = [goal["number"] for goal in plan["top_goals"]]

        self.assertIn(5, goal_numbers)
        self.assertIn(6, goal_numbers)
        self.assertEqual(plan["missing_artifacts"], ["dashboard-mockup.html"])
        self.assertEqual(plan["next_action"], "make dashboard")

    def test_load_goals_parses_numbered_markdown(self) -> None:
        with TemporaryDirectory() as temp_dir:
            goals_path = Path(temp_dir) / "goals.md"
            goals_path.write_text("1. First goal\nnot a goal\n23. Later goal\n", encoding="utf-8")

            goals = load_goals(goals_path)

        self.assertEqual([goal.number for goal in goals], [1, 23])
        self.assertEqual(goals[1].text, "Later goal")

    def test_writers_create_markdown_and_json(self) -> None:
        plan = build_automation_plan(
            goals=[],
            triage={"status": "ready", "health_summary": {"ok": 0, "warn": 0, "fail": 0}},
            manifest={"file_count": 0, "missing_expected": []},
            handoff={"review_status": "ready"},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "automation-plan.md"
            json_path = Path(temp_dir) / "automation-plan.json"

            write_outputs(plan, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Automation Plan", markdown)
        self.assertEqual(parsed["status"], "ready_for_additive_iteration")


if __name__ == "__main__":
    unittest.main()
