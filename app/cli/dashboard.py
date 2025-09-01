"""Rich-based CLI providing a simple text dashboard."""
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel
from rich import box

from ..pipeline import realtime, monitor
from ..analysis import (
    heatmap,
    geo_mapper,
    meta_analysis,
    movement_stats,
    cluster_strategy_tracker,
    threat_assessment,
)
from ..utils.human_feedback_viewer import launch_feedback_gui
from ..cli.configure import run_config_setup
from ..cli.report import run_detection_report
from ..drones import live_feed
from ..info_gathering import camera_collector
from ..training import auto_dataset_train, hyperparameter_search
from ..cli.train_wizard import run_train_wizard
from ..cli.self_reinforce import self_reinforce
from ..config import settings
from ..translation import translate_text


console = Console()

_LANG = settings.UI_LANG

def _t(text: str) -> str:
    """Translate static UI text if a non-English language is configured."""
    return translate_text(text, target_lang=_LANG)


def _get_time_filters():
    """Prompt the user for a date range or hours lookback."""
    start_str = Prompt.ask(_t("Start date (YYYY-MM-DD, optional)"), default="")
    end_str = Prompt.ask(_t("End date (YYYY-MM-DD, optional)"), default="")
    if start_str or end_str:
        start_dt = datetime.fromisoformat(start_str) if start_str else None
        end_dt = datetime.fromisoformat(end_str) if end_str else None
        return start_dt, end_dt, None
    hours = int(Prompt.ask(_t("Hours"), default="24"))
    return None, None, hours


def _show_help() -> None:
    """Display a brief help message for operators."""
    msg = _t(
        "Use this dashboard to run detection pipelines, monitor areas, stream drone feeds, capture frames, "
        "launch analysis tools, handle training tasks, configure environment values, and review detection reports."
    )
    console.print(Panel(msg, title=_t("Help"), border_style="green"))


def _change_language() -> None:
    """Prompt the operator to switch UI language at runtime."""
    global _LANG
    lang = Prompt.ask(_t("Language code"), choices=["en", "uk"], default=_LANG)
    _LANG = lang
    console.print(_t("Language set to " ) + lang)


def _show_config_summary() -> None:
    """Display current non-secret configuration values."""
    cfg = settings.as_dict()
    table = Table(show_header=True, box=box.ROUNDED, padding=(0, 1))
    table.add_column(_t("Setting"), style="cyan")
    table.add_column(_t("Value"), style="magenta")
    for key, val in cfg.items():
        if any(s in key.lower() for s in ["secret", "key"]):
            val = "******" if val else ""
        table.add_row(key, str(val))
    console.print(Panel(table, title=_t("Configuration"), border_style="green"))


def _menu() -> str:
    """Display the dashboard menu and return the user's choice."""
    table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    table.add_column(_t("Key"), justify="center", style="bold cyan")
    table.add_column(_t("Action"), style="magenta")
    table.add_row("1", _t("Run pipeline once"))
    table.add_row("2", _t("Monitor area continuously"))
    table.add_row("3", _t("Stream drone feed"))
    table.add_row("4", _t("Capture camera frames"))
    table.add_row("5", _t("Map and analysis tools"))
    table.add_row("6", _t("Launch feedback GUI"))
    table.add_row("7", _t("Training tasks"))
    table.add_row("8", _t("Configure environment"))
    table.add_row("9", _t("Detection report"))
    table.add_row("s", _t("Show configuration"))
    table.add_row("h", _t("Help / about"))
    table.add_row("l", _t("Switch language"))
    table.add_row("0", _t("Exit"))
    console.print(Panel(table, title=_t("Main menu"), border_style="cyan"))
    return Prompt.ask(
        _t("Choice"),
        choices=[
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "s",
            "h",
            "l",
            "0",
        ],
        default="0",
    )


def run_dashboard(lang: Optional[str] = None) -> None:
    """Launch an interactive CLI for common tasks.

    Args:
        lang: Optional language code ("en" or "uk") to override the
            ``UI_LANG`` environment setting.
    """
    global _LANG
    if lang:
        _LANG = lang
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
            _map_menu_loop()
        elif choice == "6":
            img_dir = Path(Prompt.ask(_t("Image directory")))
            pred_csv = Path(Prompt.ask(_t("Predictions CSV")))
            out_csv = Path(Prompt.ask(_t("Output feedback CSV")))
            launch_feedback_gui(img_dir, pred_csv, out_csv)
        elif choice == "7":
            _training_menu_loop()
        elif choice == "8":
            run_config_setup()
        elif choice == "9":
            run_detection_report()
        elif choice == "s":
            _show_config_summary()
        elif choice == "h":
            _show_help()
        elif choice == "l":
            _change_language()
        elif choice == "0":
            console.print(_t("Goodbye!"), style="bold green")
            break


def _map_menu() -> str:
    """Display the map/analysis submenu and return the user's choice."""
    table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    table.add_column(_t("Key"), justify="center", style="bold cyan")
    table.add_column(_t("Action"), style="magenta")
    table.add_row("1", _t("Generate detection map"))
    table.add_row("2", _t("Generate heatmap"))
    table.add_row("3", _t("Cluster unit movements"))
    table.add_row("4", _t("Run meta analysis"))
    table.add_row("5", _t("Unit movement stats"))
    table.add_row("6", _t("Threat assessment"))
    table.add_row("0", _t("Back"))
    console.print(Panel(table, title=_t("Map & analysis"), border_style="cyan"))
    return Prompt.ask(
        _t("Choice"), choices=["1", "2", "3", "4", "5", "6", "0"], default="0"
    )


