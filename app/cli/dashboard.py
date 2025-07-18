"""Rich-based CLI providing a simple text dashboard."""
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel

from ..pipeline import realtime, monitor
from ..analysis import heatmap
from ..utils.human_feedback_viewer import launch_feedback_gui


console = Console()

def run_dashboard() -> None:
    """Launch an interactive CLI for common tasks."""
    console.print(Panel("Troop Analysis Dashboard", style="bold cyan"))
    while True:
        console.print("\n[1] Run pipeline once")
        console.print("[2] Monitor area continuously")
        console.print("[3] Generate heatmap")
        console.print("[4] Launch feedback GUI")
        console.print("[5] Exit")
        choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5"], default="5")
        if choice == "1":
            area = Prompt.ask("Area name")
            model = Prompt.ask("Trajectory model", default="models/trajectory.h5")
            realtime.process_area(area, model)
        elif choice == "2":
            area = Prompt.ask("Area name")
            model = Prompt.ask("Trajectory model", default="models/trajectory.h5")
            interval = int(Prompt.ask("Interval seconds", default="300"))
            console.print("Press Ctrl+C to stop monitoring")
            try:
                monitor.monitor(area, model, interval)
            except KeyboardInterrupt:
                console.print("Monitoring stopped")
        elif choice == "3":
            area = Prompt.ask("Area name")
            hours = int(Prompt.ask("Hours", default="24"))
            output = Prompt.ask("Output file", default=f"{area}_heatmap.png")
            heatmap.generate_heatmap(area, hours, output=Path(output))
        elif choice == "4":
            img_dir = Path(Prompt.ask("Image directory"))
            pred_csv = Path(Prompt.ask("Predictions CSV"))
            out_csv = Path(Prompt.ask("Output feedback CSV"))
            launch_feedback_gui(img_dir, pred_csv, out_csv)
        else:
            console.print("Goodbye!", style="bold green")
            break


if __name__ == "__main__":
    run_dashboard()
