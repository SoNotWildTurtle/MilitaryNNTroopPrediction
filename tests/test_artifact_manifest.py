"""Tests for diagnostic artifact manifest generation."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.artifact_manifest import build_manifest, write_json, write_markdown


class ArtifactManifestTests(unittest.TestCase):
    """Verify generated artifact indexes are deterministic and useful."""

    def test_manifest_indexes_files_with_hashes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "python-version.txt").write_text("Python 3.11.0\n", encoding="utf-8")
            (artifact_dir / "nested").mkdir()
            (artifact_dir / "nested" / "extra.txt").write_text("extra\n", encoding="utf-8")

            manifest = build_manifest(artifact_dir)

        paths = [entry["path"] for entry in manifest["files"]]
        self.assertEqual(paths, ["nested/extra.txt", "python-version.txt"])
        self.assertEqual(manifest["file_count"], 2)
        self.assertGreater(manifest["total_size_bytes"], 0)
        self.assertEqual(len(manifest["files"][0]["sha256"]), 64)
        self.assertIn("pip-version.txt", manifest["missing_expected"])

    def test_manifest_writers_create_json_and_markdown(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir) / "artifacts"
            artifact_dir.mkdir()
            (artifact_dir / "summary.txt").write_text("bundle summary\n", encoding="utf-8")
            manifest = build_manifest(artifact_dir)
            json_path = artifact_dir / "artifact-manifest.json"
            markdown_path = artifact_dir / "artifact-manifest.md"

            write_json(manifest, json_path)
            write_markdown(manifest, markdown_path)

            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(parsed["file_count"], 1)
        self.assertIn("summary.txt", markdown)
        self.assertIn("# Diagnostic artifact manifest", markdown)


if __name__ == "__main__":
    unittest.main()
