"""Tests for diagnostic artifact gap reports."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.artifact_gap_report import MIN_SIZE_BYTES, build_gap_report, write_json, write_markdown
from app.cli.artifact_manifest import EXPECTED_ARTIFACTS


class ArtifactGapReportTests(unittest.TestCase):
    """Verify artifact gap reporting catches incomplete bundles."""

    def test_gap_report_flags_missing_and_empty_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            manifest_path = artifact_dir / "artifact-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "artifact_dir": artifact_dir.as_posix(),
                        "files": [
                            {
                                "path": "python-version.txt",
                                "size_bytes": 0,
                                "sha256": "0" * 64,
                            }
                        ],
                        "missing_expected": ["pip-version.txt"],
                    }
                ),
                encoding="utf-8",
            )

            report = build_gap_report(artifact_dir)

        self.assertEqual(report["severity"], "fail")
        self.assertIn("pip-version.txt", report["missing_expected"])
        self.assertIn("python-version.txt", report["empty_files"])

    def test_gap_report_writers_create_json_and_markdown(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            manifest_path = artifact_dir / "artifact-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "artifact_dir": artifact_dir.as_posix(),
                        "files": [
                            {
                                "path": "python-version.txt",
                                "size_bytes": 13,
                                "sha256": "a" * 64,
                            }
                        ],
                        "missing_expected": [],
                    }
                ),
                encoding="utf-8",
            )
            report = build_gap_report(artifact_dir)
            json_path = artifact_dir / "artifact-gap-report.json"
            markdown_path = artifact_dir / "artifact-gap-report.md"

            write_json(report, json_path)
            write_markdown(report, markdown_path)

            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertIn("severity", parsed)
        self.assertIn("# Diagnostic artifact gap report", markdown)
        self.assertIn("Recommended next step", markdown)

    def test_acceptance_artifacts_are_expected_and_size_checked(self) -> None:
        expected = {
            "implementation-acceptance-checklist.md",
            "implementation-acceptance-checklist.json",
            "implementation-acceptance-handoff.md",
            "implementation-acceptance-handoff.json",
            "implementation-acceptance-checklist-help.txt",
            "implementation-acceptance-handoff-help.txt",
        }

        self.assertTrue(expected.issubset(EXPECTED_ARTIFACTS))
        self.assertTrue(expected.intersection(MIN_SIZE_BYTES).issuperset(
            {
                "implementation-acceptance-checklist.md",
                "implementation-acceptance-checklist.json",
                "implementation-acceptance-handoff.md",
                "implementation-acceptance-handoff.json",
            }
        ))

    def test_gap_report_flags_missing_acceptance_handoff(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "artifact-manifest.json").write_text(
                json.dumps(
                    {
                        "artifact_dir": artifact_dir.as_posix(),
                        "files": [
                            {
                                "path": "implementation-acceptance-checklist.json",
                                "size_bytes": 64,
                                "sha256": "b" * 64,
                            }
                        ],
                        "missing_expected": [],
                    }
                ),
                encoding="utf-8",
            )

            report = build_gap_report(artifact_dir)

        self.assertEqual(report["severity"], "fail")
        self.assertIn("implementation-acceptance-handoff.json", report["missing_expected"])


if __name__ == "__main__":
    unittest.main()
