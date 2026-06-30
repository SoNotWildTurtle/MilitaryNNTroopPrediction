"""Tests for artifact provenance ledger generation."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.artifact_provenance_ledger import (
    build_provenance_ledger,
    render_markdown,
    write_json,
    write_markdown,
)


class ArtifactProvenanceLedgerTests(unittest.TestCase):
    """Verify diagnostic artifact provenance stays explicit and safe."""

    def test_ledger_classifies_synthetic_and_review_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "artifact-manifest.json").write_text(
                json.dumps(
                    {
                        "missing_expected": [],
                        "files": [
                            {
                                "path": "synthetic-fixtures/synthetic-detections.jsonl",
                                "size_bytes": 10,
                                "sha256": "a" * 64,
                                "description": "fixture",
                            },
                            {
                                "path": "reviewer-handoff.md",
                                "size_bytes": 20,
                                "sha256": "b" * 64,
                                "description": "handoff",
                            },
                            {
                                "path": "release-health.json",
                                "size_bytes": 30,
                                "sha256": "c" * 64,
                                "description": "health",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            ledger = build_provenance_ledger(artifact_dir)
            markdown = render_markdown(ledger)

        self.assertEqual(ledger["status"], "ready")
        self.assertEqual(ledger["file_count"], 3)
        self.assertEqual(ledger["category_counts"]["synthetic_fixture"], 1)
        self.assertEqual(ledger["category_counts"]["handoff"], 1)
        self.assertEqual(ledger["category_counts"]["release_gate"], 1)
        self.assertEqual(ledger["non_operational_artifacts"], ["synthetic-fixtures/synthetic-detections.jsonl"])
        synthetic_entry = next(
            entry for entry in ledger["entries"] if entry["path"] == "synthetic-fixtures/synthetic-detections.jsonl"
        )
        self.assertFalse(synthetic_entry["operational_claim"])
        self.assertIn("Artifact provenance ledger", markdown)
        self.assertIn("synthetic_fixture", markdown)
        self.assertIn("not operational evidence", markdown)

    def test_ledger_classifies_implementation_acceptance_evidence(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "artifact-manifest.json").write_text(
                json.dumps(
                    {
                        "missing_expected": [],
                        "files": [
                            {
                                "path": "implementation-acceptance-checklist.json",
                                "size_bytes": 64,
                                "sha256": "d" * 64,
                                "description": "acceptance gates",
                            },
                            {
                                "path": "implementation-acceptance-handoff.md",
                                "size_bytes": 96,
                                "sha256": "e" * 64,
                                "description": "acceptance handoff",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            ledger = build_provenance_ledger(artifact_dir)
            markdown = render_markdown(ledger)

        self.assertEqual(ledger["category_counts"]["implementation_acceptance_evidence"], 2)
        self.assertNotIn("implementation-acceptance-handoff.md", ledger["non_operational_artifacts"])
        handoff_entry = next(
            entry for entry in ledger["entries"] if entry["path"] == "implementation-acceptance-handoff.md"
        )
        self.assertTrue(handoff_entry["operational_claim"])
        self.assertIn("implementation_acceptance_evidence", markdown)
        self.assertIn("reviewer merge gates", markdown)

    def test_ledger_flags_missing_manifest_safely(self) -> None:
        with TemporaryDirectory() as temp_dir:
            ledger = build_provenance_ledger(Path(temp_dir))
            markdown = render_markdown(ledger)

        self.assertEqual(ledger["status"], "missing_manifest")
        self.assertEqual(ledger["file_count"], 0)
        self.assertEqual(ledger["category_counts"], {})
        self.assertIn("MISSING_MANIFEST", markdown)
        self.assertIn("Classifies local diagnostic artifacts only", markdown)

    def test_ledger_reports_missing_expected_artifacts(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "custom-manifest.json").write_text(
                json.dumps(
                    {
                        "missing_expected": ["openapi.json"],
                        "files": [
                            {
                                "path": "artifact-gap-report.md",
                                "size_bytes": 15,
                                "sha256": "d" * 64,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            ledger = build_provenance_ledger(artifact_dir, manifest_path=artifact_dir / "custom-manifest.json")
            markdown = render_markdown(ledger)

        self.assertEqual(ledger["status"], "needs_review")
        self.assertEqual(ledger["missing_expected"], ["openapi.json"])
        self.assertIn("Missing expected artifacts", markdown)
        self.assertIn("openapi.json", markdown)

    def test_writers_create_parent_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "nested"
            markdown_path = output_dir / "artifact-provenance-ledger.md"
            json_path = output_dir / "artifact-provenance-ledger.json"
            ledger = {
                "generated_at": "now",
                "artifact_dir": "ci_artifacts",
                "manifest_path": "ci_artifacts/artifact-manifest.json",
                "status": "ready",
                "file_count": 0,
                "category_counts": {},
                "missing_expected": [],
                "non_operational_artifacts": [],
                "entries": [],
                "safe_scope": "safe",
                "copyable_summary": "ready",
            }

            write_markdown("# Ledger\n", markdown_path)
            write_json(ledger, json_path)

            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "# Ledger\n")
            self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["status"], "ready")


if __name__ == "__main__":
    unittest.main()
