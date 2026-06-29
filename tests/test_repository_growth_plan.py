from pathlib import Path


def test_repository_growth_plan_is_linked() -> None:
    root = Path(__file__).resolve().parents[1]
    plan = (root / "docs" / "repository_incremental_growth_plan.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert "Near-term goals" in plan
    assert "Medium-term goals" in plan
    assert "Long-term goals" in plan
    assert "docs/repository_incremental_growth_plan.md" in readme