def _map_menu_loop() -> None:
    """Loop over map and analysis options until the user exits."""
    while True:
        choice = _map_menu()
        if choice == "1":
            area = Prompt.ask(_t("Area name"))
            start, end, hours = _get_time_filters()
            output = Prompt.ask(
                _t("Output HTML"), default=f"{area}_map.html"
            )
            geo_mapper.map_detections(area, hours or 24, Path(output), start=start, end=end)
        elif choice == "2":
            area = Prompt.ask(_t("Area name"))
            start, end, hours = _get_time_filters()
            output = Prompt.ask(
                _t("Output file"), default=f"{area}_heatmap.png"
            )
            heatmap.generate_heatmap(area, hours or 24, output=Path(output), start=start, end=end)
        elif choice == "3":
            unit = Prompt.ask(_t("Unit ID"))
            start, end, hours = _get_time_filters()
            clusters = cluster_strategy_tracker.analyze_unit(unit, hours or 24, start=start, end=end)
            if clusters:
                console.print_json(data=clusters)
        elif choice == "4":
            start, end, hours = _get_time_filters()
            report = meta_analysis.meta_analysis(hours or 24, start=start, end=end)
            console.print_json(data=report)
        elif choice == "5":
            unit = Prompt.ask(_t("Unit ID"))
            start, end, hours = _get_time_filters()
            stats = movement_stats.movement_stats(unit, hours or 24, start=start, end=end)
            if stats:
                console.print_json(data=stats)
        elif choice == "6":
            unit = Prompt.ask(_t("Unit ID"))
            start, end, hours = _get_time_filters()
            clusters = cluster_strategy_tracker.analyze_unit(unit, hours or 24, start=start, end=end)
            if clusters:
                scores = threat_assessment.score_clusters(clusters)
                console.print_json(data=scores)
        else:
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


def _training_menu() -> str:
    """Display the training submenu and return the user's choice."""
    table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    table.add_column(_t("Key"), justify="center", style="bold cyan")
    table.add_column(_t("Action"), style="magenta")
    table.add_row("1", _t("Run training wizard"))
    table.add_row("2", _t("Self-reinforce dataset"))
    table.add_row("3", _t("Auto dataset trainer"))
    table.add_row("4", _t("Hyperparameter search"))
    table.add_row("0", _t("Back"))
    console.print(Panel(table, title=_t("Training menu"), border_style="cyan"))
    return Prompt.ask(
        _t("Choice"),
        choices=["1", "2", "3", "4", "0"],
        default="0",
    )


def _training_menu_loop() -> None:
    """Loop over the training submenu until the user exits."""
    while True:
        choice = _training_menu()
        if choice == "1":
            run_train_wizard()
        elif choice == "2":
            _run_self_reinforce()
        elif choice == "3":
            _run_auto_dataset_trainer()
        elif choice == "4":
            _run_hyperparameter_search()
        else:
            break


def _run_auto_dataset_trainer() -> None:
    """Prompt for parameters and run the auto dataset trainer."""
    dataset_dir = Path(Prompt.ask(_t("Dataset directory")))
    classes = Prompt.ask(_t("Classes (space separated)"), default="troop vehicle").split()
    out_model = Path(Prompt.ask(_t("Output model file"), default="auto_model.pt"))
    val_split = float(Prompt.ask(_t("Validation split"), default="0.2"))
    augment = Prompt.ask(_t("Augment data? (y/n)"), default="y").lower().startswith("y")
    epochs = int(Prompt.ask(_t("Epochs"), default="50"))
    auto_dataset_train(
        dataset_dir,
        classes,
        out_model,
        val_split=val_split,
        augment=augment,
        epochs=epochs,
    )


def _run_hyperparameter_search() -> None:
    """Prompt for parameters and run the hyperparameter search."""
    train_dir = Path(Prompt.ask(_t("Training directory")))
    val_dir = Path(Prompt.ask(_t("Validation directory")))
    classes = Prompt.ask(_t("Classes (space separated)"), default="troop vehicle").split()
    epochs = int(Prompt.ask(_t("Epochs"), default="25"))
    out_dir = Path(Prompt.ask(_t("Output directory"), default="hparam_runs"))
    batches = [int(b) for b in Prompt.ask(_t("Batch sizes"), default="16").split()]
    lrs = [float(l) for l in Prompt.ask(_t("Learning rates"), default="0.001 0.0001").split()]
    img_sizes = [int(i) for i in Prompt.ask(_t("Image sizes"), default="640").split()]
    hyperparameter_search(
        train_dir,
        val_dir,
        classes,
        epochs,
        out_dir,
        batches=batches,
        lrs=lrs,
        img_sizes=img_sizes,
    )


def main() -> None:
    """Entry point supporting command-line arguments."""
    parser = argparse.ArgumentParser(description="Interactive dashboard")
    parser.add_argument(
        "--lang", choices=["en", "uk"], default=settings.UI_LANG,
        help="UI language for prompts",
    )
    args = parser.parse_args()
    run_dashboard(lang=args.lang)


if __name__ == "__main__":
    main()
