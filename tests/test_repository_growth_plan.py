from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "docs" / "repository_incremental_growth_plan.md"
CHANGELOG = ROOT / "CHANGELOG.md"


def test_repository_growth_plan_has_goal_hierarchy() -> None:
    plan = PLAN.read_text(encoding="utf-8")

    assert "Near-term goals" in plan
    assert "Medium-term goals" in plan
    assert "Long-term goals" in plan
    assert "Follow-up capture" in plan


def test_repository_growth_plan_preserves_reviewable_additive_scope() -> None:
    plan = PLAN.read_text(encoding="utf-8")

    assert "meaningful, mergeable, testable" in plan
    assert "without replacing working components" in plan
    assert "Avoid changes that" in plan
    assert "Hide failing checks" in plan


def test_repository_growth_plan_changelog_entry_is_present() -> None:
    changelog = CHANGELOG.read_text(encoding="utf-8")

    assert "docs/repository_incremental_growth_plan.md" in changelog
    assert "durable near-term, medium-term, and long-term repository goals" in changelog
