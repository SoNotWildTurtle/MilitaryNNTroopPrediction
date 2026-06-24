"""Smoke tests for the first-run quickstart helper."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.cli import quickstart


class QuickstartSmokeTests(unittest.TestCase):
    """Verify quickstart stays safe to exercise in a minimal environment."""

    def test_requirements_profile_mapping(self) -> None:
        self.assertEqual(
            quickstart._requirements_for_profile("core"),
            Path("requirements-core.txt"),
        )
        self.assertEqual(
            quickstart._requirements_for_profile("optional"),
            Path("requirements-optional.txt"),
        )
        with self.assertRaises(ValueError):
            quickstart._requirements_for_profile("unknown")

    def test_quickstart_skip_install_bootstraps_env_and_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            with mock.patch.object(quickstart.doctor.settings, "DATA_DIR", Path(tmpdir)):
                exit_code = quickstart.run_quickstart(
                    quickstart.QuickstartOptions(
                        skip_install=True,
                        env_path=env_path,
                        skip_optional_checks=True,
                        skip_mongo=True,
                    )
                )

            self.assertEqual(exit_code, 0)
            self.assertTrue(env_path.exists())
            written = env_path.read_text(encoding="utf-8")
            self.assertIn("DATA_DIR=data", written)
            self.assertIn("MONGO_URI=mongodb://localhost:27017", written)

    def test_parser_defaults_to_safe_core_flow(self) -> None:
        args = quickstart.build_parser().parse_args([])
        self.assertEqual(args.install_profile, "core")
        self.assertFalse(args.check_optional)
        self.assertFalse(args.check_mongo)
        self.assertFalse(args.launch_api)


if __name__ == "__main__":
    unittest.main()
