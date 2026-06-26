"""Tests for operator digest generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.operator_digest import build_operator_digest, render_markdown, write_outputs


class OperatorDigestTests(unittest.TestCase):
    """Verify operator digest summaries are deterministic and actionable."""

    def test_digest_prioritizes_triage_next_step(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            (artifact_dir / "artifact-manifest.json").write_text(
                json.dumps({"file_count": 7, "missing_expected": []}), encoding="utf-8"
            )
            (artifact_dir / "triage-summary.json").write_text(
                json.dumps({"status": "ready", "next_step": "Open release-bundle-index.html", "recommended_actions": []}),
                encoding="utf-8",
            )
            (artifact_dir / "reviewer-handoff.json").write_text(
                json.dumps({"review_status": "ready", "recommended_rerun": "make verify"}), encoding="utf-8"
            )

            digest = build_operator_digest(
                artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

        self.assertEqual(digest["status"], "ready")
        self.assertEqual(digest["status_label"], "Ready for review")
        self.assertEqual(digest["next_step"], "Open release-bundle-index.html")
        self.assertEqual(digest["artifact_count"], 7)
        self.assertIn("Ready for review", render_markdown(digest))

    def test_digest_surfaces_missing_outputs_and_actions(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "artifact-manifest.json").write_text(
                json.dumps({"file_count": 2, "missing_expected": ["openapi.json"]}), encoding="utf-8"
            )
            (artifact_dir / "triage-summary.json").write_text(
                json.dumps(
                    {
                        "status": "incomplete",
                        "next_step": "make openapi",
                        "recommended_actions": [
                            {"reason": "missing artifact: openapi.json", "target": "make openapi", "detail": "Not present"}
                        ],
                        "failing_checks": [],
                    }
                ),
                encoding="utf-8",
            )
            (artifact_dir / "reviewer-handoff.json").write_text(
                json.dumps({"review_status": "needs_attention", "missing_key_artifacts": ["release-health.md"]}),
                encoding="utf-8",
            )

            digest = build_operator_digest(
                artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
            markdown = render_markdown(digest)

        self.assertEqual(digest["status"], "needs_attention")
        self.assertEqual(digest["next_step"], "make openapi")
        self.assertIn("1 expected artifact", digest["blocking_reasons"][0])
        self.assertIn("openapi.json", markdown)
        self.assertIn("make openapi", markdown)

    def test_writers_create_requested_outputs(self) -> None:
        digest = build_operator_digest(generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "operator-digest.md"
            json_path = Path(temp_dir) / "operator-digest.json"

            write_outputs(digest, markdown_path, json_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Operator Digest", markdown)
        self.assertIn("safe_scope", parsed)


if __name__ == "__main__":
    unittest.main()
