"""Lightweight regression tests for exception-register workflow wiring."""

from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ExceptionRegisterWiringTests(unittest.TestCase):
    """Keep the exception register available in normal review workflows."""

    def test_makefile_exposes_exception_register_target(self) -> None:
        content = (ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertRegex(content, r"(?m)^\.PHONY: .*\boperator-exception-register\b")
        self.assertIn("make operator-exception-register", content)
        self.assertRegex(content, r"(?m)^operator-exception-register:")
        self.assertIn("app.cli.operator_exception_register", content)
        self.assertIn("$(ARTIFACT_DIR)/operator-exception-register.md", content)
        self.assertIn("$(ARTIFACT_DIR)/operator-exception-register.json", content)
        self.assertIn("$(ARTIFACT_DIR)/operator-exception-register.txt", content)

    def test_ci_report_includes_exception_register_outputs(self) -> None:
        content = (ROOT / "scripts" / "ci_report.sh").read_text(encoding="utf-8")

        self.assertIn("app.cli.operator_exception_register --help", content)
        self.assertIn("operator-exception-register-help.txt", content)
        self.assertIn("operator-exception-register.md", content)
        self.assertIn("operator-exception-register.json", content)
        self.assertIn("operator-exception-register.txt", content)

    def test_workflow_smoke_checks_exception_register_cli(self) -> None:
        content = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

        self.assertIn("Export operator exception register smoke artifact", content)
        self.assertIn("app.cli.operator_exception_register", content)
        self.assertIn("militarynntroopprediction-operator-exception-register.json", content)


if __name__ == "__main__":
    unittest.main()
