"""CLI to show detection bursts in recent data."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis import detect_bursts
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_burst_report() -> None:
    """Prompt for parameters and display burst results."""
    hours = int(Prompt.ask(_t("Lookback hours"), default="24"))
    bucket = int(Prompt.ask(_t("Bucket minutes"), default="60"))
    thresh = float(Prompt.ask(_t("Z-score threshold"), default="2.0"))
    bursts = detect_bursts(hours=hours, bucket_minutes=bucket, z_thresh=thresh)
    if not bursts:
        console.print(_t("No bursts detected"), style="green")
        return
    table = Table(title=_t("Detection bursts"))
    table.add_column(_t("Class"))
    table.add_column(_t("Bucket start"))
    table.add_column(_t("Count"), justify="right")
    table.add_column("z", justify="right")
    for b in bursts:
        table.add_row(b["class"], b["bucket_start"], str(b["count"]), f"{b['z']:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_burst_report()
