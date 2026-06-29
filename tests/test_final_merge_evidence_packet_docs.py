"""Static regression coverage for final merge evidence packet guidance.

These tests keep the merge-readiness documentation aligned with the existing
safe, additive, non-operational review workflow without invoking external
services, model inference, or hosted CI APIs.
"""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "final_merge_evidence_packet.md"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"


class FinalMergeEvidencePacketDocsTests(unittest.TestCase):
    """Ensure final merge review guidance remains explicit and safe."""

    def test_packet_documents_required_final_evidence(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        required_terms = [
            "Target branch",
            "Final head SHA",
            "Required hosted checks",
            "Workflow run URLs",
            "Diagnostic artifacts",
            "Narrow rerun target",
            "Final diff review",
            "Review blockers",
            "Compatibility notes",
            "Safe analytical framing",
        ]
        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, content)

    def test_packet_keeps_unavailable_validation_as_blocker(self) -> None:
        content = DOC.read_text(encoding="utf-8")

        self.assertIn("Missing validation is a blocker", content)
        self.assertIn("blocked_ci", content)
        self.assertIn("unavailable", content)
        self.assertIn("must not be bypassed", content)

    def test_packet_preserves_safe_analytical_scope(self) -> None:
        content = DOC.read_text(encoding="utf-8").lower()

        self.assertIn("does not collect live osint", content)
        self.assertIn("operational targeting", content)
        self.assertIn("certainty", content)
        self.assertIn("predictive outputs remain framed as estimates", content)

    def test_packet_is_linked_from_readme_and_changelog(self) -> None:
        readme = README.read_text(encoding="utf-8")
        changelog = CHANGELOG.read_text(encoding="utf-8")

        self.assertIn("docs/final_merge_evidence_packet.md", readme)
        self.assertIn("final merge evidence packet", changelog.lower())


if __name__ == "__main__":
    unittest.main()
