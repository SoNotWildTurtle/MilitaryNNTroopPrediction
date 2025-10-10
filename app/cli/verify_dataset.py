"""CLI to check that every image has a matching label file."""
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..training.verify_dataset import verify_dataset
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    """Translate static UI text if a non-English language is configured."""
    return translate_text(text, target_lang=_LANG)


def run_verify_dataset() -> None:
    """Prompt for a dataset path and display missing images or labels."""
    dataset = Prompt.ask(_t("Dataset directory"), default="data")
    result = verify_dataset(dataset)
    table = Table(title=_t("Dataset verification"))
    table.add_column(_t("Issue"))
    table.add_column(_t("Count"), justify="right")
    table.add_row(_t("Images without labels"), str(len(result["missing_labels"])))
    table.add_row(_t("Labels without images"), str(len(result["missing_images"])))
    console.print(table)


if __name__ == "__main__":
    run_verify_dataset()
