"""CLI to print detection anomalies based on recent trends."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis import detect_anomalies
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_anomaly_report() -> None:
    """Prompt for parameters and display anomaly results."""
    hours = int(Prompt.ask(_t("Lookback hours"), default="24"))
    days = int(Prompt.ask(_t("Baseline days"), default="7"))
    thresh = float(Prompt.ask(_t("Z-score threshold"), default="2.0"))
    anomalies = detect_anomalies(hours=hours, baseline_days=days, z_thresh=thresh)
    if not anomalies:
        console.print(_t("No anomalies found"), style="green")
        return
    table = Table(title=_t("Detection anomalies"))
    table.add_column(_t("Class"))
    table.add_column(_t("Recent/hr"), justify="right")
    table.add_column(_t("Baseline/hr"), justify="right")
    table.add_column("z", justify="right")
    for a in anomalies:
        table.add_row(
            a["class"],
            f"{a['recent_per_hr']:.2f}",
            f"{a['baseline_per_hr']:.2f}",
            f"{a['z']:.2f}",
        )
    console.print(table)


if __name__ == "__main__":
    run_anomaly_report()
