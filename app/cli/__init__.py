"""Command-line utilities with lightweight lazy exports."""

from __future__ import annotations

from typing import Any

__all__ = ["run_dashboard", "run_config_setup", "run_quickstart", "self_reinforce"]


def __getattr__(name: str) -> Any:
    """Import CLI entry points only when they are requested.

    This lets ``python -m app.cli.doctor`` run in minimal environments where
    optional dashboard or ML dependencies may not be installed yet.
    """

    if name == "run_dashboard":
        from .dashboard import run_dashboard

        return run_dashboard
    if name == "run_config_setup":
        from .configure import run_config_setup

        return run_config_setup
    if name == "run_quickstart":
        from .quickstart import run_quickstart

        return run_quickstart
    if name == "self_reinforce":
        from .self_reinforce import self_reinforce

        return self_reinforce
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
