"""Tests for the installation health check utilities."""

from __future__ import annotations

import json

from app.utils import system_check


def test_run_installation_checks_uses_overridden_modules(monkeypatch, tmp_path):
    """The health check should respect the module lists and data directory."""

    data_dir = tmp_path / "data"
    monkeypatch.setattr(system_check.settings, "DATA_DIR", data_dir)
    monkeypatch.setattr(system_check, "REQUIRED_MODULES", {"json": "JSON module"})
    monkeypatch.setattr(system_check, "OPTIONAL_MODULES", {"math": "Math helpers"})

    results = system_check.run_installation_checks()

    assert data_dir.exists()
    labels = {result.name for result in results}
    assert any("JSON module" in label for label in labels)
    assert any("Math helpers" in label for label in labels)


def test_results_to_json_round_trip(monkeypatch):
    """Serialised JSON should be parseable and contain status fields."""

    monkeypatch.setattr(
        system_check,
        "REQUIRED_MODULES",
        {"json": "JSON module"},
    )
    monkeypatch.setattr(system_check, "OPTIONAL_MODULES", {})
    results = system_check.run_installation_checks()
    payload = json.loads(system_check.results_to_json(results))
    assert isinstance(payload, list)
    assert all("status" in item for item in payload)
