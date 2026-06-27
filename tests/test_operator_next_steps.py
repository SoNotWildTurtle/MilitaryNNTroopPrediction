"""Tests for operator next steps generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.operator_next_steps import build_operator_next_steps, render_markdown, write_outputs


class OperatorNextStepsTests(unittest.TestCase):
    """Verify ranked maintainer actions stay deterministic and safe."""

    def test_failures_rank_before_missing_artifacts_and_warnings(self) -> None:
        plan = build_operator_next_steps(
            health_results=[
                {"name": "optional_deps", "status": "warn", "detail": "Optional GIS missing", "remediation": ""},
                {"name": "core_deps", "status": "fail", "detail": "FastAPI missing", "remediation": "Install core deps"},
            ],
            manifest={"file_count": 4, "missing_expected": ["openapi.json"]},
            triage_summary={"status": "blocked", "recommended_actions": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        markdown = render_markdown(plan)
        reasons = [action["reason"] for action in plan["actions"]]

        self.assertEqual(plan["status"], "action_needed")
        self.assertEqual(plan["next_step"], "make install-core")
        self.assertEqual(reasons[0], "fail health check: core_deps")
        self.assertIn("missing artifact: openapi.json", reasons)
        self.assertIn("make openapi", markdown)

    def test_ready_triage_without_actions_returns_handoff_step(self) -> None:
        plan = build_operator_next_steps(
            health_results=[{"name": "python", "status": "ok", "detail": "Python works", "remediation": ""}],
            manifest={"file_count": 12, "missing_expected": []},
            triage_summary={"status": "ready", "recommended_actions": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["actions"], [])
        self.assertIn("release-bundle-index.html", plan["next_step"])
        self.assertIn("No blocking or warning actions", render_markdown(plan))

    def test_triage_recommendations_are_deduplicated(self) -> None:
        plan = build_operator_next_steps(
            health_results=[{"name": "core_deps", "status": "fail", "detail": "FastAPI missing", "remediation": ""}],
            manifest={"file_count": 1, "missing_expected": []},
            triage_summary={
                "status": "blocked",
                "recommended_actions": [
                    {"reason": "fail health check: core_deps", "target": "make install-core", "detail": "FastAPI missing"},
                    {"reason": "missing artifact: dashboard-mockup.html", "target": "make dashboard", "detail": "Missing dashboard"},
                ],
            },
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        keys = {(action["reason"], action["target"]) for action in plan["actions"]}

        self.assertEqual(len(keys), len(plan["actions"]))
        self.assertIn(("fail health check: core_deps", "make install-core"), keys)
        self.assertIn(("missing artifact: dashboard-mockup.html", "make dashboard"), keys)

    def test_analytical_guardrails_are_rendered_and_serialized(self) -> None:
        plan = build_operator_next_steps(
            health_results=[],
            manifest={"file_count": 2, "missing_expected": []},
            triage_summary={"status": "ready", "recommended_actions": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        markdown = render_markdown(plan)

        self.assertIn("analytical_guardrails", plan)
        self.assertGreaterEqual(len(plan["analytical_guardrails"]), 3)
        self.assertIn("## Analytical guardrails", markdown)
        self.assertIn("not operational targeting instructions", markdown)
        self.assertIn("Communicate uncertainty", markdown)

    def test_writers_create_markdown_and_json(self) -> None:
        plan = build_operator_next_steps(
            health_results=[],
            manifest={"file_count": 0, "missing_expected": []},
            triage_summary={"status": "ready", "recommended_actions": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "operator-next-steps.md"
            json_path = Path(temp_dir) / "operator-next-steps.json"

            write_outputs(plan, markdown_path, json_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Operator Next Steps", markdown)
        self.assertEqual(parsed["status"], "ready")
        self.assertIn("analytical_guardrails", parsed)


if __name__ == "__main__":
    unittest.main()
