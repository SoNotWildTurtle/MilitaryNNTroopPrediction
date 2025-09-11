"""CLI to identify entities by fusing image and sensor point clouds."""
from __future__ import annotations

import argparse

from rich.console import Console
from rich.table import Table

from ..analysis import rank_fused_gaussian
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_fused_gaussian_report() -> None:
    parser = argparse.ArgumentParser(description=_t("Match fused point clouds"))
    parser.add_argument("image", help=_t("Image file"))
    parser.add_argument("sensor", help=_t("Sensor point cloud CSV"))
    parser.add_argument(
        "--model",
        default="fused_gaussian_model.json",
        help=_t("Trained model JSON"),
    )
    parser.add_argument(
        "--top", type=int, default=3, help=_t("Number of top classes to show")
    )
    args = parser.parse_args()

    results = rank_fused_gaussian(args.image, args.sensor, args.model, args.top)
    table = Table(title=_t("Fused Gaussian matches"))
    table.add_column(_t("Class"))
    table.add_column(_t("Distance"), justify="right")
    table.add_column(_t("Probability"), justify="right")
    for label, score, prob in results:
        table.add_row(label, f"{score:.2f}", f"{prob:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_fused_gaussian_report()
