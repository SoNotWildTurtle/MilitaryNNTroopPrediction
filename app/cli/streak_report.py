"""Display longest detection streak per class."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.detection_streaks import detection_streaks
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG

def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_streak_report() -> None:
    """Print the longest detection streak for each class."""
    days = int(Prompt.ask(_t("Lookback days"), default="30"))
    data = detection_streaks(days=days)
    if not data:
        console.print(_t("No detections found"), style="yellow")
        return
    table = Table(title=_t("Detection streaks"))
    table.add_column(_t("Class"))
    table.add_column(_t("Longest streak (days)"), justify="right")
    for row in data:
        table.add_row(row["class"], str(row["max_streak"]))
    console.print(table)


if __name__ == "__main__":
    run_streak_report()
