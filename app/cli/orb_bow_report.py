"""Display ORB bag-of-visual-words classification probabilities."""
from __future__ import annotations
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table

from ..analysis.orb_bow_match import match_orb_bow
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG

def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_orb_bow_report() -> None:
    parser = argparse.ArgumentParser(description=_t("ORB bag-of-words report"))
    parser.add_argument("--image", required=True, help=_t("Image file"))
    parser.add_argument("--model", required=True, help=_t("Trained model"))
    args = parser.parse_args()

    results = match_orb_bow(Path(args.image), Path(args.model))
    if not results:
        console.print(_t("No features found"), style="yellow")
        return
    table = Table(title=_t("ORB bag-of-words matches"))
    table.add_column(_t("Class"))
    table.add_column(_t("Probability"), justify="right")
    for cls, prob in results:
        table.add_row(cls, f"{prob:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_orb_bow_report()
