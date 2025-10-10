"""Textual-based control centre that surfaces key operational insights."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:  # pragma: no cover - optional dependency resolution
    from rich.markdown import Markdown
except ImportError:  # pragma: no cover - rich may be missing in minimal environments
    Markdown = None

try:  # pragma: no cover - optional dependency resolution
    from ..analysis.next_gen_recommendations import gather_next_gen_recommendations  # type: ignore
except Exception as exc:  # pragma: no cover - allow import without heavy deps
    def gather_next_gen_recommendations(*args, **kwargs):  # type: ignore
        raise RuntimeError("next_gen_recommendations module unavailable") from exc

try:  # pragma: no cover - optional dependency resolution
    from ..analysis.object_drilldown import object_speed_summary  # type: ignore
except Exception as exc:  # pragma: no cover - allow import without heavy deps
    def object_speed_summary(*args, **kwargs):  # type: ignore
        raise RuntimeError("object_speed_summary unavailable") from exc

from ..config import settings
from ..translation import translate_text

TEXTUAL_AVAILABLE = True
try:  # pragma: no cover - optional dependency resolution
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, VerticalScroll
    from textual.widgets import (
        Button,
        DataTable,
        Footer,
        Header,
        Input,
        Static,
        TabPane,
        TabbedContent,
    )
except ImportError:  # pragma: no cover - textual not installed
    TEXTUAL_AVAILABLE = False


_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate interface strings when a different UI language is set."""

    return translate_text(text, target_lang=_LANG)


def _update_static(widget, text: str) -> None:
    """Update a Static widget with Markdown when available."""

    if Markdown is not None:
        widget.update(Markdown(text))
    else:  # pragma: no cover - fallback path when rich is absent
        widget.update(text)


@dataclass
class ControlSnapshot:
    """Aggregate data used by the control centre UI."""

    area: Optional[str]
    recommendations: Dict[str, Any]
    speed_summaries: List[Dict[str, Any]]
    errors: List[str]


def _empty_recommendations(area: Optional[str]) -> Dict[str, Any]:
    """Return a baseline payload when recommendations are unavailable."""

    return {
        "priority": [],
        "monitor": [],
        "data_quality": [],
        "sensor_tasks": [],
        "intel_tasks": [],
        "focus": [],
        "risk_matrix": {},
        "opportunities": [],
        "summary": {},
        "latest_detection": None,
        "lookback_hours": 24,
        "area": area,
    }


def gather_control_snapshot(area: Optional[str]) -> ControlSnapshot:
    """Collect dashboard data, tolerating missing databases or sensors."""

    errors: List[str] = []
    try:
        recommendations = gather_next_gen_recommendations(area, lookback_hours=24)
    except Exception as exc:  # pragma: no cover - defensive guardrail
        errors.append(f"Failed to gather recommendations: {exc}")
        recommendations = _empty_recommendations(area)

    speed_summaries: List[Dict[str, Any]] = []
    for object_type in ("armor", "aircraft", "drone"):
        try:
            summary = object_speed_summary(object_type, hours=24)
        except Exception as exc:  # pragma: no cover - database offline, etc.
            errors.append(f"{object_type} speed summary unavailable: {exc}")
            speed_summaries.append(
                {
                    "object_type": object_type,
                    "total_units": 0,
                    "overall_avg_speed_kmh": 0.0,
                    "rows": [],
                    "error": str(exc),
                }
            )
            continue
        summary.setdefault("rows", [])
        summary.setdefault("total_units", len(summary.get("rows", [])))
        summary.setdefault("overall_avg_speed_kmh", 0.0)
        speed_summaries.append(summary)

    return ControlSnapshot(area, recommendations, speed_summaries, errors)


