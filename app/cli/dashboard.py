"""Rich-based CLI providing a simple text dashboard."""
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional
import numpy as np
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
    uncertainty_heatmap,
    prediction_correlation,
    object_speed_summary,
)
from ..utils.human_feedback_viewer import launch_feedback_gui
from ..utils.twilio_alerts import (
    send_alert as send_twilio_alert,
    is_configured as twilio_is_configured,
    TwilioConfigurationError,
)
from ..cli.configure import run_config_setup
from ..cli.report import run_detection_report
from ..cli.control_center import run_control_center_cli
from ..cli.coanalysis_report import run_coanalysis_report
from ..cli.acceleration_report import run_acceleration_report
from ..cli.speed_report import run_speed_report
from ..cli.diversity_report import run_diversity_report
from ..cli.streak_report import run_streak_report
from ..cli.volatility_report import run_volatility_report
from ..cli.activity_report import run_activity_report
from ..cli.interarrival_report import run_interarrival_report
from ..cli.trend_report import run_trend_report
from ..cli.peak_report import run_peak_report
from ..cli.anomaly_report import run_anomaly_report
from ..cli.burst_report import run_burst_report
from ..cli.changepoint_report import run_changepoint_report
from ..cli.cooccurrence_report import run_cooccurrence_report
from ..cli.lag_report import run_lag_report
from ..cli.moving_report import run_moving_report
from ..cli.weekly_report import run_weekly_report
from ..cli.confidence_report import run_confidence_report
from ..cli.export_geojson import run_geojson_export
from ..cli.method_cohesion_report import run_method_cohesion_report
from ..cli.doctrine_movement_report import run_doctrine_movement_report
from ..cli.next_gen_recommendations import run_next_gen_recommendations
from ..drones import live_feed
from ..info_gathering import camera_collector
from ..info_gathering.source_catalog import SourceCatalog
from ..info_gathering.source_finder import _ask_chatgpt
from ..training import auto_dataset_train, hyperparameter_search
from ..cli.train_wizard import run_train_wizard
from ..cli.self_reinforce import self_reinforce
from ..cli.train_sensor_pointcloud import run_sensor_pointcloud_training
from ..cli.verify_dataset import run_verify_dataset
from ..cli.generate_demo_data import run_demo_data_generator
from ..cli.calibrate_confidence import run_confidence_calibration
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


def _run_source_discovery() -> None:
    """Ask ChatGPT for imagery feeds and store them in the catalog."""
    prompt = Prompt.ask(_t("Discovery prompt"))
    verify = Prompt.ask(_t("Verify URLs? (y/n)"), default="y").lower().startswith("y")
    catalog = SourceCatalog()
    sources = _ask_chatgpt(prompt)
    if not sources:
        console.print(_t("No sources found"), style="yellow")
        return
    added = catalog.add(sources, verify=verify)
    table = Table(show_header=True, box=box.ROUNDED)
    table.add_column(_t("Source"))
    for src in added:
        table.add_row(src)
    console.print(Panel(table, title=_t("Stored sources"), border_style="green"))


def _list_sources() -> None:
    """Display all known imagery sources."""
    catalog = SourceCatalog()
    sources = catalog.all()
    if not sources:
        console.print(_t("No sources recorded"), style="yellow")
        return
    table = Table(show_header=True, box=box.ROUNDED)
    table.add_column(_t("Source"))
    for src in sources:
        table.add_row(src)
    console.print(Panel(table, title=_t("Known sources"), border_style="green"))


def _run_prediction_correlation() -> None:
    """Prompt for predictions JSON and display correlation matrix."""
    json_path = Path(Prompt.ask(_t("Predictions JSON")))
    matrix = prediction_correlation.prediction_correlations(json_path)
    models = list(matrix.keys())
    table = Table(title=_t("Prediction correlation"), box=box.ROUNDED)
    table.add_column(_t("Model"))
    for m in models:
        table.add_column(m, justify="right")
    for m1 in models:
        row = [m1]
        for m2 in models:
            val = matrix[m1][m2]
            row.append("nan" if np.isnan(val) else f"{val:.2f}")
        table.add_row(*row)
    console.print(table)


