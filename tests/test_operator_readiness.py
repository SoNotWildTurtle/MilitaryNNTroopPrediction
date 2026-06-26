import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.cli.operator_readiness import build_readiness_brief, main, render_markdown


class OperatorReadinessTests(unittest.TestCase):
    def test_ready_bundle_returns_ready_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "release-health.json").write_text(
                json.dumps([
                    {"name": "python", "status": "ok", "detail": "Python available"},
                    {"name": "api_contract", "status": "ok", "detail": "OpenAPI exported"},
                ]),
                encoding="utf-8",
            )
            files = [
                {"path": path, "size_bytes": 1, "sha256": "0" * 64}
                for path in [
                    "release-health.json",
                    "release-health.md",
                    "artifact-manifest.json",
                    "artifact-manifest.md",
                    "triage-summary.json",
                    "triage-summary.md",
                    "reviewer-handoff.json",
                    "reviewer-handoff.md",
                ]
            ]
            (artifact_dir / "artifact-manifest.json").write_text(
                json.dumps({"file_count": len(files), "files": files, "missing_expected": []}),
                encoding="utf-8",
            )
            (artifact_dir / "triage-summary.json").write_text(
                json.dumps({"next_step": "make verify"}),
                encoding="utf-8",
            )

            brief = build_readiness_brief(
                artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

            self.assertEqual(brief["launch_status"], "ready")
            self.assertEqual(brief["health_summary"]["ok"], 2)
            self.assertEqual(brief["missing_required_artifacts"], [])
            self.assertIn("release-bundle-index.html", brief["next_step"])

    def test_missing_required_artifact_blocks_launch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp)
            (artifact_dir / "release-health.json").write_text(
                json.dumps([{"name": "python", "status": "ok", "detail": "Python available"}]),
                encoding="utf-8",
            )
            (artifact_dir / "artifact-manifest.json").write_text(
                json.dumps({"file_count": 1, "files": [{"path": "release-health.json"}], "missing_expected": []}),
                encoding="utf-8",
            )
            (artifact_dir / "triage-summary.json").write_text(
                json.dumps({"next_step": "make ci-report"}),
                encoding="utf-8",
            )

            brief = build_readiness_brief(artifact_dir)

            self.assertEqual(brief["launch_status"], "blocked")
            self.assertIn("artifact-manifest.md", brief["missing_required_artifacts"])
            self.assertEqual(brief["next_step"], "make ci-report")

    def test_markdown_contains_operator_decision_and_scope(self) -> None:
        brief = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "artifact_dir": "ci_artifacts",
            "launch_status": "review",
            "signal_status": "warn",
            "operator_decision": "Review warnings before launch.",
            "next_step": "make verify",
            "health_summary": {"ok": 1, "warn": 1, "fail": 0, "unknown": 0},
            "artifact_count": 8,
            "failing_checks": [],
            "warning_checks": [{"name": "optional_deps", "detail": "Optional stack not installed"}],
            "missing_expected": [],
            "missing_required_artifacts": [],
            "required_artifacts": [
                {"path": "release-health.json", "status": "present", "purpose": "Readiness checks"}
            ],
            "safe_scope": "Summarizes local diagnostic artifacts only.",
        }

        markdown = render_markdown(brief)

        self.assertIn("Operator Readiness Brief", markdown)
        self.assertIn("Review warnings before launch.", markdown)
        self.assertIn("optional_deps", markdown)
        self.assertIn("Summarizes local diagnostic artifacts only.", markdown)

    def test_cli_writes_markdown_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifact_dir = Path(tmp) / "artifacts"
            markdown_path = Path(tmp) / "readiness.md"
            json_path = Path(tmp) / "readiness.json"

            exit_code = main(
                [
                    "--artifact-dir",
                    str(artifact_dir),
                    "--markdown-path",
                    str(markdown_path),
                    "--json-path",
                    str(json_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(markdown_path.exists())
            self.assertTrue(json_path.exists())
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["launch_status"], "blocked")


if __name__ == "__main__":
    unittest.main()