if TEXTUAL_AVAILABLE:  # pragma: no cover - exercised via manual runs

    class ControlCenterApp(App[None]):
        """Textual application that surfaces pipeline insights."""

        CSS = """
        #top-bar {
            padding: 1 2;
            background: $surface;
        }
        #status {
            color: $text-muted;
            padding-left: 1;
        }
        .panel-scroll {
            padding: 1;
        }
        """

        BINDINGS = [
            ("q", "quit", "Quit"),
            ("r", "refresh", "Refresh"),
        ]

        def __init__(self, default_area: Optional[str] = None) -> None:
            super().__init__()
            self._area = default_area or ""
            self._snapshot: Optional[ControlSnapshot] = None

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Container(id="top-bar"):
                with Horizontal():
                    yield Input(
                        placeholder=_t("Area (optional)"),
                        value=self._area,
                        id="area-input",
                    )
                    yield Button(_t("Apply"), id="apply-area", variant="primary")
                    yield Button(_t("Refresh"), id="refresh-button")
                    yield Static("", id="status")
            with TabbedContent(id="tabs"):
                with TabPane(_t("Overview"), id="overview-pane"):
                    with VerticalScroll(id="overview-scroll", classes="panel-scroll"):
                        yield Static(id="overview-content")
                with TabPane(_t("Risk matrix"), id="risk-pane"):
                    table = DataTable(id="risk-table")
                    table.add_columns(
                        _t("Class"),
                        _t("Band"),
                        _t("Score"),
                        _t("Signals"),
                    )
                    yield table
                with TabPane(_t("Speeds"), id="speed-pane"):
                    speed_table = DataTable(id="speed-table")
                    speed_table.add_columns(
                        _t("Type"),
                        _t("Unit or note"),
                        _t("Avg km/h"),
                        _t("Max km/h"),
                        _t("Distance km"),
                        _t("Samples"),
                    )
                    yield speed_table
                with TabPane(_t("Guidance"), id="guidance-pane"):
                    with VerticalScroll(id="guidance-scroll", classes="panel-scroll"):
                        yield Static(id="guidance-content")
            yield Footer()

        async def on_mount(self) -> None:
            await self._refresh_snapshot()

        async def action_refresh(self) -> None:
            await self._refresh_snapshot()

        async def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "apply-area":
                input_widget = self.query_one("#area-input", Input)
                self._area = input_widget.value.strip()
                await self._refresh_snapshot()
            elif event.button.id == "refresh-button":
                await self._refresh_snapshot()

        async def _refresh_snapshot(self) -> None:
            status = self.query_one("#status", Static)
            status.update(_t("Loading latest data…"))
            snapshot = await self.call_in_thread(gather_control_snapshot, self._area or None)
            self._snapshot = snapshot
            self._update_overview(snapshot)
            self._update_risk(snapshot)
            self._update_speeds(snapshot)
            self._update_guidance(snapshot)
            if snapshot.errors:
                status.update(_t("Updated with warnings:") + " " + "; ".join(snapshot.errors))
            else:
                status.update(_t("Updated"))

        def _update_overview(self, snapshot: ControlSnapshot) -> None:
            rec = snapshot.recommendations
            lines = [f"# {_t('Operational overview')}"]
            if snapshot.area:
                lines.append(f"*{_t('Area')}:* {snapshot.area}")
            latest = rec.get("latest_detection") or _t("Unknown")
            lines.append(f"*{_t('Latest detection')}:* {latest}")
            lines.append(f"*{_t('Lookback (hours)')}:* {rec.get('lookback_hours', 24)}")
            for key, title in [
                ("priority", _t("Priority")),
                ("monitor", _t("Watch")),
                ("data_quality", _t("Data quality")),
            ]:
                items = rec.get(key, []) or []
                lines.append(f"\n## {title}")
                if not items:
                    lines.append(_t("- No items at this time."))
                else:
                    for item in items[:8]:
                        lines.append(f"- {item}")
                    if len(items) > 8:
                        lines.append(_t("- … additional items available via CLI"))
            focus_items = rec.get("focus", [])
            if focus_items:
                lines.append(f"\n## {_t('Focus signals')}")
                for item in focus_items[:5]:
                    label = item.get("label", "unknown")
                    score = item.get("score", 0.0)
                    signal_text = ", ".join(item.get("signals", []))
                    lines.append(f"- **{label}** · {score:.2f} · {signal_text}")
            overview = self.query_one("#overview-content", Static)
            _update_static(overview, "\n".join(lines))

        def _update_risk(self, snapshot: ControlSnapshot) -> None:
            table = self.query_one("#risk-table", DataTable)
            table.clear()
            risk_matrix = snapshot.recommendations.get("risk_matrix", {})
            entries = sorted(
                risk_matrix.values(),
                key=lambda item: item.get("score", 0.0),
                reverse=True,
            )
            if not entries:
                table.add_row(_t("No data"), "-", "-", "-")
                return
            for entry in entries[:20]:
                signals = ", ".join(entry.get("signals", [])) or "-"
                table.add_row(
                    str(entry.get("label", "unknown")),
                    str(entry.get("band", "-")),
                    f"{entry.get('score', 0.0):.2f}",
                    signals,
                )

        def _update_speeds(self, snapshot: ControlSnapshot) -> None:
            table = self.query_one("#speed-table", DataTable)
            table.clear()
            for summary in snapshot.speed_summaries:
                object_type = summary.get("object_type", "unknown")
                if summary.get("error"):
                    table.add_row(object_type, summary["error"], "-", "-", "-", "-")
                    continue
                rows = summary.get("rows", [])
                if not rows:
                    table.add_row(object_type, _t("No units"), "-", "-", "-", "-")
                    continue
                for row in rows[:5]:
                    table.add_row(
                        object_type,
                        str(row.get("unit_id", "unknown")),
                        f"{row.get('avg_speed_kmh', 0.0):.1f}",
                        f"{row.get('max_speed_kmh', 0.0):.1f}",
                        f"{row.get('distance_km', 0.0):.1f}",
                        str(row.get("samples", 0)),
                    )
                table.add_row(
                    object_type,
                    _t("Overall average"),
                    f"{summary.get('overall_avg_speed_kmh', 0.0):.1f}",
                    "-",
                    "-",
                    str(summary.get("total_units", len(rows))),
                )

        def _update_guidance(self, snapshot: ControlSnapshot) -> None:
            rec = snapshot.recommendations
            lines: List[str] = [f"# {_t('Action guidance')}"]
            for key, title in [
                ("sensor_tasks", _t("Sensor actions")),
                ("intel_tasks", _t("Intelligence follow-ups")),
                ("opportunities", _t("Opportunities")),
            ]:
                lines.append(f"\n## {title}")
                items = rec.get(key, []) or []
                if not items:
                    lines.append(_t("- Nothing queued."))
                else:
                    for item in items[:8]:
                        lines.append(f"- {item}")
                    if len(items) > 8:
                        lines.append(_t("- … additional items available via CLI"))
            if snapshot.errors:
                lines.append(f"\n## {_t('Warnings')}")
                for err in snapshot.errors:
                    lines.append(f"- {err}")
            guidance = self.query_one("#guidance-content", Static)
            _update_static(guidance, "\n".join(lines))


def run_control_center(area: Optional[str] = None) -> None:
    """Launch the Textual control centre if the dependency is installed."""

    if not TEXTUAL_AVAILABLE:
        raise RuntimeError(
            "textual is not installed; install it with `pip install textual` to launch the control centre."
        )
    app = ControlCenterApp(default_area=area)
    app.run()


__all__ = ["run_control_center", "gather_control_snapshot", "ControlSnapshot"]
