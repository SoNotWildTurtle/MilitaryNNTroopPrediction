"""Tests for evidence checklist generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.evidence_checklist import build_evidence_checklist, render_markdown, write_outputs


class EvidenceChecklistTests(unittest.TestCase):
    """Verify evidence checklist behavior for ready and blocked bundles."""

    def test_ready_bundle_passes_all_baseline_checks(self) -> None:
        report = build_evidence_checklist(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest={
                "files": [
                    {"path": "artifact-manifest.json"},
                    {"path": "artifact-provenance-ledger.json"},
                    {"path": "triage-summary.json"},
                    {"path": "reviewer-handoff.json"},
                    {"path": "uncertainty-review-packet.json"},
                    {"path": "handoff-integrity-report.json"},
                ],
                "missing_expected": [],
                "suspicious_artifacts": [],
            },
            provenance={"entries": [{"path": "artifact-manifest.json", "label": "review"}]},
            triage={"status": "ready", "recommended_actions": []},
            handoff={"review_status": "ready"},
            uncertainty={"recommended_actions": [{"action": "acknowledge analytical estimate limits"}]},
            integrity={"status": "pass"},
        )

        markdown = render_markdown(report)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["summary"], {"pass": 8, "warn": 0, "fail": 0})
        self.assertIn("# Evidence Checklist", markdown)
        self.assertIn("required_review_artifacts", markdown)
        self.assertIn("lawful defensive analysis", report["safe_scope"])

    def test_missing_required_artifacts_block_handoff(self) -> None:
        report = build_evidence_checklist(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest={"files": [], "missing_expected": ["reviewer-handoff.json"]},
            provenance={"entries": []},
            triage={"status": "blocked", "recommended_actions": [{"target": "make ci-report"}]},
            handoff={"review_status": "blocked"},
            uncertainty={"recommended_actions": []},
            integrity={"status": "fail"},
        )

        failed_checks = {check["name"] for check in report["checks"] if check["status"] == "fail"}

        self.assertEqual(report["status"], "blocked")
        self.assertIn("required_review_artifacts", failed_checks)
        self.assertIn("manifest_completeness", failed_checks)
        self.assertIn("Repair failing evidence checks", report["next_action"])

    def test_artifact_directory_presence_can_satisfy_required_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            for name in (
                "artifact-manifest.json",
                "artifact-provenance-ledger.json",
                "triage-summary.json",
                "reviewer-handoff.json",
                "uncertainty-review-packet.json",
                "handoff-integrity-report.json",
            ):
                (artifact_dir / name).write_text("{}\n", encoding="utf-8")

            report = build_evidence_checklist(
                artifact_dir=artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                manifest={"files": [], "missing_expected": [], "suspicious_artifacts": []},
                provenance={"entries": [{"path": "local"}]},
                triage={"status": "ready", "recommended_actions": []},
                handoff={"review_status": "ready"},
                uncertainty={"recommended_actions": [{"action": "review"}]},
                integrity={"status": "ready"},
            )

        required_check = next(check for check in report["checks"] if check["name"] == "required_review_artifacts")
        self.assertEqual(required_check["status"], "pass")

    def test_writers_create_markdown_and_json(self) -> None:
        report = build_evidence_checklist(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest={"files": [], "missing_expected": []},
            provenance={"entries": []},
            triage={},
            handoff={},
            uncertainty={},
            integrity={},
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "evidence-checklist.md"
            json_path = Path(temp_dir) / "evidence-checklist.json"

            write_outputs(report, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Evidence Checklist", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
