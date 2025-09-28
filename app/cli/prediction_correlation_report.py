"""CLI to display correlation between model predictions."""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
from rich.console import Console
from rich.table import Table

from ..analysis import prediction_correlations
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG

def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)

def run_prediction_correlation_report() -> None:
    parser = argparse.ArgumentParser(description=_t("Correlate model predictions"))
    parser.add_argument("json_file", help=_t("JSON list of prediction records"))
    args = parser.parse_args()

    matrix = prediction_correlations(Path(args.json_file))
    models = list(matrix.keys())
    table = Table(title=_t("Prediction correlation"))
    table.add_column(_t("Model"))
    for m in models:
        table.add_column(m, justify="right")
    for m1 in models:
        row = [m1]
        for m2 in models:
            val = matrix[m1][m2]
            row.append("nan" if np.isnan(val) else f"{val:.2f}")
        table.add_row(*row)
    console.print(table)

if __name__ == "__main__":
    run_prediction_correlation_report()