def _run_sensor_reliability() -> None:
    """Display current sensor weights."""
    table = Table(title=_t("Sensor reliability"), box=box.ROUNDED)
    table.add_column(_t("Sensor"))
    table.add_column(_t("Weight"), justify="right")
    table.add_row("camera", f"{settings.CAMERA_WEIGHT:.2f}")
    table.add_row("lidar", f"{settings.LIDAR_WEIGHT:.2f}")
    table.add_row("bluetooth", f"{settings.BLUETOOTH_WEIGHT:.2f}")
    console.print(table)


def _object_type_menu() -> Optional[str]:
    """Allow operators to pick an object class for drilldown analytics."""

    options = {
        "1": ("armor", _t("Armor / ground vehicles")),
        "2": ("aircraft", _t("Aircraft")),
        "3": ("drone", _t("Drones / UAVs")),
        "0": (None, _t("Back")),
    }
    table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    table.add_column(_t("Key"), justify="center", style="bold cyan")
    table.add_column(_t("Object"), style="magenta")
    for key, (_, label) in options.items():
        table.add_row(key, label)
    console.print(Panel(table, title=_t("Select object type"), border_style="cyan"))
    choice = Prompt.ask(_t("Choice"), choices=list(options.keys()), default="0")
    return options[choice][0]


