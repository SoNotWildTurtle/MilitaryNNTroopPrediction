"""Rich-based CLI providing a simple text dashboard."""
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
from rich import box

from ..pipeline import realtime, monitor
from ..analysis import heatmap
from ..utils.human_feedback_viewer import launch_feedback_gui
from ..cli.train_wizard import run_train_wizard
from ..cli.configure import run_config_setup
from ..cli.self_reinforce import self_reinforce
from ..cli.report import run_detection_report
from ..drones import live_feed
from ..info_gathering import camera_collector
from ..config import settings
from ..translation import translate_text


console = Console()

_LANG = settings.UI_LANG

def _t(text: str) -> str:
    """Translate static UI text if a non-English language is configured."""
    return translate_text(text, target_lang=_LANG)


def _menu() -> str:
    """Display the dashboard menu and return the user's choice."""
    table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    table.add_column(_t("Key"), justify="center", style="bold cyan")
    table.add_column(_t("Action"), style="magenta")
    table.add_row("1", _t("Run pipeline once"))
    table.add_row("2", _t("Monitor area continuously"))
    table.add_row("3", _t("Stream drone feed"))
    table.add_row("4", _t("Capture camera frames"))
    table.add_row("5", _t("Generate heatmap"))
    table.add_row("6", _t("Launch feedback GUI"))
    table.add_row("7", _t("Run training wizard"))
    table.add_row("8", _t("Self-reinforce dataset"))
    table.add_row("9", _t("Configure environment"))
    table.add_row("10", _t("Detection report"))
    table.add_row("0", _t("Exit"))
    console.print(Panel(table, title=_t("Main menu"), border_style="cyan"))
    return Prompt.ask(
        _t("Choice"),
        choices=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "0"],
        default="0",
    )


def run_dashboard() -> None:
    """Launch an interactive CLI for common tasks."""
    console.print(Panel(_t("Troop Analysis Dashboard"), style="bold cyan"))
    while True:
        choice = _menu()
        if choice == "1":
            area = Prompt.ask(_t("Area name"))
            model = Prompt.ask(_t("Trajectory model"), default="models/trajectory.h5")
            realtime.process_area(area, model)
        elif choice == "2":
            area = Prompt.ask(_t("Area name"))
            model = Prompt.ask(_t("Trajectory model"), default="models/trajectory.h5")
            interval = int(Prompt.ask(_t("Interval seconds"), default="300"))
            console.print(_t("Press Ctrl+C to stop monitoring"))
            try:
                monitor.monitor(area, model, interval)
            except KeyboardInterrupt:
                console.print(_t("Monitoring stopped"))
        elif choice == "3":
            source = Prompt.ask(_t("Video source"), default="0")
            troop_model = Prompt.ask(_t("Troop classifier"), default="")
            drones_opt = Prompt.ask(_t("Classify drones? (y/n)"), default="n")
            vehicles_opt = Prompt.ask(_t("Classify vehicles? (y/n)"), default="n")
            live_feed.stream(
                int(source) if source.isdigit() else source,
                troop_model_path=troop_model or None,
                classify_drones=drones_opt.lower().startswith("y"),
                classify_vehicles=vehicles_opt.lower().startswith("y"),
            )
        elif choice == "4":
            source = Prompt.ask(_t("Camera source"), default="0")
            out_dir = Path(Prompt.ask(_t("Output directory"), default="captures"))
            interval = int(Prompt.ask(_t("Interval seconds"), default="5"))
            camera_collector.capture_frames(
                int(source) if source.isdigit() else source, out_dir, interval
            )
        elif choice == "5":
            area = Prompt.ask(_t("Area name"))
            hours = int(Prompt.ask(_t("Hours"), default="24"))
            output = Prompt.ask(_t("Output file"), default=f"{area}_heatmap.png")
            heatmap.generate_heatmap(area, hours, output=Path(output))
        elif choice == "6":
            img_dir = Path(Prompt.ask(_t("Image directory")))
            pred_csv = Path(Prompt.ask(_t("Predictions CSV")))
            out_csv = Path(Prompt.ask(_t("Output feedback CSV")))
            launch_feedback_gui(img_dir, pred_csv, out_csv)
        elif choice == "7":
            run_train_wizard()
        elif choice == "8":
            _run_self_reinforce()
        elif choice == "9":
            run_config_setup()
        elif choice == "10":
            run_detection_report()
        else:
            console.print(_t("Goodbye!"), style="bold green")
            break


def _run_self_reinforce() -> None:
    """Prompt for paths and run the self-reinforcement helper."""
    new_images = Path(Prompt.ask(_t("New images directory")))
    train_dir = Path(Prompt.ask(_t("Training images directory"), default="data/train/images"))
    val_dir = Path(Prompt.ask(_t("Validation images directory"), default="data/val/images"))
    classes = Prompt.ask(_t("Classes (space separated)"), default="troop vehicle").split()
    out_model = Path(Prompt.ask(_t("Output model file"), default="self_model.pt"))
    epochs = int(Prompt.ask(_t("Epochs"), default="10"))
    model = Prompt.ask(_t("Existing model for labeling (optional)"), default="")
    model_path = Path(model) if model else None
    self_reinforce(new_images, train_dir, val_dir, classes, out_model, epochs, model_path=model_path)


if __name__ == "__main__":
    run_dashboard()
