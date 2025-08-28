"""Display units with anomalous average speeds."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.speed_anomaly import speed_anomalies
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate text to the configured language."""
    return translate_text(text, target_lang=_LANG)


def run_speed_report() -> None:
    """Print units whose speeds deviate from peers."""
    hours = int(Prompt.ask(_t("Lookback hours"), default="24"))
    z_thresh = float(Prompt.ask(_t("Z-score threshold"), default="2.0"))
    data = speed_anomalies(hours=hours, z_thresh=z_thresh)
    if not data:
        console.print(_t("No anomalies found"), style="yellow")
        return
    table = Table(title=_t("Speed anomalies"))
    table.add_column(_t("Unit"))
    table.add_column(_t("Avg km/h"), justify="right")
    table.add_column(_t("Z"), justify="right")
    for row in data:
        table.add_row(row["unit_id"], f"{row['avg_speed_kmh']:.2f}", f"{row['z']:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_speed_report()
