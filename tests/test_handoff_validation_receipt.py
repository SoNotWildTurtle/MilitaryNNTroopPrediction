"""Tests for handoff validation receipt generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.handoff_validation_receipt import (
    build_handoff_validation_receipt,
    render_markdown,
    write_outputs,
)


class HandoffValidationReceiptTests(unittest.TestCase):
    """Verify deterministic validation receipt behavior."""

    def _ready_manifest(self) -> dict[str, object]:
        files = [
            {"path": "artifact-manifest.json", "sha256": "a" * 64, "size_bytes": 10},
            {"path": "artifact-provenance-ledger.json", "sha256": "b" * 64, "size_bytes": 11},
            {"path": "triage-summary.json", "sha256": "c" * 64, "size_bytes": 12},
            {"path": "reviewer-handoff.json", "sha256": "d" * 64, "size_bytes": 13},
            {"path": "uncertainty-review-packet.json", "sha256": "e" * 64, "size_bytes": 14},
            {"path": "handoff-integrity-report.json", "sha256": "f" * 64, "size_bytes": 15},
            {"path": "evidence-checklist.json", "sha256": "1" * 64, "size_bytes": 16},
        ]
        return {
            "file_count": len(files),
            "total_size_bytes": 91,
            "missing_expected": [],
            "scan_warnings": [],
            "files": files,
        }

    def test_ready_receipt_summarizes_bundle_identity(self) -> None:
        report = build_handoff_validation_receipt(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest=self._ready_manifest(),
            evidence={"status": "ready", "summary": {"pass": 8, "warn": 0, "fail": 0}},
            integrity={"status": "ready"},
            triage={"status": "ready"},
            handoff={"review_status": "ready"},
            uncertainty={"status": "ready"},
        )
        markdown = render_markdown(report)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["artifact_count"], 7)
        self.assertEqual(len(report["bundle_manifest_digest"]), 64)
        self.assertEqual(report["missing_required_artifacts"], [])
        self.assertIn("# Handoff Validation Receipt", markdown)
        self.assertIn("not operational targeting guidance", report["safe_scope"])

    def test_missing_required_artifact_blocks_receipt(self) -> None:
        manifest = self._ready_manifest()
        manifest["files"] = [entry for entry in manifest["files"] if entry["path"] != "evidence-checklist.json"]
        report = build_handoff_validation_receipt(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest=manifest,
            evidence={"status": "ready", "summary": {"pass": 8, "warn": 0, "fail": 0}},
            integrity={"status": "ready"},
            triage={"status": "ready"},
            handoff={"review_status": "ready"},
            uncertainty={"status": "ready"},
        )

        self.assertEqual(report["status"], "blocked")
        self.assertIn("evidence-checklist.json", report["missing_required_artifacts"])
        self.assertIn("missing required receipt artifacts", report["blockers"][0])

    def test_warning_status_requires_review_without_blocking(self) -> None:
        report = build_handoff_validation_receipt(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest=self._ready_manifest(),
            evidence={"status": "needs_review", "summary": {"pass": 7, "warn": 1, "fail": 0}},
            integrity={"status": "ready"},
            triage={"status": "ready"},
            handoff={"review_status": "ready"},
            uncertainty={"status": "ready"},
        )

        self.assertEqual(report["status"], "needs_review")
        self.assertEqual(report["blockers"], [])
        self.assertTrue(any("need review" in warning for warning in report["warnings"]))

    def test_artifact_directory_presence_can_satisfy_receipt_requirements(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            for name in (
                "artifact-manifest.json",
                "artifact-provenance-ledger.json",
                "triage-summary.json",
                "reviewer-handoff.json",
                "uncertainty-review-packet.json",
                "handoff-integrity-report.json",
                "evidence-checklist.json",
            ):
                (artifact_dir / name).write_text("{}\n", encoding="utf-8")

            report = build_handoff_validation_receipt(
                artifact_dir=artifact_dir,
                generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                manifest={"files": [], "missing_expected": [], "scan_warnings": []},
                evidence={"status": "ready", "summary": {"pass": 8, "warn": 0, "fail": 0}},
                integrity={"status": "ready"},
                triage={"status": "ready"},
                handoff={"review_status": "ready"},
                uncertainty={"status": "ready"},
            )

        self.assertEqual(report["missing_required_artifacts"], [])

    def test_writers_create_markdown_and_json(self) -> None:
        report = build_handoff_validation_receipt(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest=self._ready_manifest(),
            evidence={"status": "ready", "summary": {"pass": 8, "warn": 0, "fail": 0}},
            integrity={"status": "ready"},
            triage={"status": "ready"},
            handoff={"review_status": "ready"},
            uncertainty={"status": "ready"},
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "handoff-validation-receipt.md"
            json_path = Path(temp_dir) / "handoff-validation-receipt.json"

            write_outputs(report, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Handoff Validation Receipt", markdown)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
