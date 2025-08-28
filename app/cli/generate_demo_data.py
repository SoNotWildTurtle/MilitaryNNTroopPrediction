"""CLI to create a synthetic dataset for offline demonstrations."""
from rich.prompt import Prompt
from rich.console import Console

from ..utils.demo_dataset import generate_demo_dataset
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate static UI text if a non-English language is configured."""
    return translate_text(text, target_lang=_LANG)


def run_demo_data_generator() -> None:
    """Prompt for output directory and image count then generate demo data."""
    out_dir = Prompt.ask(_t("Output directory"), default="demo_data")
    num_images = int(Prompt.ask(_t("Number of images"), default="10"))
    generate_demo_dataset(out_dir, num_images=num_images)
    console.print(_t("Demo dataset created"), style="green")


if __name__ == "__main__":
    run_demo_data_generator()
