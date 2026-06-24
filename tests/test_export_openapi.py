"""Smoke tests for OpenAPI contract export helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.cli import export_openapi


class ExportOpenApiTests(unittest.TestCase):
    """Verify OpenAPI artifacts are useful and generated without launching a server."""

    def test_render_markdown_lists_routes(self) -> None:
        schema = export_openapi.app.openapi()
        markdown = export_openapi.render_markdown(schema)

        self.assertIn("# OpenAPI Contract Summary", markdown)
        self.assertIn("`/healthz`", markdown)
        self.assertIn("`/readyz`", markdown)
        self.assertIn("`/predict/{area}`", markdown)

    def test_write_openapi_outputs_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "openapi.json"
            markdown_path = Path(tmpdir) / "openapi-summary.md"

            written_json, written_markdown, schema = export_openapi.write_openapi(
                json_path=json_path,
                markdown_path=markdown_path,
            )

            self.assertEqual(written_json, json_path)
            self.assertEqual(written_markdown, markdown_path)
            self.assertTrue(json_path.exists())
            self.assertTrue(markdown_path.exists())
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["info"]["title"], schema["info"]["title"])
            self.assertIn("/healthz", loaded["paths"])

    def test_main_accepts_no_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "schema.json"
            exit_code = export_openapi.main(["--json-path", str(json_path), "--no-markdown"])

            self.assertEqual(exit_code, 0)
            self.assertTrue(json_path.exists())


if __name__ == "__main__":
    unittest.main()
