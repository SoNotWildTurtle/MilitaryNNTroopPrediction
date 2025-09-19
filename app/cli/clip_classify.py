"""Classify an image with CLIP zero-shot model."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from rich.console import Console
from rich.table import Table

from ..detection.clip_identifier import classify_clip
from ..translation import translate_text

console = Console()


def run_clip_classify() -> None:
    parser = argparse.ArgumentParser(description="CLIP zero-shot classifier")
    parser.add_argument("image", help="Image file")
    parser.add_argument("labels", nargs="+", help="Candidate labels")
    args = parser.parse_args()

    lang = os.getenv("UI_LANG", "en")
    results = classify_clip(Path(args.image), args.labels)

    table = Table(title=translate_text("CLIP classification", lang))
    table.add_column(translate_text("Label", lang))
    table.add_column(translate_text("Score", lang), justify="right")
    for lbl, score in results:
        table.add_row(lbl, f"{score:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_clip_classify()
