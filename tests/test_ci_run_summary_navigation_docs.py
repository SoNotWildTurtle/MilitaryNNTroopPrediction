from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "ci_run_summary_navigation.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def test_ci_run_summary_navigation_guide_documents_required_fields():
    text = GUIDE.read_text(encoding="utf-8")

    required_phrases = [
        "GITHUB_STEP_SUMMARY",
        "Final head SHA",
        "Primary artifact name",
        "Machine-readable evidence",
        "Narrow local rerun",
        "Safe analytical scope",
        "Merge blocker reminder",
        "do not merge when required hosted validation is unavailable",
    ]

    for phrase in required_phrases:
        assert phrase in text


def test_ci_run_summary_navigation_guide_preserves_safe_scope_and_rollback():
    text = GUIDE.read_text(encoding="utf-8")

    assert "must not change prediction" in text
    assert "live OSINT" in text
    assert "operational behavior" in text
    assert "Rollback" in text
    assert "Removing the summary should not affect generated artifacts" in text


def test_ci_run_summary_navigation_has_changelog_entry():
    changelog = CHANGELOG.read_text(encoding="utf-8")

    assert "CI run summary navigation" in changelog
    assert "GITHUB_STEP_SUMMARY" in changelog
    assert "safe analytical scope" in changelog
