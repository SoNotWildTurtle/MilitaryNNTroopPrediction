"""CLI wrapper for the theatre outlook assessment."""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

from ..analysis.theater_assessment import assess_theater_outlook
from ..config import settings
from ..translation import translate_text


console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def _render_corridors(entries) -> None:
    if not entries:
        console.print(Panel(_t("No detections in window."), border_style="yellow"))
        return
    table = Table(title=_t("Corridor summary"), box=box.ROUNDED)
    table.add_column(_t("Corridor"), style="cyan")
    table.add_column(_t("Detections"), justify="right")
    table.add_column(_t("Avg confidence"), justify="right")
    table.add_column(_t("Momentum"), style="magenta")
    table.add_column(_t("Top classes"))
    for item in entries:
        avg = item.get("avg_confidence")
        classes = ", ".join(item.get("top_classes", []))
        table.add_row(
            str(item.get("corridor", "?")),
            str(item.get("detections", 0)),
            f"{avg:.2f}" if isinstance(avg, (float, int)) else "—",
            _t(str(item.get("momentum", "unknown"))),
            _t(classes) if classes else "—",
        )
    console.print(table)


def _render_axes(entries) -> None:
    if not entries:
        return
    table = Table(title=_t("Axes of advance"), box=box.ROUNDED)
    table.add_column(_t("Axis"), style="cyan")
    table.add_column(_t("Count"), justify="right")
    table.add_column(_t("Avg confidence"), justify="right")
    table.add_column(_t("Units"))
    for item in entries:
        avg = item.get("avg_confidence")
        units = ", ".join(item.get("units", []))
        table.add_row(
            _t(str(item.get("axis", "?"))),
            str(item.get("count", 0)),
            f"{avg:.2f}" if isinstance(avg, (float, int)) else "—",
            units or "—",
        )
    console.print(table)


def _render_hotspots(entries) -> None:
    if not entries:
        console.print(Panel(_t("No risk hotspots identified."), border_style="green"))
        return
    table = Table(title=_t("Risk hotspots"), box=box.ROUNDED)
    table.add_column(_t("Corridor"), style="cyan")
    table.add_column(_t("Risk"), style="magenta")
    table.add_column(_t("Avg confidence"), justify="right")
    table.add_column(_t("Drivers"))
    for item in entries:
        avg = item.get("avg_confidence")
        drivers = ", ".join(item.get("drivers", []))
        table.add_row(
            str(item.get("corridor", "?")),
            _t(str(item.get("risk", "unknown"))),
            f"{avg:.2f}" if isinstance(avg, (float, int)) else "—",
            _t(drivers) if drivers else "—",
        )
    console.print(table)


def run_theater_assessment_report(
    *,
    area: Optional[str] = None,
    lookback_hours: Optional[int] = None,
    detection_limit: Optional[int] = None,
    prediction_limit: Optional[int] = None,
) -> None:
    """Run the theatre assessment and display a Rich report."""

    target_area = area or Prompt.ask(_t("Area"), default="default")
    hours = lookback_hours or int(Prompt.ask(_t("Lookback hours"), default="36"))
    det_limit = detection_limit or int(Prompt.ask(_t("Detection limit"), default="400"))
    pred_limit = prediction_limit or int(Prompt.ask(_t("Prediction limit"), default="100"))

    result = assess_theater_outlook(
        target_area,
        lookback_hours=hours,
        detection_limit=det_limit,
        prediction_limit=pred_limit,
    )

    header = Table(box=box.ROUNDED)
    header.add_column(_t("Field"), style="cyan")
    header.add_column(_t("Value"), style="magenta")
    timeframe = result.get("timeframe", {})
    header.add_row(_t("Area"), target_area)
    header.add_row(_t("Lookback (h)"), str(timeframe.get("lookback_hours", hours)))
    header.add_row(_t("Detections"), str(timeframe.get("total_detections", 0)))
    header.add_row(_t("Latest detection"), str(timeframe.get("latest_detection", "—")))
    centroid = result.get("centroid", {})
    header.add_row(
        _t("Centroid"),
        f"lat {centroid.get('lat', 0):.3f}, lon {centroid.get('lon', 0):.3f}",
    )
    console.print(Panel(header, title=_t("Theatre outlook"), border_style="blue"))

    _render_corridors(result.get("corridors", []))
    _render_axes(result.get("axes_of_advance", []))
    tempo = result.get("tempo", {})
    tempo_panel = Panel(
        _t(
            f"Assessment: {tempo.get('assessment', 'unknown')} – recent {tempo.get('recent', 0)} vs earlier {tempo.get('earlier', 0)}"
        ),
        title=_t("Tempo"),
        border_style="magenta",
    )
    console.print(tempo_panel)
    _render_hotspots(result.get("risk_hotspots", []))

    recommendations = result.get("recommendations", [])
    if recommendations:
        rec_text = "\n".join(f"• {_t(rec)}" for rec in recommendations)
        console.print(Panel(rec_text, title=_t("Recommendations"), border_style="green"))

    notes = result.get("notes", [])
    if notes:
        note_text = "\n".join(f"• {_t(note)}" for note in notes)
        console.print(Panel(note_text, title=_t("Analyst notes"), border_style="cyan"))


if __name__ == "__main__":  # pragma: no cover
    run_theater_assessment_report()
