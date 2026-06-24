"""Tests for synthetic API response examples and export helpers."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.api.examples import sample_detection_records, sample_payload_bundle, sample_prediction_records
from app.cli.export_api_examples import write_json, write_markdown


class ApiExampleTests(unittest.TestCase):
    """Verify example payloads stay JSON-safe and useful for client builders."""

    def test_sample_records_are_public_and_json_safe(self) -> None:
        detection = sample_detection_records()[0]
        prediction = sample_prediction_records()[0]

        self.assertNotIn("_id", detection)
        self.assertEqual(detection["id"], "sample-detection-001")
        self.assertEqual(detection["bbox"], [10, 20, 30, 40])
        self.assertNotIn("_id", prediction)
        self.assertEqual(prediction["id"], "sample-prediction-001")
        json.dumps({"detection": detection, "prediction": prediction})

    def test_payload_bundle_covers_public_api_examples(self) -> None:
        bundle = sample_payload_bundle()
        endpoints = bundle["endpoints"]

        self.assertIn("GET /healthz", endpoints)
        self.assertIn("GET /readyz", endpoints)
        self.assertIn("GET /detections/{area}?limit=10", endpoints)
        self.assertIn("GET /predictions/{area}?limit=10", endpoints)
        self.assertIn("POST /predict/{area}", endpoints)
        self.assertEqual(endpoints["GET /healthz"]["status"], "ok")

    def test_export_writers_create_json_and_markdown_files(self) -> None:
        bundle = sample_payload_bundle()

        with TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "examples.json"
            markdown_path = Path(temp_dir) / "examples.md"

            write_json(bundle, json_path)
            write_markdown(bundle, markdown_path)

            parsed = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")

        self.assertEqual(parsed["metadata"]["area"], "training-range-alpha")
        self.assertIn("# API response examples", markdown)
        self.assertIn("GET /detections/{area}?limit=10", markdown)


if __name__ == "__main__":
    unittest.main()
