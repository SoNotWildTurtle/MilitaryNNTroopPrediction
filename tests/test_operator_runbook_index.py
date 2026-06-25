"""Tests for operator runbook index generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.operator_runbook_index import build_runbook_index, render_markdown, write_outputs


class OperatorRunbookIndexTests(unittest.TestCase):
    """Verify generated operator runbook guidance is deterministic and useful."""

    def test_index_groups_commands_and_counts_outputs(self) -> None:
        index = build_runbook_index(generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))

        self.assertEqual(index["generated_at"], "2026-01-01T00:00:00+00:00")
        self.assertIn("make verify", index["first_steps"])
        self.assertIn("validation", index["commands_by_category"])
        self.assertGreaterEqual(index["counts"]["commands"], 10)
        self.assertGreaterEqual(index["counts"]["documents"], 5)
        self.assertGreaterEqual(index["counts"]["artifacts"], 5)

    def test_markdown_includes_safe_scope_commands_docs_and_artifacts(self) -> None:
        index = build_runbook_index(generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        markdown = render_markdown(index)

        self.assertIn("# Operator Runbook Index", markdown)
        self.assertIn("Local setup", markdown)
        self.assertIn("make runbook-index", markdown)
        self.assertIn("docs/common_tasks.md", markdown)
        self.assertIn("release-bundle-index.html", markdown)

    def test_writers_create_markdown_and_json(self) -> None:
        index = build_runbook_index(generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "operator-runbook-index.md"
            json_path = Path(temp_dir) / "operator-runbook-index.json"

            write_outputs(index, markdown_path, json_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("Operator Runbook Index", markdown)
        self.assertEqual(parsed["counts"]["commands"], index["counts"]["commands"])


if __name__ == "__main__":
    unittest.main()
