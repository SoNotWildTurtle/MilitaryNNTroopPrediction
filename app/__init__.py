"""Application package exposing common helpers with lazy imports.

Keeping package-level imports lazy makes lightweight tools such as
``python -m app.cli.doctor`` usable before optional ML, mapping, or dashboard
libraries are installed. This improves first-run setup diagnostics and CI smoke
checks without changing the public helper names exported by the package.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "run_dashboard",
    "run_config_setup",
    "self_reinforce",
    "log_movements",
    "analyze_unit",
    "score_clusters",
    "encode_state",
]


def __getattr__(name: str) -> Any:
    """Load heavier helpers only when callers actually request them."""

    if name in {"run_dashboard", "run_config_setup", "self_reinforce"}:
        from . import cli

        return getattr(cli, name)
    if name == "log_movements":
        from .movement_logger import log_movements

        return log_movements
    if name in {"analyze_unit", "score_clusters", "encode_state"}:
        from . import analysis

        return getattr(analysis, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
