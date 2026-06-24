"""Smoke tests for the setup doctor CLI.

These tests intentionally avoid optional ML/GIS/dashboard dependencies so the
project can validate first-run diagnostics in a minimal CI environment.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.cli import doctor


class DoctorSmokeTests(unittest.TestCase):
    """Verify lightweight setup diagnostics stay usable and structured."""

    def test_core_checks_can_run_without_optional_or_mongo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(doctor.settings, "DATA_DIR", Path(tmpdir)):
                results = doctor.run_checks(include_optional=False, check_mongo=False)

        names = {result.name for result in results}
        self.assertIn("python", names)
        self.assertIn("data_dir", names)
        self.assertIn("sentinel_env", names)
        self.assertNotIn("mongo_socket", names)
        self.assertFalse(any(name.startswith("import:tensorflow") for name in names))

    def test_json_output_is_machine_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(doctor.settings, "DATA_DIR", Path(tmpdir)):
                with mock.patch("builtins.print") as mocked_print:
                    exit_code = doctor.main(["--json", "--skip-optional", "--skip-mongo"])

        self.assertIn(exit_code, {0, 1})
        printed = "\n".join(str(call.args[0]) for call in mocked_print.call_args_list)
        payload = json.loads(printed)
        self.assertIsInstance(payload, list)
        self.assertTrue(all({"name", "status", "detail", "remediation"} <= set(item) for item in payload))


if __name__ == "__main__":
    unittest.main()
