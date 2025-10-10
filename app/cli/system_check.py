"""Command-line entry point for environment verification."""

from __future__ import annotations

import argparse
import sys
from typing import Iterable

from rich.console import Console
from rich.table import Table

from app.config import settings
from app.translation.translator import translate_text
from app.utils.system_check import CheckResult, results_to_json, run_installation_checks


def _(text: str) -> str:
    """Translate ``text`` into the configured UI language."""

    return translate_text(text, settings.UI_LANG)


def _render_table(console: Console, results: Iterable[CheckResult]) -> None:
    table = Table(_("Check"), _("Status"), _("Detail"))
    status_icons = {"pass": "✅", "warn": "⚠️", "fail": "❌"}
    for result in results:
        icon = status_icons.get(result.status, "•")
        table.add_row(result.name, f"{icon} {result.status}", result.detail)
    console.print(table)


def run_system_check() -> None:
    """Run installation checks and display the results."""

    parser = argparse.ArgumentParser(description=_("Verify environment prerequisites"))
    parser.add_argument(
        "--json",
        action="store_true",
        help=_("Output results as JSON"),
    )
    parser.add_argument(
        "--skip-optional",
        action="store_true",
        help=_("Skip optional dependency checks"),
    )
    args = parser.parse_args()

    results = run_installation_checks(include_optional=not args.skip_optional)

    if args.json:
        print(results_to_json(results))
    else:
        console = Console()
        _render_table(console, results)

    if any(res.status == "fail" for res in results):
        sys.exit(1)


__all__ = ["run_system_check"]
