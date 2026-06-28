"""Tests for analytical framing audit generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.analytical_framing_audit import (
    build_analytical_framing_audit,
    render_markdown,
    write_outputs,
)


class AnalyticalFramingAuditTests(unittest.TestCase):
    """Verify deterministic safe-framing audit behavior."""

    def test_ready_audit_accepts_caveated_analytical_language(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "reviewer-handoff.md").write_text(
                "This analytical estimate uses synthetic examples and documents uncertainty.\n",
                encoding="utf-8",
            )

            report = build_analytical_framing_audit(
                artifact_dir=artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            markdown = render_markdown(report)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["severity_counts"]["warn"], 0)
        self.assertIn("# Analytical Framing Audit", markdown)
        self.assertIn("does not validate ground truth", report["safe_scope"])

    def test_audit_flags_overconfident_and_operational_wording(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "operator-status-board.md").write_text(
                "The prediction will happen and creates an actionable target package.\n",
                encoding="utf-8",
            )

            report = build_analytical_framing_audit(
                artifact_dir=artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

        self.assertEqual(report["status"], "needs_review")
        rules = {finding["rule"] for finding in report["findings"]}
        self.assertIn("certainty_language", rules)
        self.assertIn("operational_framing", rules)
        self.assertGreaterEqual(report["severity_counts"]["warn"], 2)

    def test_missing_scope_terms_are_informational_only(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "summary.txt").write_text("Plain status output.\n", encoding="utf-8")

            report = build_analytical_framing_audit(
                artifact_dir=artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["severity_counts"]["warn"], 0)
        self.assertEqual(report["severity_counts"]["info"], 1)
        self.assertEqual(report["findings"][0]["rule"], "missing_safe_scope_terms")

    def test_custom_include_patterns_limit_scanned_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "included.md").write_text("Guaranteed result.\n", encoding="utf-8")
            (artifact_dir / "ignored.json").write_text("{\"status\": \"guaranteed\"}\n", encoding="utf-8")

            report = build_analytical_framing_audit(
                artifact_dir=artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                include_patterns=("*.md",),
            )

        self.assertEqual(report["scanned_files"], ["included.md"])
        self.assertTrue(all(finding["path"] == "included.md" for finding in report["findings"]))

    def test_writers_create_markdown_and_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir) / "artifacts"
            artifact_dir.mkdir()
            (artifact_dir / "reviewer-handoff.md").write_text(
                "Analytical estimate with uncertainty caveats.\n",
                encoding="utf-8",
            )
            report = build_analytical_framing_audit(
                artifact_dir=artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            markdown_path = Path(temp_dir) / "analytical-framing-audit.md"
            json_path = Path(temp_dir) / "analytical-framing-audit.json"

            write_outputs(report, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Analytical Framing Audit", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
