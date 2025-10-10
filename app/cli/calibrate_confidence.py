"""Calibrate detection confidence with human feedback."""
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt

from ..analysis.confidence_calibrator import calibrate_confidence
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG

def _t(text: str) -> str:
    """Translate UI text."""
    return translate_text(text, target_lang=_LANG)

def run_confidence_calibration() -> None:
    """Fit an isotonic-regression calibration model from feedback."""
    feedback = Path(Prompt.ask(_t("Feedback CSV")))
    out_model = Path(Prompt.ask(_t("Output model"), default="calibration.npz"))
    calibrate_confidence(feedback, out_model)
    console.print(_t("Calibration saved"), style="green")

if __name__ == "__main__":
    run_confidence_calibration()
