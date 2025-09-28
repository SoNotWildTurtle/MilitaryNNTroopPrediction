"""Display detection trends over recent days."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.detection_trends import detection_trends
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate text to the configured language."""
    return translate_text(text, target_lang=_LANG)


def run_trend_report() -> None:
    """Print per-class detection counts grouped by day."""
    days = int(Prompt.ask(_t("Lookback days"), default="7"))
    data = detection_trends(days=days)
    if not data:
        console.print(_t("No detections found"), style="yellow")
        return
    table = Table(title=_t("Detection trends"))
    table.add_column(_t("Date"))
    table.add_column(_t("Class"))
    table.add_column(_t("Count"), justify="right")
    for row in data:
        table.add_row(row["date"], row["class"], str(row["count"]))
    console.print(table)


if __name__ == "__main__":
    run_trend_report()
