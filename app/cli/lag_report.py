"""CLI to compute lagged correlations between detection classes."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis import lag_correlation
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_lag_report() -> None:
    """Prompt for parameters and display lag correlation results."""
    class_a = Prompt.ask(_t("First class"), default="troop")
    class_b = Prompt.ask(_t("Second class"), default="vehicle")
    hours = int(Prompt.ask(_t("Lookback hours"), default="24"))
    bucket = int(Prompt.ask(_t("Bucket minutes"), default="60"))
    max_lag = int(Prompt.ask(_t("Max lag buckets"), default="3"))
    results = lag_correlation(class_a, class_b, hours=hours, bucket_minutes=bucket, max_lag=max_lag)
    table = Table(title=_t("Lag correlation"))
    table.add_column(_t("Lag (min)"), justify="right")
    table.add_column(_t("Correlation"), justify="right")
    for r in results:
        table.add_row(str(r["lag"]), f"{r['corr']:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_lag_report()
