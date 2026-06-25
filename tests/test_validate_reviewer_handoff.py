import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = REPO_ROOT / "scripts" / "validate_reviewer_handoff.py"

spec = importlib.util.spec_from_file_location("validate_reviewer_handoff", VALIDATOR_PATH)
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


def valid_handoff():
    return {
        "artifact_dir": "ci_artifacts",
        "copyable_summary": "Bundle is ready for review.",
        "generated_at": "2026-06-25T14:00:00Z",
        "key_artifacts": [
            {
                "path": "release-health.md",
                "present": True,
                "purpose": "Summarizes readiness.",
                "size_bytes": 123,
                "sha256": "a" * 64,
            }
        ],
        "missing_expected": [],
        "missing_key_artifacts": [],
        "recommended_rerun": "make verify ARTIFACT_DIR=ci_artifacts",
        "release_status": "pass",
        "review_order": [
            {
                "step": 1,
                "action": "Open release health",
                "artifact": "release-health.md",
                "detail": "Confirm overall readiness.",
                "present": True,
                "status": "present",
            },
            {
                "step": 2,
                "action": "Open triage summary",
                "artifact": "triage-summary.md",
                "detail": "Check focused rerun guidance.",
                "present": True,
                "status": "present",
            },
        ],
        "review_status": "ready",
    }


class ReviewerHandoffValidatorTests(unittest.TestCase):
    def test_valid_handoff_has_no_errors(self):
        self.assertEqual(validator.validate_handoff(valid_handoff()), [])

    def test_missing_required_fields_are_reported(self):
        data = valid_handoff()
        del data["review_status"]
        del data["recommended_rerun"]

        errors = validator.validate_handoff(data)

        self.assertIn("missing required field: recommended_rerun", errors)
        self.assertIn("missing required field: review_status", errors)

    def test_invalid_review_status_is_reported(self):
        data = valid_handoff()
        data["review_status"] = "maybe"

        errors = validator.validate_handoff(data)

        self.assertTrue(any("review_status must be one of" in error for error in errors))

    def test_review_order_steps_must_increase(self):
        data = valid_handoff()
        data["review_order"][1]["step"] = 1

        errors = validator.validate_handoff(data)

        self.assertIn("review_order steps must be strictly increasing", errors)

    def test_cli_json_output_reports_success(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "reviewer-handoff.json"
            path.write_text(json.dumps(valid_handoff()), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(VALIDATOR_PATH), str(path), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["errors"], [])

    def test_cli_reports_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "reviewer-handoff.json"
            path.write_text("{not-json", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(VALIDATOR_PATH), str(path), "--json"],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["valid"])
        self.assertTrue(payload["errors"])


if __name__ == "__main__":
    unittest.main()
