"""Train an ORB bag-of-visual-words classifier."""
from __future__ import annotations
import argparse
from pathlib import Path
from rich.console import Console

from ..training.orb_bow_trainer import train_orb_bow
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG

def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_train_orb_bow() -> None:
    parser = argparse.ArgumentParser(description=_t("Train ORB bag-of-words model"))
    parser.add_argument("--images", nargs="+", required=True, help=_t("Image files"))
    parser.add_argument("--labels", nargs="+", required=True, help=_t("Class labels"))
    parser.add_argument("--out", required=True, help=_t("Output model path"))
    parser.add_argument("--clusters", type=int, default=64, help=_t("Vocabulary size"))
    args = parser.parse_args()

    model = train_orb_bow([Path(p) for p in args.images], args.labels, Path(args.out), clusters=args.clusters)
    console.print(_t("Saved model to {p}").format(p=model))


if __name__ == "__main__":
    run_train_orb_bow()
