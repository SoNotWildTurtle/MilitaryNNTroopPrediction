"""Generate a simple summary of recent detections."""
from collections import defaultdict
import argparse
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


def run_detection_report(area: str | None = None, limit: int = 50) -> None:
    """Fetch recent detections for an area and display summary stats."""
    if area is None:
        area = Prompt.ask(_t("Area name"))
    if limit is None:
        limit = int(Prompt.ask(_t("Number of records"), default=str(limit)))
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=_t("Summarize recent detections"), add_help=True
    )
    parser.add_argument("--area", type=str, help=_t("Area name"))
    parser.add_argument(
        "--limit", type=int, default=50, help=_t("Number of records")
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_detection_report(args.area, args.limit)
