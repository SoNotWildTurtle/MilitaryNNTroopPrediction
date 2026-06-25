"""Regression tests for reviewer handoff contract documentation."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from app.cli.reviewer_handoff import build_handoff

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "docs" / "reviewer_handoff_schema.json"
CONTRACT_PATH = ROOT / "docs" / "reviewer_handoff_contract.md"


class ReviewerHandoffContractTests(unittest.TestCase):
    """Keep the downstream handoff contract discoverable and aligned with output."""

    def test_schema_is_valid_json_with_expected_required_fields(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        self.assertEqual(schema["title"], "MilitaryNNTroopPrediction reviewer handoff")
        self.assertEqual(schema["type"], "object")
        self.assertTrue(schema["additionalProperties"])

        required = set(schema["required"])
        for field in [
            "artifact_dir",
            "copyable_summary",
            "generated_at",
            "key_artifacts",
            "missing_expected",
            "missing_key_artifacts",
            "recommended_rerun",
            "release_status",
            "review_order",
            "review_status",
        ]:
            self.assertIn(field, required)
            self.assertIn(field, schema["properties"])

    def test_schema_required_fields_match_generated_handoff(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        handoff = build_handoff(ROOT / "definitely-missing-artifacts")

        for field in schema["required"]:
            self.assertIn(field, handoff)

        self.assertIn(handoff["review_status"], schema["properties"]["review_status"]["enum"])
        self.assertGreaterEqual(len(handoff["review_order"]), 1)
        for step in handoff["review_order"]:
            self.assertIn(step["status"], schema["properties"]["review_order"]["items"]["properties"]["status"]["enum"])

    def test_contract_document_explains_consumer_routing(self) -> None:
        text = CONTRACT_PATH.read_text(encoding="utf-8")

        self.assertIn("docs/reviewer_handoff_schema.json", text)
        self.assertIn("review_status", text)
        self.assertIn("recommended_rerun", text)
        self.assertIn("ready", text)
        self.assertIn("review_warnings", text)
        self.assertIn("needs_attention", text)
        self.assertIn("needs_review", text)
        self.assertIn("Compatibility rules", text)
        self.assertIn("defensive validation", text)


if __name__ == "__main__":
    unittest.main()
