"""Tests for reviewer handoff generation."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.reviewer_handoff import build_handoff, render_markdown, write_json, write_markdown


class ReviewerHandoffTests(unittest.TestCase):
    """Verify handoff artifacts are useful, deterministic, and safe to share."""

    def test_build_handoff_summarizes_manifest_health_and_triage(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            manifest = {
                "missing_expected": ["openapi.json"],
                "files": [
                    {
                        "path": "release-bundle-index.html",
                        "size_bytes": 123,
                        "sha256": "a" * 64,
                    },
                    {
                        "path": "release-health.md",
                        "size_bytes": 99,
                        "sha256": "b" * 64,
                    },
                ],
            }
            (artifact_dir / "artifact-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (artifact_dir / "release-health.json").write_text('{"status":"warn"}\n', encoding="utf-8")
            (artifact_dir / "triage-summary.json").write_text(
                '{"recommended_rerun":"make openapi"}\n', encoding="utf-8"
            )
            (artifact_dir / "release-health.md").write_text("# Release health\n", encoding="utf-8")
            (artifact_dir / "triage-summary.md").write_text("# Triage\n", encoding="utf-8")

            handoff = build_handoff(artifact_dir)
            markdown = render_markdown(handoff)

        self.assertEqual(handoff["release_status"], "warn")
        self.assertEqual(handoff["review_status"], "needs_attention")
        self.assertEqual(handoff["recommended_rerun"], "make openapi")
        self.assertIn("openapi.json", handoff["missing_expected"])
        self.assertIn("artifact-manifest.md", handoff["missing_key_artifacts"])
        self.assertIn("release-bundle-index.html", markdown)
        self.assertIn("Copyable summary", markdown)
        self.assertIn("Safe review scope", markdown)
        self.assertIn("make openapi", markdown)
        self.assertIn("needs_attention", handoff["copyable_summary"])
        self.assertIn("yes", markdown)

    def test_build_handoff_includes_machine_readable_review_order(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            manifest = {
                "missing_expected": [],
                "files": [
                    {"path": "release-health.md", "size_bytes": 1, "sha256": "d" * 64},
                    {"path": "reviewer-handoff.md", "size_bytes": 1, "sha256": "e" * 64},
                ],
            }
            (artifact_dir / "artifact-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            handoff = build_handoff(artifact_dir)
            markdown = render_markdown(handoff)

        review_order = handoff["review_order"]
        self.assertEqual(review_order[0]["step"], 1)
        self.assertEqual(review_order[0]["action"], "Confirm bundle readiness")
        self.assertEqual(review_order[0]["artifact"], "release-health.md")
        self.assertTrue(review_order[0]["present"])
        self.assertEqual(review_order[0]["status"], "present")
        self.assertEqual(review_order[2]["artifact"], "triage-summary.md")
        self.assertFalse(review_order[2]["present"])
        self.assertEqual(review_order[2]["status"], "missing")
        self.assertIn("Confirm bundle readiness", markdown)
        self.assertIn("`triage-summary.md` (missing)", markdown)

    def test_build_handoff_has_safe_defaults_without_inputs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            handoff = build_handoff(Path(temp_dir))
            markdown = render_markdown(handoff)

        self.assertEqual(handoff["release_status"], "unknown")
        self.assertEqual(handoff["review_status"], "needs_attention")
        self.assertEqual(handoff["recommended_rerun"], "make verify")
        self.assertEqual(handoff["review_order"][0]["status"], "missing")
        self.assertIn("UNKNOWN", markdown)
        self.assertIn("NEEDS_ATTENTION", markdown)
        self.assertIn("make verify", markdown)
        self.assertIn("missing key artifact", handoff["copyable_summary"])

    def test_build_handoff_marks_complete_pass_bundle_ready(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            manifest = {
                "missing_expected": [],
                "files": [
                    {"path": name, "size_bytes": 1, "sha256": "c" * 64}
                    for name in [
                        "release-bundle-index.html",
                        "release-health.md",
                        "triage-summary.md",
                        "release-notes.md",
                        "artifact-manifest.md",
                        "openapi-summary.md",
                        "api-response-examples.md",
                        "dashboard-mockup.html",
                        "reviewer-handoff.md",
                    ]
                ],
            }
            (artifact_dir / "artifact-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (artifact_dir / "release-health.json").write_text('{"status":"pass"}\n', encoding="utf-8")

            handoff = build_handoff(artifact_dir)
            markdown = render_markdown(handoff)

        self.assertEqual(handoff["review_status"], "ready")
        self.assertEqual(handoff["missing_key_artifacts"], [])
        self.assertTrue(all(step["present"] for step in handoff["review_order"]))
        self.assertIn("READY", markdown)
        self.assertIn("0 missing expected output", handoff["copyable_summary"])

    def test_writers_create_parent_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "nested"
            markdown_path = output_dir / "reviewer-handoff.md"
            json_path = output_dir / "reviewer-handoff.json"
            handoff = {
                "generated_at": "now",
                "artifact_dir": "ci_artifacts",
                "review_status": "ready",
                "release_status": "pass",
                "recommended_rerun": "make verify",
                "missing_expected": [],
                "missing_key_artifacts": [],
                "key_artifacts": [],
                "review_order": [],
                "copyable_summary": "ready",
            }

            write_markdown("# Handoff\n", markdown_path)
            write_json(handoff, json_path)

            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "# Handoff\n")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["release_status"], "pass")


if __name__ == "__main__":
    unittest.main()
