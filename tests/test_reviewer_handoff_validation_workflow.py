"""Regression tests for reviewer handoff validation workflow wiring."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
CI_REPORT = ROOT / "scripts" / "ci_report.sh"
SMOKE_TEST = ROOT / "scripts" / "test.sh"
COMMON_TASKS = ROOT / "docs" / "common_tasks.md"
CI_TROUBLESHOOTING = ROOT / "docs" / "ci_troubleshooting.md"


def test_make_verify_runs_handoff_contract_validation():
    text = MAKEFILE.read_text(encoding="utf-8")

    assert "validate-handoff" in text
    assert "verify: doctor test ci-report validate-handoff" in text
    assert "scripts/validate_reviewer_handoff.py $(ARTIFACT_DIR)/reviewer-handoff.json --json" in text
    assert "make validate-handoff" in text


def test_ci_report_publishes_validation_artifacts():
    text = CI_REPORT.read_text(encoding="utf-8")

    assert "reviewer-handoff-validation.txt" in text
    assert "reviewer-handoff-validation.json" in text
    assert "scripts/validate_reviewer_handoff.py" in text
    assert "${ARTIFACT_DIR}/reviewer-handoff.json" in text
    assert "--json > \"${ARTIFACT_DIR}/reviewer-handoff-validation.json\"" in text


def test_smoke_script_validates_generated_handoff():
    text = SMOKE_TEST.read_text(encoding="utf-8")

    assert "militarynntroopprediction-reviewer-handoff.json" in text
    assert "scripts/validate_reviewer_handoff.py /tmp/militarynntroopprediction-reviewer-handoff.json --json" in text


def test_docs_explain_handoff_validation_command():
    common_tasks = COMMON_TASKS.read_text(encoding="utf-8")
    ci_troubleshooting = CI_TROUBLESHOOTING.read_text(encoding="utf-8")

    for text in [common_tasks, ci_troubleshooting]:
        assert "make validate-handoff" in text
        assert "reviewer-handoff-validation.json" in text
        assert "scripts/validate_reviewer_handoff.py" in text
