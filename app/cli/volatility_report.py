"""Display detection count volatility."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.detection_volatility import detection_volatility
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate text to the configured language."""
    return translate_text(text, target_lang=_LANG)


def run_volatility_report() -> None:
    """Print per-class detection volatility."""
    days = int(Prompt.ask(_t("Lookback days"), default="30"))
    data = detection_volatility(days=days)
    if not data:
        console.print(_t("No detections found"), style="yellow")
        return
    table = Table(title=_t("Detection volatility"))
    table.add_column(_t("Class"))
    table.add_column(_t("Average"), justify="right")
    table.add_column(_t("Std dev"), justify="right")
    for row in data:
        table.add_row(row["class"], f"{row['avg']:.2f}", f"{row['std']:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_volatility_report()
