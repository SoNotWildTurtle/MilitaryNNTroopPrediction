"""Display detection counts by day of week."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.weekly_activity import weekly_activity
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate text to the configured language."""
    return translate_text(text, target_lang=_LANG)


DAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def run_weekly_report() -> None:
    """Print per-class detection counts grouped by day of week."""
    weeks = int(Prompt.ask(_t("Lookback weeks"), default="4"))
    data = weekly_activity(weeks=weeks)
    if not data:
        console.print(_t("No detections found"), style="yellow")
        return
    table = Table(title=_t("Weekly activity"))
    table.add_column(_t("Day"))
    table.add_column(_t("Class"))
    table.add_column(_t("Count"), justify="right")
    for row in data:
        day_label = _t(DAY_NAMES[row["day"]])
        table.add_row(day_label, row["class"], str(row["count"]))
    console.print(table)


if __name__ == "__main__":
    run_weekly_report()
