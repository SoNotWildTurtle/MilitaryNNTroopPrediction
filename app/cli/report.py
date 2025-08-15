"""Generate a simple summary of recent detections."""
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..movement_history import recent_detections
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate static UI text if a non-English language is configured."""
    return translate_text(text, target_lang=_LANG)


def run_detection_report() -> None:
    """Fetch recent detections for an area and display summary stats."""
    area = Prompt.ask(_t("Area name"))
    limit = int(Prompt.ask(_t("Number of records"), default="50"))
    detections = recent_detections(area, limit=limit)
    if not detections:
        console.print(_t("No detections found"), style="yellow")
        return

    stats = defaultdict(list)
    for det in detections:
        cls = det.get("class", "unknown")
        stats[cls].append(float(det.get("confidence", 0.0)))

    table = Table(title=_t("Detection summary"))
    table.add_column(_t("Class"))
    table.add_column(_t("Count"), justify="right")
    table.add_column(_t("Avg confidence"), justify="right")

    for cls, confs in stats.items():
        avg = sum(confs) / len(confs)
        table.add_row(cls, str(len(confs)), f"{avg:.2f}")

    console.print(table)


if __name__ == "__main__":
    run_detection_report()
