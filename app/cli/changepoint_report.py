"""Display significant daily count changes per class."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.change_point import change_points
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_changepoint_report() -> None:
    """Prompt for parameters and print change points."""
    days = int(Prompt.ask(_t("Lookback days"), default="30"))
    thresh = float(Prompt.ask(_t("Z-score threshold"), default="2.0"))
    rows = change_points(days=days, z_thresh=thresh)
    if not rows:
        console.print(_t("No change points found"), style="green")
        return
    table = Table(title=_t("Change points"))
    table.add_column(_t("Class"))
    table.add_column(_t("Date"))
    table.add_column(_t("Change"), justify="right")
    table.add_column("z", justify="right")
    for r in rows:
        table.add_row(r["class"], r["date"], str(r["change"]), f"{r['z']:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_changepoint_report()
