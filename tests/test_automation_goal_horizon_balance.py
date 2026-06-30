from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "automation_goal_horizon_balance.md"


def test_goal_horizon_balance_guide_defines_three_horizons() -> None:
    guide = GUIDE.read_text(encoding="utf-8")

    assert "Near-term" in guide
    assert "Medium-term" in guide
    assert "Long-term" in guide
    assert "Horizon model" in guide


def test_goal_horizon_balance_guide_keeps_runs_mergeable_and_evidence_based() -> None:
    guide = GUIDE.read_text(encoding="utf-8")

    assert "smallest repair" in guide
    assert "failing validation" in guide
    assert "reviewed in one pull request" in guide
    assert "Exact local and hosted validation evidence" in guide
    assert "safe analytical framing" in guide


def test_goal_horizon_balance_guide_records_next_run_follow_up() -> None:
    guide = GUIDE.read_text(encoding="utf-8")

    assert "concrete next-step candidate" in guide
    assert "next automation run" in guide
