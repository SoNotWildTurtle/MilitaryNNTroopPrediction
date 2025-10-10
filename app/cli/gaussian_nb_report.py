"""Display GaussianNB class probabilities for fused image and sensor clouds."""
from __future__ import annotations

import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table

from ..analysis.gaussian_nb_match import match_gaussian_nb

console = Console()


def run_gaussian_nb_report() -> None:
    parser = argparse.ArgumentParser(description="GaussianNB match report")
    parser.add_argument("--image", required=True, help="Image file")
    parser.add_argument("--sensor", required=True, help="Sensor CSV file")
    parser.add_argument("--model", required=True, help="Trained model path")
    args = parser.parse_args()

    results = match_gaussian_nb(Path(args.image), Path(args.sensor), Path(args.model))
    table = Table(title="GaussianNB Matches")
    table.add_column("Class")
    table.add_column("Probability", justify="right")
    for cls, prob in results:
        table.add_row(cls, f"{prob:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_gaussian_nb_report()
