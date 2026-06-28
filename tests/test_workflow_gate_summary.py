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

    def test_default_summary_includes_gate_evidence_to_collect(self) -> None:
        summary = build_workflow_gate_summary()

        for gate in summary["gates"]:
            with self.subTest(gate=gate["name"]):
                self.assertIn("evidence_to_collect", gate)
                self.assertIn("run URL", gate["evidence_to_collect"])
                self.assertIn("job conclusion", gate["evidence_to_collect"])
                self.assertIn("final", gate["evidence_to_collect"])
        self.assertTrue(any("uploaded artifact evidence" in item for item in summary["review_order"]))

    def test_default_summary_includes_narrow_rerun_targets(self) -> None:
        summary = build_workflow_gate_summary()

        self.assertIn("narrow_rerun_plan", summary)
        self.assertGreaterEqual(len(summary["narrow_rerun_plan"]), len(summary["gates"]))
        for gate in summary["gates"]:
            with self.subTest(gate=gate["name"]):
                self.assertIn("narrow_rerun_targets", gate)
                self.assertTrue(gate["narrow_rerun_targets"])
                self.assertTrue(all(" " in command for command in gate["narrow_rerun_targets"]))
        self.assertTrue(any(item["command"].startswith("python -m unittest") for item in summary["narrow_rerun_plan"]))
        self.assertTrue(any(item["gate"] == "Handoff Validation Receipt" for item in summary["narrow_rerun_plan"]))

    def test_missing_required_workflow_blocks_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            summary = build_workflow_gate_summary(repo_root=repo_root)

        self.assertEqual("blocked", summary["status"])
        self.assertIn(".github/workflows/ci.yml", summary["missing_required_workflows"])
        self.assertTrue(any(gate["merge_blocker"] for gate in summary["gates"]))

    def test_markdown_preserves_green_meaning_limits_evidence_and_reruns(self) -> None:
        summary = build_workflow_gate_summary()
        markdown = render_markdown(summary)

        self.assertIn("# Workflow Gate Summary", markdown)
        self.assertIn("What green does not mean", markdown)
        self.assertIn("predictive truth", markdown)
        self.assertIn("Merge blockers", markdown)
        self.assertIn("Evidence capture checklist", markdown)
        self.assertIn("Narrow rerun plan", markdown)
        self.assertIn("python -m unittest", markdown)
        self.assertIn("job conclusion", markdown)
        self.assertIn(SAFE_SCOPE, markdown)

    def test_writer_creates_json_and_markdown_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            markdown_path = output_dir / "summary.md"
            json_path = output_dir / "summary.json"
            summary = build_workflow_gate_summary(artifact_dir=output_dir)

            write_outputs(summary, markdown_path, json_path)

            self.assertIn("Workflow Gate Summary", markdown_path.read_text(encoding="utf-8"))
            json_text = json_path.read_text(encoding="utf-8")
            self.assertIn('"required_gate_count": 3', json_text)
            self.assertIn('"evidence_to_collect"', json_text)
            self.assertIn('"narrow_rerun_targets"', json_text)
            self.assertIn('"narrow_rerun_plan"', json_text)

    def test_default_gates_are_required_before_merge(self) -> None:
        self.assertTrue(DEFAULT_GATES)
        self.assertTrue(all(gate.required_before_merge for gate in DEFAULT_GATES))
        self.assertTrue(all(".github/workflows/" in gate.workflow_path for gate in DEFAULT_GATES))
        self.assertTrue(all("final" in gate.evidence_to_collect for gate in DEFAULT_GATES))
        self.assertTrue(all(gate.narrow_rerun_targets for gate in DEFAULT_GATES))


if __name__ == "__main__":
    unittest.main()
