"""Display rolling average detection counts."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.moving_average import moving_average
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate text to the configured language."""
    return translate_text(text, target_lang=_LANG)


def run_moving_report() -> None:
    """Print per-class moving average counts."""
    days = int(Prompt.ask(_t("Lookback days"), default="30"))
    window = int(Prompt.ask(_t("Window size"), default="7"))
    data = moving_average(days=days, window=window)
    if not data:
        console.print(_t("No detections found"), style="yellow")
        return
    table = Table(title=_t("Moving average"))
    table.add_column(_t("Date"))
    table.add_column(_t("Class"))
    table.add_column(_t("Average"), justify="right")
    for row in data:
        table.add_row(row["date"], row["class"], f"{row['avg']:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_moving_report()
