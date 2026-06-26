"""Tests for operator runbook index generation."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.operator_runbook_index import (
    build_runbook_index,
    render_markdown,
    write_json,
    write_markdown,
)


class OperatorRunbookIndexTests(unittest.TestCase):
    """Verify the runbook index stays deterministic, safe, and useful."""

    def test_build_runbook_index_maps_commands_docs_and_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-bundle-index.html").write_text("<html></html>\n", encoding="utf-8")
            (artifact_dir / "operator-status-board.md").write_text("# Status\n", encoding="utf-8")

            index = build_runbook_index(artifact_dir)
            markdown = render_markdown(index)

        self.assertEqual(index["schema_version"], "militarynntroopprediction.operator_runbook_index.v1")
        self.assertEqual(index["artifact_dir"], artifact_dir.as_posix())
        self.assertIn("validation", index["command_categories"])
        self.assertIn("orientation", index["doc_categories"])
        self.assertIn("handoff", index["artifact_categories"])
        self.assertTrue(any(row["command"] == "make verify" for row in index["commands"]))
        self.assertTrue(any(row["path"] == "release-bundle-index.html" and row["present"] for row in index["artifacts"]))
        self.assertIn("operator-session-plan.md", index["missing_artifacts"])
        self.assertIn("Operator runbook index", markdown)
        self.assertIn("make verify", markdown)
        self.assertIn("Safe operating scope", markdown)
        self.assertIn("collection", markdown.lower())

    def test_missing_artifacts_are_not_failures(self) -> None:
        with TemporaryDirectory() as temp_dir:
            index = build_runbook_index(Path(temp_dir))
            markdown = render_markdown(index)

        self.assertGreater(len(index["missing_artifacts"]), 0)
        self.assertIn("not_generated_yet", {row["status"] for row in index["artifacts"]})
        self.assertIn("Artifacts not generated yet", markdown)
        self.assertIn("Start with `make verify`", index["copyable_handoff"])

    def test_writers_create_parent_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "nested"
            markdown_path = output_dir / "operator-runbook-index.md"
            json_path = output_dir / "operator-runbook-index.json"
            index = build_runbook_index(Path(temp_dir))

            write_markdown("# Runbook\n", markdown_path)
            write_json(index, json_path)

            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "# Runbook\n")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["schema_version"], index["schema_version"])


if __name__ == "__main__":
    unittest.main()
