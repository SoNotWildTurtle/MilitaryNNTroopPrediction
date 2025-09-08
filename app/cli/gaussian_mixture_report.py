"""CLI for Gaussian mixture matching."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

from rich.console import Console
from rich.table import Table

from app.analysis.gaussian_mixture_match import match_gaussian_mixture

console = Console()


def run_gaussian_mixture_report() -> None:
    parser = argparse.ArgumentParser(description="Gaussian mixture report")
    parser.add_argument("--model", required=True, help="Path to mixture model")
    parser.add_argument("--features", required=True, nargs="+", help="key=value feature pairs")
    args = parser.parse_args()

    feat: Dict[str, float] = {}
    for item in args.features:
        key, value = item.split("=")
        feat[key] = float(value)

    results = match_gaussian_mixture(feat, args.model)
    table = Table(title="Gaussian Mixture Matches")
    table.add_column("Class")
    table.add_column("Probability", justify="right")
    for cls, prob in results:
        table.add_row(cls, f"{prob:.2f}")
    console.print(table)
