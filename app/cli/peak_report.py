"""Display peak detection times per class."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.peak_times import peak_times
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_peak_report() -> None:
    """Print each class's most active hour and weekday."""
    days = int(Prompt.ask(_t("Lookback days"), default="30"))
    data = peak_times(days=days)
    if not data:
        console.print(_t("No detections found"), style="yellow")
        return
    table = Table(title=_t("Peak detection times"))
    table.add_column(_t("Class"))
    table.add_column(_t("Peak hour"), justify="right")
    table.add_column(_t("Peak day"), justify="right")
    day_names = [
        _t("Monday"),
        _t("Tuesday"),
        _t("Wednesday"),
        _t("Thursday"),
        _t("Friday"),
        _t("Saturday"),
        _t("Sunday"),
    ]
    for row in data:
        hour = row["peak_hour"]
        day = row["peak_day"]
        table.add_row(
            row["class"],
            str(hour) if hour is not None else "-",
            day_names[day] if day is not None else "-",
        )
    console.print(table)


if __name__ == "__main__":
    run_peak_report()
