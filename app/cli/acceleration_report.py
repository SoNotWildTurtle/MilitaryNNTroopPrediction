"""Display units with anomalous average acceleration."""
import argparse
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.acceleration_anomaly import acceleration_anomalies
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate text to the configured language."""
    return translate_text(text, target_lang=_LANG)


def run_acceleration_report(
    hours: int | None = None, z_thresh: float | None = None
) -> None:
    """Print units whose accelerations deviate from peers."""
    if hours is None:
        hours = int(Prompt.ask(_t("Lookback hours"), default="24"))
    if z_thresh is None:
        z_thresh = float(Prompt.ask(_t("Z-score threshold"), default="2.0"))
    data = acceleration_anomalies(hours=hours, z_thresh=z_thresh)
    if not data:
        console.print(_t("No anomalies found"), style="yellow")
        return
    table = Table(title=_t("Acceleration anomalies"))
    table.add_column(_t("Unit"))
    table.add_column(_t("Avg km/h^2"), justify="right")
    table.add_column(_t("Z"), justify="right")
    for row in data:
        table.add_row(row["unit_id"], f"{row['avg_accel_kmh2']:.2f}", f"{row['z']:.2f}")
    console.print(table)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=_t("List units with anomalous acceleration"), add_help=True
    )
    parser.add_argument("--hours", type=int, help=_t("Lookback hours"))
    parser.add_argument("--z", type=float, help=_t("Z-score threshold"))
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_acceleration_report(args.hours, args.z)
