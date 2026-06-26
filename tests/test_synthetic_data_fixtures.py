from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from app.cli.synthetic_data_fixtures import build_fixture_bundle, write_fixture_bundle


class SyntheticDataFixturesTests(unittest.TestCase):
    def test_build_fixture_bundle_is_safe_and_deterministic(self) -> None:
        bundle = build_fixture_bundle()

        self.assertEqual(bundle["metadata"]["area"], "training-range-alpha")
        self.assertEqual(bundle["metadata"]["record_counts"]["detections"], len(bundle["detections"]))
        self.assertEqual(bundle["metadata"]["record_counts"]["predictions"], len(bundle["predictions"]))
        self.assertIn("Synthetic placeholders only", bundle["metadata"]["safe_scope"])
        self.assertEqual(bundle["detections"][0]["source"], "synthetic_fixture")
        self.assertEqual(bundle["predictions"][0]["source"], "synthetic_fixture")
        self.assertIn("current_point", bundle["predictions"][0])
        self.assertIn("next_point", bundle["predictions"][0])

    def test_write_fixture_bundle_outputs_jsonl_csv_and_summary(self) -> None:
        bundle = build_fixture_bundle()
        with tempfile.TemporaryDirectory() as tmpdir:
            written = write_fixture_bundle(bundle, Path(tmpdir))

            for path in written.values():
                self.assertTrue(Path(path).exists(), path)

            detection_lines = Path(written["detections_jsonl"]).read_text(encoding="utf-8").splitlines()
            prediction_lines = Path(written["predictions_jsonl"]).read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(detection_lines), 1)
            self.assertEqual(len(prediction_lines), 1)
            self.assertEqual(json.loads(detection_lines[0])["id"], "sample-detection-001")
            self.assertEqual(json.loads(prediction_lines[0])["id"], "sample-prediction-001")

            with Path(written["detections_csv"]).open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["id"], "sample-detection-001")
            self.assertEqual(rows[0]["source"], "synthetic_fixture")

            summary = Path(written["summary_markdown"]).read_text(encoding="utf-8")
            self.assertIn("# Synthetic Data Fixtures", summary)
            self.assertIn("no live OSINT", summary)


if __name__ == "__main__":
    unittest.main()