def _run_object_drilldown() -> None:
    """Generate a drilldown report and optionally send Twilio alerts."""

    obj_type = _object_type_menu()
    if not obj_type:
        return
    start, end, hours = _get_time_filters()
    metric_prompt = _t(
        "Metrics (comma separated: avg,max,distance,duration,samples)"
    )
    metric_input = Prompt.ask(metric_prompt, default="avg,max,distance,duration")
    metrics = [m.strip().lower() for m in metric_input.split(",") if m.strip()]
    if not metrics:
        metrics = ["avg", "max", "distance", "duration"]

    summary = object_speed_summary(obj_type, hours or 24, start=start, end=end)
    rows = summary.get("rows", [])
    if not rows:
        console.print(
            _t("No movement records found for this object type and timeframe."),
            style="yellow",
        )
        return

    metric_columns = {
        "avg": (_t("Avg speed (km/h)"), lambda r: f"{r['avg_speed_kmh']:.2f}"),
        "max": (_t("Max speed (km/h)"), lambda r: f"{r['max_speed_kmh']:.2f}"),
        "distance": (_t("Distance (km)"), lambda r: f"{r['distance_km']:.2f}"),
        "duration": (_t("Hours tracked"), lambda r: f"{r['duration_hours']:.2f}"),
        "samples": (_t("Samples"), lambda r: str(r.get("samples", 0))),
    }

    table = Table(show_header=True, box=box.ROUNDED, padding=(0, 1))
    table.add_column(_t("Unit ID"), style="cyan")
    ordered_metrics = []
    for metric in metrics:
        if metric in metric_columns and metric not in ordered_metrics:
            header, _ = metric_columns[metric]
            justify = "right" if metric != "samples" else "center"
            table.add_column(header, justify=justify)
            ordered_metrics.append(metric)
    if "samples" not in ordered_metrics:
        header, _ = metric_columns["samples"]
        table.add_column(header, justify="center")
        ordered_metrics.append("samples")

    for row in rows:
        values = [row["unit_id"]]
        for metric in ordered_metrics:
            _, formatter = metric_columns[metric]
            values.append(formatter(row))
        table.add_row(*values)

    console.print(Panel(table, title=_t("Object drilldown"), border_style="cyan"))
    summary_line = _t(
        "Overall average speed: {speed:.2f} km/h across {count} units"
    ).format(
        speed=summary.get("overall_avg_speed_kmh", 0.0),
        count=summary.get("total_units", 0),
    )
    console.print(summary_line, style="green")

    if not Prompt.ask(
        _t("Send SMS alert with this summary? (y/n)"), default="n"
    ).lower().startswith("y"):
        return

    if not twilio_is_configured():
        console.print(
            _t("Twilio credentials are not configured; cannot send alerts."),
            style="red",
        )
        return

    numbers = Prompt.ask(
        _t("Phone numbers (comma separated, include country codes)"), default=""
    )
    recipients = [n.strip() for n in numbers.split(",") if n.strip()]
    if not recipients:
        console.print(_t("No phone numbers provided; skipping alerts."), style="yellow")
        return

    default_message = _t(
        "{object_type} summary: overall average speed {speed:.2f} km/h across {count} units."
    ).format(
        object_type=obj_type,
        speed=summary.get("overall_avg_speed_kmh", 0.0),
        count=summary.get("total_units", 0),
    )
    message = Prompt.ask(_t("Message body"), default=default_message)
    try:
        results = send_twilio_alert(message, recipients)
    except TwilioConfigurationError as exc:
        console.print(
            _t("Unable to send alerts: {error}").format(error=str(exc)),
            style="red",
        )
        return

    status_table = Table(show_header=True, box=box.ROUNDED, padding=(0, 1))
    status_table.add_column(_t("Phone"))
    status_table.add_column(_t("Status"))
    for phone, status in results.items():
        status_table.add_row(phone, status)
    console.print(Panel(status_table, title=_t("Twilio delivery status"), border_style="green"))


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
    table.add_row("o", _t("Object drilldown & alerts"))
    table.add_row("a", _t("Analysis reports"))
    table.add_row("c", _t("Coanalysis report"))
    table.add_row("x", _t("Launch control centre"))
    table.add_row("d", _t("Discover image sources"))
    table.add_row("i", _t("List image sources"))
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
            "o",
            "a",
            "c",
            "d",
            "i",
            "s",
            "h",
            "l",
            "x",
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
            target_model = Prompt.ask(_t("Unified classifier"), default="")
            classify_opt = Prompt.ask(_t("Run unified classifier? (y/n)"), default="n")
            live_feed.stream(
                int(source) if source.isdigit() else source,
                troop_model_path=troop_model or None,
                target_model_path=target_model or None,
                classify_targets=classify_opt.lower().startswith("y"),
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
        elif choice == "o":
            _run_object_drilldown()
        elif choice == "a":
            _analysis_menu_loop()
        elif choice == "c":
            run_coanalysis_report()
        elif choice == "d":
            _run_source_discovery()
        elif choice == "i":
            _list_sources()
        elif choice == "s":
            _show_config_summary()
        elif choice == "h":
            _show_help()
        elif choice == "l":
            _change_language()
        elif choice == "x":
            run_control_center_cli()
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
    table.add_row("7", _t("Uncertainty heatmap"))
    table.add_row("8", _t("Export GeoJSON"))
    table.add_row("0", _t("Back"))
    console.print(Panel(table, title=_t("Map & analysis"), border_style="cyan"))
    return Prompt.ask(
        _t("Choice"), choices=["1", "2", "3", "4", "5", "6", "7", "8", "0"], default="0"
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
        elif choice == "7":
            area = Prompt.ask(_t("Area name"))
            start, end, hours = _get_time_filters()
            threshold = float(Prompt.ask(_t("Confidence threshold"), default="0.8"))
            output = Prompt.ask(
                _t("Output file"), default=f"{area}_uncertainty.png"
            )
            uncertainty_heatmap.generate_uncertainty_heatmap(
                area,
                hours or 24,
                threshold=threshold,
                output=Path(output),
                start=start,
                end=end,
            )
        elif choice == "8":
            area = Prompt.ask(_t("Area name"))
            limit = int(Prompt.ask(_t("Number of records"), default="100"))
            output = Prompt.ask(
                _t("Output file"), default="detections.geojson"
            )
            run_geojson_export(area, output, limit)
        else:
            break


def _analysis_menu() -> str:
    """Display the analysis reports submenu and return the user's choice."""
    table = Table(show_header=False, box=box.ROUNDED, padding=(0, 1))
    table.add_column(_t("Key"), justify="center", style="bold cyan")
    table.add_column(_t("Action"), style="magenta")
    table.add_row("1", _t("Acceleration anomalies"))
    table.add_row("2", _t("Speed anomalies"))
    table.add_row("3", _t("Class diversity"))
    table.add_row("4", _t("Detection streaks"))
    table.add_row("5", _t("Detection volatility"))
    table.add_row("6", _t("Hourly activity"))
    table.add_row("7", _t("Interarrival times"))
    table.add_row("8", _t("Detection trends"))
    table.add_row("9", _t("Peak detection times"))
    table.add_row("10", _t("Detection anomalies"))
    table.add_row("11", _t("Detection bursts"))
    table.add_row("12", _t("Change points"))
    table.add_row("13", _t("Class co-occurrence"))
    table.add_row("14", _t("Lag correlation"))
    table.add_row("15", _t("Moving averages"))
    table.add_row("16", _t("Weekly activity"))
    table.add_row("17", _t("Confidence summary"))
    table.add_row("18", _t("Prediction correlation"))
    table.add_row("19", _t("Sensor reliability"))
    table.add_row("20", _t("Cross-method cohesion"))
    table.add_row("21", _t("Doctrine movement drilldown"))
    table.add_row("22", _t("Next-gen recommendations"))
    table.add_row("0", _t("Back"))
    console.print(Panel(table, title=_t("Analysis reports"), border_style="cyan"))
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
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "17",
            "18",
            "19",
            "20",
            "21",
            "22",
            "0",
        ],
        default="0",
    )


