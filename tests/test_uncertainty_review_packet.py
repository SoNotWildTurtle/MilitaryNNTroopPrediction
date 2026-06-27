"""Tests for uncertainty review packet generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.uncertainty_review_packet import (
    build_uncertainty_review_packet,
    main,
    render_markdown,
    write_outputs,
)


class UncertaintyReviewPacketTests(unittest.TestCase):
    """Verify uncertainty handoff artifacts stay deterministic and safe."""

    def test_missing_artifacts_and_failed_health_block_packet(self) -> None:
        packet = build_uncertainty_review_packet(
            operator_plan={
                "status": "action_needed",
                "actions": [
                    {
                        "reason": "fail health check: core_deps",
                        "target": "make install-core",
                        "detail": "FastAPI missing",
                    }
                ],
            },
            release_health_payload=[{"name": "core_deps", "status": "fail", "detail": "FastAPI missing"}],
            manifest={"file_count": 3, "missing_expected": ["openapi.json"]},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        markdown = render_markdown(packet)
        evidence = [factor["evidence"] for factor in packet["uncertainty_factors"]]

        self.assertEqual(packet["status"], "blocked")
        self.assertEqual(packet["missing_artifact_count"], 1)
        self.assertIn("fail health check: core_deps", evidence)
        self.assertIn("missing artifact: openapi.json", evidence)
        self.assertIn("make install-core", packet["next_validation_steps"])
        self.assertIn("not live operational intelligence", markdown)
        self.assertIn("Do not use this packet for targeting", markdown)

    def test_ready_packet_uses_safe_review_steps(self) -> None:
        packet = build_uncertainty_review_packet(
            operator_plan={"status": "ready", "actions": []},
            release_health_payload={"status": "pass", "checks": [{"name": "python", "status": "pass"}]},
            manifest={"file_count": 42, "missing_expected": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        markdown = render_markdown(packet)

        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["uncertainty_factors"], [])
        self.assertIn("make verify", packet["next_validation_steps"])
        self.assertIn("No blocking uncertainty factors", markdown)
        self.assertIn("Frame every prediction", markdown)

    def test_warning_health_status_requires_review_without_blocking(self) -> None:
        packet = build_uncertainty_review_packet(
            operator_plan={"status": "needs_review", "actions": []},
            release_health_payload={"checks": [{"name": "optional_deps", "status": "warn", "detail": "Optional GIS missing"}]},
            manifest={"file_count": 8, "missing_expected": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )

        self.assertEqual(packet["status"], "review_warnings")
        self.assertEqual(packet["uncertainty_factors"][0]["severity"], "medium")
        self.assertEqual(packet["uncertainty_factors"][0]["recommended_validation"], "make verify")

    def test_writers_create_markdown_and_json(self) -> None:
        packet = build_uncertainty_review_packet(
            operator_plan={"status": "ready", "actions": []},
            release_health_payload=[],
            manifest={"file_count": 0, "missing_expected": []},
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        with TemporaryDirectory() as temp_dir:
            markdown_path = Path(temp_dir) / "uncertainty-review-packet.md"
            json_path = Path(temp_dir) / "uncertainty-review-packet.json"

            write_outputs(packet, markdown_path, json_path)

            markdown = markdown_path.read_text(encoding="utf-8")
            parsed = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("# Uncertainty Review Packet", markdown)
        self.assertEqual(parsed["status"], "ready")
        self.assertIn("privacy_and_safety_notes", parsed)

    def test_cli_reads_artifact_directory_defaults(self) -> None:
        with TemporaryDirectory() as temp_dir:
            artifact_dir = Path(temp_dir)
            (artifact_dir / "operator-next-steps.json").write_text(
                '{"status":"ready","actions":[]}',
                encoding="utf-8",
            )
            (artifact_dir / "release-health.json").write_text(
                '{"status":"pass","checks":[{"name":"python","status":"pass"}]}',
                encoding="utf-8",
            )
            (artifact_dir / "artifact-manifest.json").write_text(
                '{"file_count":2,"missing_expected":[]}',
                encoding="utf-8",
            )

            exit_code = main(["--artifact-dir", str(artifact_dir)])

            parsed = json.loads((artifact_dir / "uncertainty-review-packet.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(parsed["status"], "ready")


if __name__ == "__main__":
    unittest.main()
