"""CLI wrapper for the operational tactics assessment."""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

from ..analysis.operational_tactics import assess_operational_tactics
from ..config import settings
from ..translation import translate_text


console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def _render_top_classes(entries) -> None:
    if not entries:
        console.print(Panel(_t("No detections in window."), border_style="yellow"))
        return
    table = Table(title=_t("Top classes"), box=box.ROUNDED, show_lines=False)
    table.add_column(_t("Class"), style="cyan")
    table.add_column(_t("Count"), justify="right")
    table.add_column(_t("Avg confidence"), justify="right")
    for item in entries:
        avg = item.get("avg_confidence")
        table.add_row(
            str(item.get("label", "?")),
            str(item.get("count", 0)),
            f"{avg:.2f}" if isinstance(avg, (float, int)) else "—",
        )
    console.print(table)


def _render_list(title: str, entries) -> None:
    if not entries:
        return
    body = "\n".join(f"• {entry}" for entry in entries)
    console.print(Panel(_t(body), title=_t(title), border_style="cyan"))


def run_operational_analysis_report(
    *,
    area: Optional[str] = None,
    lookback_hours: Optional[int] = None,
    detection_limit: Optional[int] = None,
    prediction_limit: Optional[int] = None,
) -> None:
    """Run the operational tactics assessment and display the output."""

    target_area = area or Prompt.ask(_t("Area"), default="default")
    hours = lookback_hours or int(Prompt.ask(_t("Lookback hours"), default="24"))
    det_limit = detection_limit or int(Prompt.ask(_t("Detection limit"), default="200"))
    pred_limit = prediction_limit or int(Prompt.ask(_t("Prediction limit"), default="60"))

    result = assess_operational_tactics(
        target_area,
        lookback_hours=hours,
        detection_limit=det_limit,
        prediction_limit=pred_limit,
    )

    posture = result.get("posture", {})
    console.print(
        Panel(
            _t(posture.get("detail", "")),
            title=_t(f"Posture: {posture.get('posture', 'unknown').title()}"),
            border_style="green",
        )
    )

    composition = result.get("force_composition", {})
    summary_table = Table(box=box.ROUNDED, show_lines=False)
    summary_table.add_column(_t("Metric"), style="magenta")
    summary_table.add_column(_t("Value"), style="cyan")
    summary_table.add_row(
        _t("Total detections"),
        str(composition.get("total_detections", 0)),
    )
    for category, value in sorted(composition.get("category_counts", {}).items()):
        summary_table.add_row(_t(category.title()), str(value))
    console.print(Panel(summary_table, title=_t("Force composition"), border_style="blue"))

    _render_top_classes(composition.get("top_classes", []))

    logistics = result.get("logistics", {})
    logistic_panel = Panel(
        "\n".join(logistics.get("notes", [])) or _t("No logistics notes."),
        title=_t(f"Logistics: {logistics.get('status', 'unknown').title()}"),
        border_style="magenta",
    )
    console.print(logistic_panel)

    air = result.get("air_activity", {})
    air_table = Table(title=_t("Air activity"), box=box.ROUNDED)
    air_table.add_column(_t("Metric"), style="magenta")
    air_table.add_column(_t("Value"), justify="right")
    air_table.add_row(_t("Total"), str(air.get("total", 0)))
    air_table.add_row(_t("Drones"), str(air.get("drones", 0)))
    air_table.add_row(_t("Crewed"), str(air.get("crewed", 0)))
    air_table.add_row(_t("Assessment"), _t(str(air.get("assessment", "unknown"))))
    console.print(air_table)
    _render_list("Air notes", air.get("notes", []))

    timeline = result.get("timeline", {})
    timeline_table = Table(title=_t("Timeline"), box=box.ROUNDED)
    timeline_table.add_column(_t("Metric"), style="magenta")
    timeline_table.add_column(_t("Value"), justify="right")
    timeline_table.add_row(_t("Trend"), _t(str(timeline.get("trend", "unknown"))))
    timeline_table.add_row(_t("Recent detections"), str(timeline.get("recent", 0)))
    timeline_table.add_row(_t("Earlier detections"), str(timeline.get("earlier", 0)))
    timeline_table.add_row(
        _t("Recent window (h)"),
        str(timeline.get("recent_window_hours", "")),
    )
    console.print(timeline_table)

    movement = result.get("movement", {})
    _render_list("Operational signals", movement.get("insights", []))
    _render_list("Tactic indicators", result.get("tactic_indicators", []))
    _render_list("Recommendations", result.get("recommendations", []))


if __name__ == "__main__":  # pragma: no cover
    run_operational_analysis_report()