def _analysis_menu_loop() -> None:
    """Loop over analysis report options until the user exits."""
    while True:
        choice = _analysis_menu()
        if choice == "1":
            run_acceleration_report()
        elif choice == "2":
            run_speed_report()
        elif choice == "3":
            run_diversity_report()
        elif choice == "4":
            run_streak_report()
        elif choice == "5":
            run_volatility_report()
        elif choice == "6":
            run_activity_report()
        elif choice == "7":
            run_interarrival_report()
        elif choice == "8":
            run_trend_report()
        elif choice == "9":
            run_peak_report()
        elif choice == "10":
            run_anomaly_report()
        elif choice == "11":
            run_burst_report()
        elif choice == "12":
            run_changepoint_report()
        elif choice == "13":
            run_cooccurrence_report()
        elif choice == "14":
            run_lag_report()
        elif choice == "15":
            run_moving_report()
        elif choice == "16":
            run_weekly_report()
        elif choice == "17":
            run_confidence_report()
        elif choice == "18":
            _run_prediction_correlation()
        elif choice == "19":
            _run_sensor_reliability()
        elif choice == "20":
            run_method_cohesion_report()
        elif choice == "21":
            run_doctrine_movement_report()
        elif choice == "22":
            run_next_gen_recommendations()
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
    table.add_row("5", _t("Sensor pointcloud trainer"))
    table.add_row("6", _t("Calibrate confidence"))
    table.add_row("7", _t("Verify dataset"))
    table.add_row("8", _t("Generate demo data"))
    table.add_row("0", _t("Back"))
    console.print(Panel(table, title=_t("Training menu"), border_style="cyan"))
    return Prompt.ask(
        _t("Choice"),
        choices=["1", "2", "3", "4", "5", "6", "7", "8", "0"],
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
        elif choice == "5":
            _run_sensor_pointcloud_training()
        elif choice == "6":
            run_confidence_calibration()
        elif choice == "7":
            run_verify_dataset()
        elif choice == "8":
            run_demo_data_generator()
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


def _run_sensor_pointcloud_training() -> None:
    """Prompt for paths and run sensor pointcloud training."""
    csv_path = Path(Prompt.ask(_t("Sensor CSV")))
    image_dir = Path(Prompt.ask(_t("Image directory")))
    out_model = Path(
        Prompt.ask(_t("Output model"), default="sensor_pointcloud_model.joblib")
    )
    run_sensor_pointcloud_training(csv_path, image_dir, out_model)


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
