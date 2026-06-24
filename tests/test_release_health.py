"""Smoke tests for release health report generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.cli import doctor, release_health


class ReleaseHealthTests(unittest.TestCase):
    """Verify release health reports stay deterministic and safe."""

    def test_render_markdown_includes_summary_and_remediation(self) -> None:
        results = [
            doctor.CheckResult("python", "ok", "3.11.0"),
            doctor.CheckResult("optional", "warn", "missing optional package", "install optional deps"),
        ]

        report = release_health.render_markdown(results)

        self.assertIn("# Release Health", report)
        self.assertIn("- OK: 1", report)
        self.assertIn("- Warnings: 1", report)
        self.assertIn("`python`", report)
        self.assertIn("install optional deps", report)

    def test_write_reports_creates_markdown_and_json(self) -> None:
        fake_results = [doctor.CheckResult("python", "ok", "3.11.0")]
        with tempfile.TemporaryDirectory() as tmpdir:
            markdown_path = Path(tmpdir) / "health.md"
            json_path = Path(tmpdir) / "health.json"
            with mock.patch.object(release_health.doctor, "run_checks", return_value=fake_results):
                written_md, written_json, failures = release_health.write_reports(
                    markdown_path=markdown_path,
                    json_path=json_path,
                    include_optional=False,
                    check_mongo=False,
                )

            self.assertEqual(written_md, markdown_path)
            self.assertEqual(written_json, json_path)
            self.assertEqual(failures, 0)
            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            self.assertIn("Release Health", markdown_path.read_text(encoding="utf-8"))
            self.assertIn('"name": "python"', json_path.read_text(encoding="utf-8"))

    def test_parser_defaults_to_ci_safe_checks(self) -> None:
        args = release_health.build_parser().parse_args([])
        self.assertFalse(args.check_optional)
        self.assertFalse(args.check_mongo)
        self.assertFalse(args.no_json)


if __name__ == "__main__":
    unittest.main()
