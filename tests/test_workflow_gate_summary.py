"""Tests for the offline workflow gate summary exporter."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from app.cli.workflow_gate_summary import (
    DEFAULT_GATES,
    SAFE_SCOPE,
    build_workflow_gate_summary,
    render_markdown,
    write_outputs,
)


class WorkflowGateSummaryTests(unittest.TestCase):
    """Keep workflow validation guidance deterministic and safe-scoped."""

    def test_default_summary_names_required_gates_and_commands(self) -> None:
        generated_at = datetime(2026, 6, 28, 15, 0, tzinfo=timezone.utc)
        summary = build_workflow_gate_summary(generated_at=generated_at)

        gate_names = {gate["name"] for gate in summary["gates"]}
        self.assertEqual({"CI", "Analytical Framing Audit", "Handoff Validation Receipt"}, gate_names)
        self.assertEqual("ready_for_review", summary["status"])
        self.assertEqual(3, summary["required_gate_count"])
        self.assertIn("final PR head SHA", summary["next_action"])
        self.assertIn("not operational targeting guidance", summary["safe_scope"])
        self.assertIn("make verify", {gate["local_reproduction"].split()[0] + " " + gate["local_reproduction"].split()[1] for gate in summary["gates"] if gate["name"] == "CI"})

    def test_missing_required_workflow_blocks_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            summary = build_workflow_gate_summary(repo_root=repo_root)

        self.assertEqual("blocked", summary["status"])
        self.assertIn(".github/workflows/ci.yml", summary["missing_required_workflows"])
        self.assertTrue(any(gate["merge_blocker"] for gate in summary["gates"]))

    def test_markdown_preserves_green_meaning_and_limits(self) -> None:
        summary = build_workflow_gate_summary()
        markdown = render_markdown(summary)

        self.assertIn("# Workflow Gate Summary", markdown)
        self.assertIn("What green does not mean", markdown)
        self.assertIn("predictive truth", markdown)
        self.assertIn("Merge blockers", markdown)
        self.assertIn(SAFE_SCOPE, markdown)

    def test_writer_creates_json_and_markdown_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            markdown_path = output_dir / "summary.md"
            json_path = output_dir / "summary.json"
            summary = build_workflow_gate_summary(artifact_dir=output_dir)

            write_outputs(summary, markdown_path, json_path)

            self.assertIn("Workflow Gate Summary", markdown_path.read_text(encoding="utf-8"))
            self.assertIn('"required_gate_count": 3', json_path.read_text(encoding="utf-8"))

    def test_default_gates_are_required_before_merge(self) -> None:
        self.assertTrue(DEFAULT_GATES)
        self.assertTrue(all(gate.required_before_merge for gate in DEFAULT_GATES))
        self.assertTrue(all(".github/workflows/" in gate.workflow_path for gate in DEFAULT_GATES))


if __name__ == "__main__":
    unittest.main()
