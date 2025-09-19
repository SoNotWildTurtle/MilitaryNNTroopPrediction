"""Display average and median time between detections."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.interarrival import interarrival_times
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate text to the configured language."""
    return translate_text(text, target_lang=_LANG)


def run_interarrival_report() -> None:
    """Print average and median hours between detections per class."""
    days = int(Prompt.ask(_t("Lookback days"), default="30"))
    data = interarrival_times(days=days)
    if not data:
        console.print(_t("Not enough data"), style="yellow")
        return
    table = Table(title=_t("Time between detections (hours)"))
    table.add_column(_t("Class"))
    table.add_column(_t("Average"), justify="right")
    table.add_column(_t("Median"), justify="right")
    for row in data:
        table.add_row(
            row["class"],
            f"{row['avg_hours']:.2f}",
            f"{row['median_hours']:.2f}",
        )
    console.print(table)


if __name__ == "__main__":
    run_interarrival_report()
