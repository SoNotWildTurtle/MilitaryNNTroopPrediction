"""CLI for large-scale military campaign assessments."""

from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich import box

from ..analysis.military_campaign import assess_military_campaign
from ..movement_history import recent_detections, recent_predictions
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def _render_metrics(metrics) -> None:
    table = Table(title=_t("Key metrics"), box=box.ROUNDED, show_lines=False)
    table.add_column(_t("Metric"), style="cyan")
    table.add_column(_t("Value"), justify="right")
    for key, value in metrics.items():
        if key == "counts":
            counts = ", ".join(f"{lbl}:{cnt}" for lbl, cnt in sorted(value.items()))
            table.add_row(_t("Detections"), counts or "0")
        elif key == "doctrine":
            doctrine = ", ".join(f"{lbl}:{cnt}" for lbl, cnt in sorted(value.items()))
            table.add_row(_t("Doctrine"), doctrine or _t("None"))
        else:
            table.add_row(_t(key.replace("_", " ").title()), f"{value}")
    console.print(table)


def run_military_campaign_report(
    *,
    area: Optional[str] = None,
    limit: Optional[int] = None,
) -> None:
    """Prompt for context and display the campaign assessment."""

    target_area = area or Prompt.ask(_t("Area"), default="default")
    fetch_limit = limit or int(Prompt.ask(_t("Detection limit"), default="150"))

    detections = recent_detections(target_area, limit=fetch_limit)
    predictions = recent_predictions(target_area, limit=fetch_limit)

    assessment = assess_military_campaign(detections, predictions)

    console.print(
        Panel(
            f"[bold]{_t('Front pressure')}[/]: {assessment.front_pressure}\n"
            f"[bold]{_t('Tempo')}[/]: {assessment.tempo}\n"
            f"[bold]{_t('Logistics')}[/]: {assessment.logistics}\n"
            f"[bold]{_t('Air activity')}[/]: {assessment.air_activity}\n"
            f"[bold]{_t('Attrition risk')}[/]: {assessment.attrition_risk}",
            title=_t("Campaign overview"),
            border_style="cyan",
        )
    )

    _render_metrics(assessment.metrics)

    if assessment.recommended_actions:
        actions = "\n".join(f"• {action}" for action in assessment.recommended_actions)
        console.print(
            Panel(actions, title=_t("Recommended actions"), border_style="magenta")
        )


if __name__ == "__main__":  # pragma: no cover
    run_military_campaign_report()
