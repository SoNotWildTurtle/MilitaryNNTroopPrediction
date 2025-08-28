"""Display class diversity (entropy) per day."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.class_diversity import class_diversity
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate text to the configured language."""
    return translate_text(text, target_lang=_LANG)


def run_diversity_report() -> None:
    """Print daily detection class diversity scores."""
    days = int(Prompt.ask(_t("Lookback days"), default="30"))
    data = class_diversity(days=days)
    if not data:
        console.print(_t("No data"), style="yellow")
        return
    table = Table(title=_t("Class diversity (entropy)"))
    table.add_column(_t("Date"))
    table.add_column(_t("Entropy"), justify="right")
    for row in data:
        table.add_row(row["date"], f"{row['entropy']:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_diversity_report()
