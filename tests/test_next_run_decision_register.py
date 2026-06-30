from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTER = ROOT / "docs" / "next_run_decision_register.md"


def test_next_run_decision_register_prioritizes_blocker_repair_before_expansion() -> None:
    register = REGISTER.read_text(encoding="utf-8")

    assert "Protect the default branch first" in register
    assert "Repair blockers before expansion" in register
    assert "smallest reproducible repair" in register
    assert "required hosted checks" in register


def test_next_run_decision_register_discourages_duplicate_process_only_work() -> None:
    register = REGISTER.read_text(encoding="utf-8")

    assert "Prefer functional unlocks over more process text" in register
    assert "standalone guide" in register
    assert "Do not add another process guide" in register
    assert "executable evidence" in register


def test_next_run_decision_register_requires_handoff_and_safety_fields() -> None:
    register = REGISTER.read_text(encoding="utf-8")

    assert "Selected candidate and why it beat the alternatives" in register
    assert "Exact local validation commands and hosted checks reviewed" in register
    assert "One next concrete candidate" in register
    assert "Rollback path and safe analytical framing notes" in register
