"""Render a doctrine-aware movement drilldown table."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..analysis.doctrine_movement import doctrine_movement_drilldown
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def _parse_optional_date(label: str) -> Optional[datetime]:
    raw = Prompt.ask(label, default="")
    if not raw.strip():
        return None
    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError:
        console.print(_t("Invalid date format, expected ISO 8601."), style="red")
        return _parse_optional_date(label)


def _parse_hours(default: str = "24") -> int:
    value = Prompt.ask(_t("Lookback hours (ignored if start/end provided)"), default=default)
    try:
        return max(1, int(value))
    except ValueError:
        console.print(_t("Enter a valid integer for hours."), style="red")
        return _parse_hours(default)


def run_doctrine_movement_report() -> None:
    """Prompt for filters and print doctrine-based movement timelines."""

    level = Prompt.ask(
        _t("Level (unit/group/battalion)"),
        choices=["unit", "group", "battalion"],
        default="unit",
    )
    identifier = Prompt.ask(_t("Identifier (optional)"), default="").strip() or None
    bucket = Prompt.ask(
        _t("Time bucket"), choices=["hour", "day"], default="hour"
    )
    start = _parse_optional_date(_t("Start timestamp (YYYY-MM-DD or ISO, optional)"))
    end = _parse_optional_date(_t("End timestamp (YYYY-MM-DD or ISO, optional)"))
    hours = _parse_hours()

    result = doctrine_movement_drilldown(
        level,
        identifier,
        bucket=bucket,
        hours=hours,
        start=start,
        end=end,
    )
    rows = result.get("rows", [])
    if not rows:
        console.print(_t("No movement records matched the filters."), style="yellow")
        return

    level_label = {
        "unit": _t("Unit"),
        "group": _t("Group"),
        "battalion": _t("Battalion"),
    }[result["level"]]

    table = Table(title=_t("Doctrine movement drilldown"), show_lines=False)
    table.add_column(level_label)
    table.add_column(_t("Doctrine"))
    table.add_column(_t("Bucket start"))
    table.add_column(_t("Avg km/h"), justify="right")
    table.add_column(_t("Max km/h"), justify="right")
    table.add_column(_t("Distance km"), justify="right")
    table.add_column(_t("Hours"), justify="right")
    table.add_column(_t("Samples"), justify="center")

    for row in rows:
        table.add_row(
            str(row["level_value"]),
            str(row["doctrine"]),
            str(row["bucket_start"]),
            f"{row['avg_speed_kmh']:.2f}",
            f"{row['max_speed_kmh']:.2f}",
            f"{row['distance_km']:.2f}",
            f"{row['duration_hours']:.2f}",
            str(row["samples"]),
        )

    console.print(table)

    summary = result.get("doctrine_summary", [])
    if summary:
        summary_table = Table(title=_t("Doctrine summary"))
        summary_table.add_column(_t("Doctrine"))
        summary_table.add_column(_t("Avg km/h"), justify="right")
        summary_table.add_column(_t("Distance km"), justify="right")
        summary_table.add_column(_t("Hours"), justify="right")
        summary_table.add_column(_t("Samples"), justify="center")
        summary_table.add_column(_t("Buckets"), justify="center")
        for entry in summary:
            summary_table.add_row(
                str(entry["doctrine"]),
                f"{entry['avg_speed_kmh']:.2f}",
                f"{entry['distance_km']:.2f}",
                f"{entry['duration_hours']:.2f}",
                str(entry["samples"]),
                str(entry["buckets"]),
            )
        console.print(summary_table)


if __name__ == "__main__":
    run_doctrine_movement_report()
