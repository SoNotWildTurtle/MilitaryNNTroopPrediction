"""Tests for the Textual control centre data gathering helpers."""

from __future__ import annotations

from app.gui.control_center import gather_control_snapshot


def test_gather_control_snapshot_handles_failures(monkeypatch):
    """Even if dependencies fail, the snapshot should contain defaults."""

    def fake_recs(area, lookback_hours=24):  # pragma: no cover - patched behaviour
        raise RuntimeError("boom")

    def fake_speed(object_type, hours=24):  # pragma: no cover - patched behaviour
        if object_type == "armor":
            raise RuntimeError("no armor data")
        return {
            "object_type": object_type,
            "rows": [
                {
                    "unit_id": f"{object_type}-1",
                    "avg_speed_kmh": 12.5,
                    "max_speed_kmh": 18.0,
                    "distance_km": 6.0,
                    "samples": 3,
                }
            ],
            "overall_avg_speed_kmh": 12.5,
            "total_units": 1,
        }

    monkeypatch.setattr(
        "app.gui.control_center.gather_next_gen_recommendations",
        fake_recs,
    )
    monkeypatch.setattr(
        "app.gui.control_center.object_speed_summary",
        fake_speed,
    )

    snapshot = gather_control_snapshot("kyiv")
    assert snapshot.area == "kyiv"
    # Recommendations should fall back to an empty structure when unavailable.
    assert snapshot.recommendations["priority"] == []
    assert any("Failed to gather" in err for err in snapshot.errors)

    assert len(snapshot.speed_summaries) == 3
    armor_summary = next(item for item in snapshot.speed_summaries if item["object_type"] == "armor")
    assert "error" in armor_summary and armor_summary["error"]
    drone_summary = next(item for item in snapshot.speed_summaries if item["object_type"] == "drone")
    assert drone_summary["rows"][0]["unit_id"] == "drone-1"
    assert snapshot.speed_summaries[1]["overall_avg_speed_kmh"] == 12.5
