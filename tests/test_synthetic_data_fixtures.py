"""Tests for safe synthetic data fixture export."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cli.synthetic_data_fixtures import build_fixture_bundle, write_fixture_bundle


class SyntheticDataFixtureTests(unittest.TestCase):
    """Verify fixture generation stays deterministic, safe, and client-friendly."""

    def test_fixture_bundle_uses_shared_synthetic_examples(self) -> None:
        bundle = build_fixture_bundle()

        metadata = bundle["metadata"]
        self.assertEqual(metadata["schema"], "militarynntroopprediction.synthetic_fixtures.v1")
        self.assertEqual(metadata["generated_from"], "app.api.examples")
        self.assertIn("Synthetic placeholders only", metadata["safe_scope"])
        self.assertEqual(metadata["record_counts"]["detections"], len(bundle["detections"]))
        self.assertEqual(metadata["record_counts"]["predictions"], len(bundle["predictions"]))
        self.assertEqual(bundle["detections"][0]["source"], "synthetic_fixture")
        self.assertIn("current_point", bundle["predictions"][0])
        self.assertIn("next_point", bundle["predictions"][0])

    def test_writer_exports_jsonl_csv_markdown_and_summary(self) -> None:
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "fixtures"
            written = write_fixture_bundle(build_fixture_bundle(), output_dir)

            bundle_summary = json.loads(Path(written["bundle_json"]).read_text(encoding="utf-8"))
            detections_jsonl = Path(written["detections_jsonl"]).read_text(encoding="utf-8").strip().splitlines()
            predictions_jsonl = Path(written["predictions_jsonl"]).read_text(encoding="utf-8").strip().splitlines()
            markdown = Path(written["summary_markdown"]).read_text(encoding="utf-8")
            with Path(written["detections_csv"]).open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

        self.assertEqual(bundle_summary["metadata"]["schema"], "militarynntroopprediction.synthetic_fixtures.v1")
        self.assertEqual(len(detections_jsonl), 1)
        self.assertEqual(len(predictions_jsonl), 1)
        self.assertEqual(rows[0]["source"], "synthetic_fixture")
        self.assertIn("Synthetic Data Fixtures", markdown)
        self.assertIn("no live OSINT", markdown)


if __name__ == "__main__":
    unittest.main()
