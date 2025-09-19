"""Summarize detection confidence metrics."""
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.confidence_stats import confidence_summary
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate UI text to the configured language."""
    return translate_text(text, target_lang=_LANG)


def run_confidence_report() -> None:
    """Print per-class detection confidence statistics."""
    json_file = Path(Prompt.ask(_t("Detections JSON")))
    summary = confidence_summary(json_file)
    if not summary:
        console.print(_t("No detections found"), style="yellow")
        return
    table = Table(title=_t("Confidence summary"))
    table.add_column(_t("Class"))
    table.add_column(_t("Count"), justify="right")
    table.add_column(_t("Avg"), justify="right")
    table.add_column(_t("Min"), justify="right")
    table.add_column(_t("Max"), justify="right")
    for cls, stats in summary.items():
        table.add_row(
            cls,
            str(stats["count"]),
            f"{stats['avg_confidence']:.2f}",
            f"{stats['min_confidence']:.2f}",
            f"{stats['max_confidence']:.2f}",
        )
    console.print(table)


if __name__ == "__main__":
    run_confidence_report()
