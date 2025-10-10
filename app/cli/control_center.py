"""Launch the Textual control centre for operators."""

from __future__ import annotations

import argparse
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt

from ..config import settings
from ..translation import translate_text
from ..gui.control_center import run_control_center

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate interface strings when a different UI language is configured."""

    return translate_text(text, target_lang=_LANG)


def run_control_center_cli(area: Optional[str] = None) -> None:
    """Wrapper that prompts for an area before launching the control centre."""

    chosen = area
    if chosen is None:
        response = Prompt.ask(_t("Area name (leave blank for global view)"), default="")
        chosen = response.strip() or None
    try:
        run_control_center(chosen)
    except RuntimeError as exc:
        console.print(str(exc), style="red")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=_t("Launch the Textual control centre"), add_help=True
    )
    parser.add_argument("--area", type=str, help=_t("Area name"))
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_control_center_cli(args.area)
