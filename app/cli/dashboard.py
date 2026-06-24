"""Rich-based CLI providing a simple text dashboard."""
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

from ..pipeline import realtime, monitor
from ..analysis import heatmap
from ..utils.human_feedback_viewer import launch_feedback_gui
from . import doctor


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
        console.print("\n[1] Run setup doctor")
        console.print("[2] Run pipeline once")
        console.print("[3] Monitor area continuously")
        console.print("[4] Generate heatmap")
        console.print("[5] Launch feedback GUI")
        console.print("[6] Exit")
        choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "6"], default="6")
        if choice == "1":
            _show_doctor_results()
        elif choice == "2":
            area = Prompt.ask("Area name")
            model = Prompt.ask("Trajectory model", default="models/trajectory.h5")
            realtime.process_area(area, model)
        elif choice == "3":
            area = Prompt.ask("Area name")
            model = Prompt.ask("Trajectory model", default="models/trajectory.h5")
            interval = _ask_int("Interval seconds", default="300")
            console.print("Press Ctrl+C to stop monitoring")
            try:
                monitor.monitor(area, model, interval)
            except KeyboardInterrupt:
                console.print("Monitoring stopped")
        elif choice == "4":
            area = Prompt.ask("Area name")
            hours = _ask_int("Hours", default="24")
            output = Prompt.ask("Output file", default=f"{area}_heatmap.png")
            heatmap.generate_heatmap(area, hours, output=Path(output))
        elif choice == "5":
            img_dir = Path(Prompt.ask("Image directory"))
            pred_csv = Path(Prompt.ask("Predictions CSV"))
            out_csv = Path(Prompt.ask("Output feedback CSV"))
            launch_feedback_gui(img_dir, pred_csv, out_csv)
        else:
            console.print("Goodbye!", style="bold green")
            break


if __name__ == "__main__":
    run_dashboard()
