"""Rich-based CLI providing a simple text dashboard."""
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

from ..pipeline import realtime, monitor
from ..analysis import heatmap
from ..utils.human_feedback_viewer import launch_feedback_gui
from . import doctor, quickstart, release_health


console = Console()


def _show_doctor_results() -> None:
    """Run setup diagnostics and display a compact dashboard summary."""

    results = doctor.run_checks()
    ok, warn, fail = doctor.summarize(results)
    style = "bold green" if fail == 0 else "bold red"
    console.print(Panel(f"{ok} ok | {warn} warnings | {fail} failures", title="Setup Doctor", style=style))
    for result in results:
        marker = {"ok": "[green]OK[/green]", "warn": "[yellow]WARN[/yellow]", "fail": "[red]FAIL[/red]"}[result.status]
        console.print(f"{marker} [bold]{result.name}[/bold]: {result.detail}")
        if result.remediation:
            console.print(f"    fix: {result.remediation}", style="dim")


def _write_release_health() -> None:
    """Create local release health Markdown/JSON reports."""

    markdown_path, json_path, failures = release_health.write_reports()
    style = "bold green" if failures == 0 else "bold red"
    console.print(Panel(f"Markdown: {markdown_path}\nJSON: {json_path}", title="Release Health", style=style))
    if failures:
        console.print("Release health found required setup problems.", style="bold red")
    else:
        console.print("Release health report generated successfully.", style="bold green")


def _run_quickstart() -> None:
    """Run the safe quickstart path from the dashboard."""

    console.print(Panel("Creating .env if needed and running core diagnostics.", title="Quickstart"))
    exit_code = quickstart.run_quickstart(
        quickstart.QuickstartOptions(
            skip_install=True,
            skip_optional_checks=True,
            skip_mongo=True,
        )
    )
    if exit_code:
        console.print("Quickstart found required setup problems.", style="bold red")
    else:
        console.print("Quickstart completed successfully.", style="bold green")


def _ask_int(label: str, default: str) -> int:
    """Prompt for an integer with friendly validation instead of a traceback."""

    while True:
        raw_value = Prompt.ask(label, default=default)
        try:
            return int(raw_value)
        except ValueError:
            console.print("Please enter a whole number.", style="bold red")


def run_dashboard() -> None:
    """Launch an interactive CLI for common tasks."""
    console.print(Panel("Troop Analysis Dashboard", style="bold cyan"))
    while True:
        console.print("\n[1] Run first-run quickstart")
        console.print("[2] Run setup doctor")
        console.print("[3] Generate release health report")
        console.print("[4] Run pipeline once")
        console.print("[5] Monitor area continuously")
        console.print("[6] Generate heatmap")
        console.print("[7] Launch feedback GUI")
        console.print("[8] Exit")
        choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "6", "7", "8"], default="8")
        if choice == "1":
            _run_quickstart()
        elif choice == "2":
            _show_doctor_results()
        elif choice == "3":
            _write_release_health()
        elif choice == "4":
            area = Prompt.ask("Area name")
            model = Prompt.ask("Trajectory model", default="models/trajectory.h5")
            realtime.process_area(area, model)
        elif choice == "5":
            area = Prompt.ask("Area name")
            model = Prompt.ask("Trajectory model", default="models/trajectory.h5")
            interval = _ask_int("Interval seconds", default="300")
            console.print("Press Ctrl+C to stop monitoring")
            try:
                monitor.monitor(area, model, interval)
            except KeyboardInterrupt:
                console.print("Monitoring stopped")
        elif choice == "6":
            area = Prompt.ask("Area name")
            hours = _ask_int("Hours", default="24")
            output = Prompt.ask("Output file", default=f"{area}_heatmap.png")
            heatmap.generate_heatmap(area, hours, output=Path(output))
        elif choice == "7":
            img_dir = Path(Prompt.ask("Image directory"))
            pred_csv = Path(Prompt.ask("Predictions CSV"))
            out_csv = Path(Prompt.ask("Output feedback CSV"))
            launch_feedback_gui(img_dir, pred_csv, out_csv)
        else:
            console.print("Goodbye!", style="bold green")
            break


if __name__ == "__main__":
    run_dashboard()
