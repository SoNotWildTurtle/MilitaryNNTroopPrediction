"""Render a doctrine-aware movement drilldown table."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from ..analysis.doctrine_movement import (
    AVAILABLE_LEVELS,
    doctrine_movement_drilldown,
    doctrine_movement_hierarchy,
)
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG
LEVEL_CHOICES = list(AVAILABLE_LEVELS) + ["all"]

_LEVEL_BASE_LABELS: Dict[str, str] = {
    "unit": "Unit",
    "group": "Group",
    "battalion": "Battalion",
}


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def _level_label(level: str) -> str:
    return _t(_LEVEL_BASE_LABELS.get(level, level.title()))


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


def _render_single_level(level: str, result: Dict[str, object]) -> bool:
    label = _level_label(level)
    rows = result.get("rows", [])
    if not rows:
        console.print(
            f"{_t('No movement records matched the filters for')} {label}.",
            style="yellow",
        )
        return False

    table = Table(
        title=f"{_t('Doctrine movement drilldown')} · {label}",
        show_lines=False,
    )
    table.add_column(label)
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
        summary_table = Table(title=f"{_t('Doctrine summary')} · {label}")
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
    return True


def _prompt_identifier_map() -> Dict[str, Optional[str]]:
    identifiers: Dict[str, Optional[str]] = {}
    if Confirm.ask(_t("Apply the same identifier to every level?"), default=False):
        shared = Prompt.ask(_t("Identifier (optional)"), default="").strip() or None
        if shared:
            for lvl in AVAILABLE_LEVELS:
                identifiers[lvl] = shared
        return identifiers

    for lvl in AVAILABLE_LEVELS:
        label = _level_label(lvl)
        value = Prompt.ask(
            f"{label} — {_t('Identifier (optional)')}",
            default="",
        ).strip()
        if value:
            identifiers[lvl] = value
    return identifiers


def run_doctrine_movement_report() -> None:
    """Prompt for filters and print doctrine-based movement timelines."""

    level = Prompt.ask(
        _t("Level (unit/group/battalion)"),
        choices=LEVEL_CHOICES,
        default=LEVEL_CHOICES[0],
    )

    identifier: Optional[str] = None
    if level != "all":
        identifier = Prompt.ask(_t("Identifier (optional)"), default="").strip() or None
    bucket = Prompt.ask(
        _t("Time bucket"), choices=["hour", "day"], default="hour"
    )
    start = _parse_optional_date(_t("Start timestamp (YYYY-MM-DD or ISO, optional)"))
    end = _parse_optional_date(_t("End timestamp (YYYY-MM-DD or ISO, optional)"))
    hours = _parse_hours()

    if level == "all":
        identifier_map = _prompt_identifier_map()
        hierarchy = doctrine_movement_hierarchy(
            levels=AVAILABLE_LEVELS,
            identifiers=identifier_map or None,
            bucket=bucket,
            hours=hours,
            start=start,
            end=end,
        )
        has_rows = False
        for lvl in AVAILABLE_LEVELS:
            result = hierarchy["levels"].get(lvl, {})
            if _render_single_level(lvl, result):
                has_rows = True
        if not has_rows:
            console.print(_t("No movement records matched the filters."), style="yellow")
        return

    result = doctrine_movement_drilldown(
        level,
        identifier,
        bucket=bucket,
        hours=hours,
        start=start,
        end=end,
    )
    _render_single_level(level, result)


if __name__ == "__main__":
    run_doctrine_movement_report()
