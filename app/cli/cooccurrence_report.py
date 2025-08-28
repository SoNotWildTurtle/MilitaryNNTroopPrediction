"""Display class co-occurrence counts in a translated table."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.cooccurrence import class_cooccurrence
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate text to the configured language."""
    return translate_text(text, target_lang=_LANG)


def run_cooccurrence_report() -> None:
    """Print a class co-occurrence matrix over a recent window."""
    hours = int(Prompt.ask(_t("Lookback hours"), default="24"))
    matrix = class_cooccurrence(window_hours=hours)
    if not matrix:
        console.print(_t("No detections found"), style="yellow")
        return

    classes = sorted(matrix.keys())
    table = Table(title=_t("Class co-occurrence"))
    table.add_column(_t("Class"))
    for cls in classes:
        table.add_column(cls, justify="right")
    for cls in classes:
        row = [cls] + [str(matrix.get(cls, {}).get(other, 0)) for other in classes]
        table.add_row(*row)
    console.print(table)


if __name__ == "__main__":
    run_cooccurrence_report()
