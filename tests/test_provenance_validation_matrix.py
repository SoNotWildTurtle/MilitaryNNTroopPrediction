"""Tests for provenance validation matrix generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.provenance_validation_matrix import (
    SCHEMA_VERSION,
    build_provenance_validation_matrix,
    render_markdown,
    write_outputs,
)


class ProvenanceValidationMatrixTests(unittest.TestCase):
    """Verify deterministic cross-artifact provenance validation behavior."""

    def _ready_manifest(self) -> dict[str, object]:
        paths = [
            "artifact-manifest.json",
            "artifact-provenance-ledger.json",
            "evidence-checklist.json",
            "handoff-integrity-report.json",
            "handoff-validation-receipt.json",
            "reviewer-handoff.json",
            "uncertainty-review-packet.json",
        ]
        return {
            "status": "ready",
            "file_count": len(paths),
            "total_size_bytes": 700,
            "missing_expected": [],
            "files": [
                {"path": path, "sha256": str(index) * 64, "size_bytes": 100 + index}
                for index, path in enumerate(paths, start=1)
            ],
        }

    def _ready_ledger(self) -> dict[str, object]:
        return {
            "status": "ready",
            "entries": [
                {
                    "path": "artifact-manifest.json",
                    "category": "bundle_integrity",
                    "operational_claim": True,
                    "rationale": "Generated bundle-integrity artifact.",
                },
                {
                    "path": "artifact-provenance-ledger.json",
                    "category": "bundle_integrity",
                    "operational_claim": True,
                    "rationale": "Generated provenance labels.",
                },
                {
                    "path": "evidence-checklist.json",
                    "category": "handoff",
                    "operational_claim": True,
                    "rationale": "Generated evidence gate summary.",
                },
                {
                    "path": "handoff-integrity-report.json",
                    "category": "handoff",
                    "operational_claim": True,
                    "rationale": "Generated cross-artifact integrity report.",
                },
                {
                    "path": "handoff-validation-receipt.json",
                    "category": "handoff",
                    "operational_claim": True,
                    "rationale": "Generated final validation receipt.",
                },
                {
                    "path": "reviewer-handoff.json",
                    "category": "handoff",
                    "operational_claim": True,
                    "rationale": "Generated reviewer handoff.",
                },
                {
                    "path": "uncertainty-review-packet.json",
                    "category": "handoff",
                    "operational_claim": True,
                    "rationale": "Generated uncertainty review packet.",
                },
            ],
        }

    def test_ready_matrix_links_required_signals(self) -> None:
        matrix = build_provenance_validation_matrix(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest=self._ready_manifest(),
            ledger=self._ready_ledger(),
            evidence={"status": "ready"},
            receipt={"status": "ready"},
        )
        markdown = render_markdown(matrix)

        self.assertEqual(matrix["schema_version"], SCHEMA_VERSION)
        self.assertEqual(matrix["status"], "ready")
        self.assertEqual(matrix["ready_signal_count"], matrix["required_signal_count"])
        self.assertEqual(matrix["blockers"], [])
        self.assertIn("# Provenance Validation Matrix", markdown)
        self.assertIn(f"Schema version: `{SCHEMA_VERSION}`", markdown)
        self.assertIn("without making operational targeting claims", matrix["safe_scope"])

    def test_schema_document_covers_exported_contract_fields(self) -> None:
        matrix = build_provenance_validation_matrix(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest=self._ready_manifest(),
            ledger=self._ready_ledger(),
            evidence={"status": "ready"},
            receipt={"status": "ready"},
        )
        schema_doc = Path("docs/provenance_validation_matrix_schema.md").read_text(encoding="utf-8")

        for field in (
            "schema_version",
            "generated_at",
            "artifact_dir",
            "status",
            "source_statuses",
            "required_signal_count",
            "ready_signal_count",
            "blockers",
            "warnings",
            "next_action",
            "rows",
            "safe_scope",
        ):
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", schema_doc)
                self.assertIn(field, matrix)

        for row_field in (
            "gate",
            "artifact",
            "status",
            "category",
            "operational_claim",
            "sha256",
            "size_bytes",
            "requirement",
            "rationale",
        ):
            with self.subTest(row_field=row_field):
                self.assertIn(f"`{row_field}`", schema_doc)
                self.assertIn(row_field, matrix["rows"][0])

        self.assertIn("not a live-data validation", schema_doc)
        self.assertIn("not an operational targeting artifact", schema_doc)
        self.assertIn("do not remove or rename", schema_doc)

    def test_missing_required_signal_blocks_matrix(self) -> None:
        manifest = self._ready_manifest()
        manifest["files"] = [
            entry for entry in manifest["files"] if entry["path"] != "handoff-validation-receipt.json"
        ]
        matrix = build_provenance_validation_matrix(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest=manifest,
            ledger=self._ready_ledger(),
            evidence={"status": "ready"},
            receipt={"status": "ready"},
        )

        self.assertEqual(matrix["status"], "blocked")
        self.assertTrue(any("handoff-validation-receipt.json" in blocker for blocker in matrix["blockers"]))

    def test_warning_source_requires_review_without_row_blocker(self) -> None:
        matrix = build_provenance_validation_matrix(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest=self._ready_manifest(),
            ledger=self._ready_ledger(),
            evidence={"status": "needs_review"},
            receipt={"status": "ready"},
        )

        self.assertEqual(matrix["status"], "needs_review")
        self.assertEqual(matrix["blockers"], [])
        self.assertTrue(any("evidence_checklist" in warning for warning in matrix["warnings"]))

    def test_writers_create_markdown_and_json(self) -> None:
        matrix = build_provenance_validation_matrix(
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            manifest=self._ready_manifest(),
            ledger=self._ready_ledger(),
            evidence={"status": "ready"},
            receipt={"status": "ready"},
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "provenance-validation-matrix.md"
            json_path = Path(temp_dir) / "provenance-validation-matrix.json"

            write_outputs(matrix, markdown_path, json_path)
            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Provenance Validation Matrix", markdown)
        self.assertEqual(parsed["schema_version"], SCHEMA_VERSION)
        self.assertEqual(parsed["generated_at"], "2026-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
