"""CLI for synthesizing next-gen operational recommendations."""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt
from rich import box

from ..analysis.next_gen_recommendations import gather_next_gen_recommendations
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def _render_list(title: str, items) -> None:
    if not items:
        console.print(Panel(_t("No items"), title=_t(title), border_style="green"))
        return
    body = "\n".join(f"• {item}" for item in items)
    console.print(Panel(body, title=_t(title), border_style="cyan"))


def _render_focus(entries) -> None:
    if not entries:
        return
    table = Table(title=_t("Focus overview"), box=box.SIMPLE, show_lines=False)
    table.add_column(_t("Class"), style="cyan")
    table.add_column(_t("Status"), style="magenta")
    table.add_column(_t("Count"), justify="right")
    table.add_column(_t("Avg conf"), justify="right")
    table.add_column(_t("Last seen"), style="yellow")
    for row in entries:
        avg = row.get("avg_confidence")
        table.add_row(
            str(row.get("label", "?")),
            _t(str(row.get("status", ""))),
            str(row.get("count", 0)),
            f"{avg:.2f}" if isinstance(avg, (float, int)) else "—",
            row.get("last_seen") or "—",
        )
    console.print(table)


def run_next_gen_recommendations(
    *,
    area: Optional[str] = None,
    hours: Optional[int] = None,
    limit: Optional[int] = None,
) -> None:
    """Prompt for parameters and display the compiled recommendations."""

    target_area = area or Prompt.ask(_t("Area"), default="default")
    lookback = hours or int(Prompt.ask(_t("Lookback hours"), default="24"))
    det_limit = limit or int(Prompt.ask(_t("Detection limit"), default="200"))
    result = gather_next_gen_recommendations(
        target_area,
        detection_limit=det_limit,
        lookback_hours=lookback,
    )

    summary = result.get("summary", {})
    if summary:
        table = Table(
            title=_t("Detection summary"),
            box=box.ROUNDED,
            show_lines=True,
        )
        table.add_column(_t("Class"), style="cyan")
        table.add_column(_t("Count"), justify="right")
        table.add_column(_t("Avg confidence"), justify="right")
        table.add_column(_t("Last seen"), style="magenta")
        for label, info in summary.items():
            avg = info.get("avg_confidence")
            table.add_row(
                label,
                str(info.get("count", 0)),
                f"{avg:.2f}" if isinstance(avg, (float, int)) else "—",
                info.get("last_seen") or "—",
            )
        console.print(table)
    else:
        console.print(_t("No detections available for this area"), style="yellow")

    _render_focus(result.get("focus", []))
    risk_matrix = result.get("risk_matrix", [])
    if risk_matrix:
        risk = Table(title=_t("Risk matrix"), box=box.ROUNDED, show_lines=False)
        risk.add_column(_t("Class"), style="cyan")
        risk.add_column(_t("Score"), justify="right")
        risk.add_column(_t("Band"), style="magenta")
        risk.add_column(_t("Signals"), style="yellow")
        for entry in risk_matrix:
            risk.add_row(
                str(entry.get("label", "?")),
                f"{entry.get('score', 0):.2f}",
                _t(str(entry.get("band", ""))),
                ", ".join(entry.get("signals", [])),
            )
        console.print(risk)
    _render_list("Priority actions", result.get("priority", []))
    _render_list("Watch list", result.get("monitor", []))
    _render_list("Data quality", result.get("data_quality", []))
    _render_list("Sensor tasks", result.get("sensor_tasks", []))
    _render_list("Intelligence tasks", result.get("intel_tasks", []))
    _render_list("Opportunities", result.get("opportunities", []))

    if result.get("latest_detection"):
        console.print(
            Panel(
                _t("Latest detection: ") + result["latest_detection"],
                border_style="magenta",
            )
        )


if __name__ == "__main__":  # pragma: no cover
    run_next_gen_recommendations()
