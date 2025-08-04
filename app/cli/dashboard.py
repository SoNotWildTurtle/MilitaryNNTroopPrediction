"""Rich-based CLI providing a simple text dashboard."""
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from rich.panel import Panel

from ..pipeline import realtime, monitor
from ..analysis import heatmap
from ..utils.human_feedback_viewer import launch_feedback_gui
from ..config import settings
from ..translation import translate_text


console = Console()

_LANG = settings.UI_LANG

def _t(text: str) -> str:
    """Translate static UI text if a non-English language is configured."""
    return translate_text(text, target_lang=_LANG)


def run_dashboard() -> None:
    """Launch an interactive CLI for common tasks."""
    console.print(Panel(_t("Troop Analysis Dashboard"), style="bold cyan"))
    while True:
        console.print(_t("\n[1] Run pipeline once"))
        console.print(_t("[2] Monitor area continuously"))
        console.print(_t("[3] Generate heatmap"))
        console.print(_t("[4] Launch feedback GUI"))
        console.print(_t("[5] Exit"))
        choice = Prompt.ask(_t("Select option"), choices=["1", "2", "3", "4", "5"], default="5")
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
            area = Prompt.ask(_t("Area name"))
            hours = int(Prompt.ask(_t("Hours"), default="24"))
            output = Prompt.ask(_t("Output file"), default=f"{area}_heatmap.png")
            heatmap.generate_heatmap(area, hours, output=Path(output))
        elif choice == "4":
            img_dir = Path(Prompt.ask(_t("Image directory")))
            pred_csv = Path(Prompt.ask(_t("Predictions CSV")))
            out_csv = Path(Prompt.ask(_t("Output feedback CSV")))
            launch_feedback_gui(img_dir, pred_csv, out_csv)
        else:
            console.print(_t("Goodbye!"), style="bold green")
            break


if __name__ == "__main__":
    run_dashboard()
