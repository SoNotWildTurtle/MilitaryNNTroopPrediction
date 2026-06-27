"""Tests for release bundle index generation."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.release_bundle_index import render_html, write_html


class ReleaseBundleIndexTests(unittest.TestCase):
    """Verify the release bundle HTML is useful for reviewers."""

    def test_render_html_links_key_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.json").write_text(
                '{"status":"pass","checks":[{"name":"doctor","status":"pass"}]}\n',
                encoding="utf-8",
            )
            (artifact_dir / "doctor-minimal.json").write_text(
                '{"checks":[{"name":"python","status":"pass"}]}\n',
                encoding="utf-8",
            )
            (artifact_dir / "release-health.md").write_text("# Release health\n", encoding="utf-8")
            (artifact_dir / "openapi-summary.md").write_text("# API\n", encoding="utf-8")
            (artifact_dir / "dashboard-mockup.html").write_text("<h1>Mockup</h1>\n", encoding="utf-8")
            (artifact_dir / "reviewer-handoff.md").write_text(
                "# Reviewer handoff\n\nRecommended local rerun: `make verify`\n",
                encoding="utf-8",
            )
            (artifact_dir / "reviewer-handoff.json").write_text(
                "{\n"
                '  "review_status": "ready",\n'
                '  "release_status": "pass",\n'
                '  "recommended_rerun": "make verify",\n'
                '  "missing_expected": [],\n'
                '  "missing_key_artifacts": [],\n'
                '  "copyable_summary": "Reviewer handoff for `ci_artifacts`: status `ready`."\n'
                "}\n",
                encoding="utf-8",
            )
            (artifact_dir / "operator-next-steps.md").write_text(
                "# Operator next steps\n\nHighest ranked safe action: review release bundle.\n",
                encoding="utf-8",
            )
            (artifact_dir / "operator-next-steps.json").write_text(
                '{"recommended_action":"review release bundle","rank":1}\n',
                encoding="utf-8",
            )
            (artifact_dir / "triage-summary.md").write_text(
                "# CI triage summary\n\nRecommended rerun: make verify\n",
                encoding="utf-8",
            )
            (artifact_dir / "triage-summary.json").write_text(
                '{"recommended_rerun":"make verify"}\n',
                encoding="utf-8",
            )
            (artifact_dir / "artifact-manifest.md").write_text("# Manifest\n", encoding="utf-8")
            (artifact_dir / "summary.txt").write_text("bundle summary\n", encoding="utf-8")

            html_text = render_html(artifact_dir)

        self.assertIn("Release bundle index", html_text)
        self.assertIn("Release readiness summary", html_text)
        self.assertIn("Copyable reviewer handoff and review order", html_text)
        self.assertIn('href="reviewer-handoff.md"', html_text)
        self.assertIn('href="reviewer-handoff.json"', html_text)
        self.assertIn("Reviewer handoff", html_text)
        self.assertIn("Handoff status", html_text)
        self.assertIn("Review status", html_text)
        self.assertIn("READY", html_text)
        self.assertIn('class="badge status-ready"', html_text)
        self.assertIn("Release status", html_text)
        self.assertIn("Recommended local rerun", html_text)
        self.assertIn("Recommended rerun", html_text)
        self.assertIn("Missing expected outputs", html_text)
        self.assertIn("Missing key artifacts", html_text)
        self.assertIn("Reviewer handoff for `ci_artifacts`: status `ready`.", html_text)
        self.assertIn("Ranked safe follow-up actions for operators", html_text)
        self.assertIn("Machine-readable operator next-step plan", html_text)
        self.assertIn('href="operator-next-steps.md"', html_text)
        self.assertIn('href="operator-next-steps.json"', html_text)
        self.assertIn("Promote operator next step", html_text)
        self.assertIn("CI triage summary and rerun targets", html_text)
        self.assertIn('href="triage-summary.md"', html_text)
        self.assertIn('href="triage-summary.json"', html_text)
        self.assertIn("Recommended rerun: make verify", html_text)
        self.assertIn('href="openapi-summary.md"', html_text)
        self.assertIn('href="dashboard-mockup.html"', html_text)
        self.assertIn("bundle summary", html_text)
        self.assertIn("PASS", html_text)

    def test_render_html_includes_review_order_checklist(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            for name in (
                "release-health.md",
                "reviewer-handoff.md",
                "operator-next-steps.md",
                "triage-summary.md",
                "artifact-manifest.md",
                "openapi-summary.md",
            ):
                (artifact_dir / name).write_text(f"# {name}\n", encoding="utf-8")

            html_text = render_html(artifact_dir)

        self.assertIn("Review order checklist", html_text)
        self.assertIn("Confirm bundle readiness", html_text)
        self.assertIn("Use the reviewer handoff", html_text)
        self.assertIn("Promote operator next step", html_text)
        self.assertIn("Triage failures next", html_text)
        self.assertIn("Verify artifact inventory", html_text)
        self.assertIn("Review user-facing contracts", html_text)
        self.assertIn('href="release-health.md"', html_text)
        self.assertIn('href="operator-next-steps.md"', html_text)
        self.assertIn('href="artifact-manifest.md"', html_text)

    def test_render_html_flags_missing_review_order_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.md").write_text("# Release health\n", encoding="utf-8")

            html_text = render_html(artifact_dir)

        self.assertIn("Review order checklist", html_text)
        self.assertIn("operator-next-steps.md", html_text)
        self.assertIn("PRESENT", html_text)
        self.assertIn("MISSING", html_text)
        self.assertIn('class="badge status-attention"', html_text)

    def test_render_html_flags_missing_reviewer_handoff_json(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.json").write_text(
                '{"status":"pass","checks":[]}\n',
                encoding="utf-8",
            )

            html_text = render_html(artifact_dir)

        self.assertIn("Reviewer handoff", html_text)
        self.assertIn("MISSING", html_text)
        self.assertIn('class="badge status-attention"', html_text)
        self.assertIn("Generate reviewer-handoff.json", html_text)

    def test_render_html_badges_warning_reviewer_status(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.json").write_text(
                '{"status":"review_warnings","checks":[]}\n',
                encoding="utf-8",
            )
            (artifact_dir / "reviewer-handoff.json").write_text(
                "{\n"
                '  "review_status": "needs_attention",\n'
                '  "release_status": "review_warnings",\n'
                '  "recommended_rerun": "make verify",\n'
                '  "missing_expected": ["release-health.md"],\n'
                '  "missing_key_artifacts": ["reviewer-handoff.md"]\n'
                "}\n",
                encoding="utf-8",
            )

            html_text = render_html(artifact_dir)

        self.assertIn("NEEDS ATTENTION", html_text)
        self.assertIn("REVIEW WARNINGS", html_text)
        self.assertIn('class="badge status-attention"', html_text)
        self.assertIn('class="badge status-warning"', html_text)
        self.assertIn('class="handoff-status status-attention-panel"', html_text)

    def test_render_html_accepts_list_shaped_doctor_diagnostics(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "release-health.json").write_text(
                '[{"name":"doctor","status":"pass"}]\n',
                encoding="utf-8",
            )
            (artifact_dir / "doctor-minimal.json").write_text(
                '[{"name":"python","status":"pass"},{"name":"optional-db","status":"fail"}]\n',
                encoding="utf-8",
            )

            html_text = render_html(artifact_dir)

        self.assertIn("Release bundle index", html_text)
        self.assertIn("1/1 readiness checks passed", html_text)
        self.assertIn("Doctor failures", html_text)
        self.assertIn("FAIL", html_text)
        self.assertIn('class="card status-attention-card"', html_text)

    def test_write_html_creates_parent_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "nested" / "index.html"
            write_html("<html></html>\n", output_path)
            written = output_path.read_text(encoding="utf-8")

        self.assertEqual(written, "<html></html>\n")


if __name__ == "__main__":
    unittest.main()
