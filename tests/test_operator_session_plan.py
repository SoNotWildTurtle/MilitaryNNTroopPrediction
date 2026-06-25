"""Tests for ranked operator session plan generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.operator_session_plan import build_operator_session_plan, render_markdown, write_outputs


class OperatorSessionPlanTests(unittest.TestCase):
    """Verify operator session plans are deterministic and actionable."""

    def test_blocked_triage_action_becomes_top_task(self) -> None:
        plan = build_operator_session_plan(
            triage_summary={
                "status": "blocked",
                "health_summary": {"ok": 2, "warn": 0, "fail": 1},
                "recommended_actions": [
                    {
                        "reason": "failing health check: core_deps",
                        "target": "make install-core",
                        "detail": "FastAPI is missing",
                        "remediation": "Install core dependencies",
                    }
                ],
            },
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        markdown = render_markdown(plan)

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["next_command"], "make install-core")
        self.assertEqual(plan["tasks"][0]["source"], "triage-summary")
        self.assertIn("failing health check: core_deps", markdown)
        self.assertIn("make install-core", markdown)

    def test_ready_status_falls_back_to_reviewer_bundle_task(self) -> None:
        plan = build_operator_session_plan(
            triage_summary={"status": "ready", "health_summary": {"ok": 8, "warn": 0, "fail": 0}},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["next_command"], "make ci-report")
        self.assertIn("reviewer", plan["objective"].lower())

    def test_release_notes_and_handoff_items_are_deduplicated_and_limited(self) -> None:
        plan = build_operator_session_plan(
            triage_summary={"status": "review", "health_summary": {"ok": 5, "warn": 1, "fail": 0}},
            release_notes={"follow_up_items": [{"title": "Document accepted warning", "detail": "Optional GIS is absent"}]},
            reviewer_handoff={"next_steps": [{"title": "Open bundle index", "command": "make bundle-index", "detail": "Review linked artifacts"}]},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            max_tasks=1,
        )

        self.assertEqual(len(plan["tasks"]), 1)
        self.assertIn(plan["tasks"][0]["source"], {"release-notes:follow_up_items", "reviewer-handoff:next_steps"})

    def test_writers_create_markdown_and_json(self) -> None:
        plan = build_operator_session_plan(
            triage_summary={"status": "unknown"},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "operator-session-plan.md"
            json_path = Path(temp_dir) / "operator-session-plan.json"

            write_outputs(plan, markdown_path, json_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Operator Session Plan", markdown)
        self.assertEqual(parsed["next_command"], "make verify")


if __name__ == "__main__":
    unittest.main()
