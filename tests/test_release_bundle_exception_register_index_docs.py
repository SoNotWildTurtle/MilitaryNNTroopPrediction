"""Regression tests for release bundle exception-register index guidance."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "release_bundle_exception_register_index.md"


class ReleaseBundleExceptionRegisterIndexDocsTests(unittest.TestCase):
    """Keep the reviewer-facing index contract discoverable and safe-scoped."""

    def test_documentation_lists_exception_register_artifacts(self) -> None:
        content = DOC_PATH.read_text(encoding="utf-8")

        self.assertIn("operator-exception-register.md", content)
        self.assertIn("operator-exception-register.json", content)
        self.assertIn("operator-exception-register.txt", content)
        self.assertIn("Prioritized operator exception queue", content)
        self.assertIn("Machine-readable operator exception queue", content)
        self.assertIn("Copyable operator exception summary", content)

    def test_documentation_keeps_exception_register_in_safe_review_scope(self) -> None:
        content = DOC_PATH.read_text(encoding="utf-8")

        self.assertIn("not an operational prediction", content)
        self.assertIn("not be described as live intelligence", content)
        self.assertIn("lawful defensive, analytical, and reproducibility workflows", content)
        self.assertIn("handoff metadata", content)

    def test_documentation_records_future_code_update_target(self) -> None:
        content = DOC_PATH.read_text(encoding="utf-8")

        self.assertIn("app/cli/release_bundle_index.py", content)
        self.assertIn("HIGHLIGHTED_ARTIFACTS", content)
        self.assertIn("REVIEW_ORDER_STEPS", content)
        self.assertIn("before `operator-next-steps.md`", content)


if __name__ == "__main__":
    unittest.main()
