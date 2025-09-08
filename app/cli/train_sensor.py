"""Train a sensor-data classifier from feature CSV files."""
from __future__ import annotations

import argparse
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt

from ..config import settings
from ..translation import translate_text
from ..training import (
    train_sensor_model,
    auto_train_directory,
    train_pointcloud_classifier,
)

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_sensor_training(
    csv_path: Path | None = None,
    output: Path | None = None,
    directory: Path | None = None,
    image_dir: Path | None = None,
    labels: Path | None = None,
) -> None:
    """Train sensor or point-cloud classifiers from various inputs."""

    if directory is not None:
        models = auto_train_directory(directory, output)
        console.print(
            _t("Trained {count} models in {dir}").format(count=len(models), dir=str(directory)),
            style="green",
        )
        return

    if image_dir is not None and labels is not None:
        if output is None:
            output = Path(
                Prompt.ask(_t("Output model path"), default="pointcloud_model.joblib")
            )
        model_path = train_pointcloud_classifier(image_dir, labels, output)
        console.print(
            _t("Saved model to {path}").format(path=str(model_path)), style="green"
        )
        return

    if csv_path is None:
        csv_path = Path(Prompt.ask(_t("Path to sensor CSV"), default="sensor.csv"))
    if output is None:
        output = Path(Prompt.ask(_t("Output model path"), default="sensor_model.joblib"))
    model_path = train_sensor_model(csv_path, output)
    console.print(_t("Saved model to {path}").format(path=str(model_path)), style="green")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=_t("Train sensor classifier"), add_help=True)
    parser.add_argument("--data", type=str, help=_t("Path to sensor CSV"))
    parser.add_argument("--out", type=str, help=_t("Output model path or directory"))
    parser.add_argument("--dir", type=str, help=_t("Train all CSVs in directory"))
    parser.add_argument("--images", type=str, help=_t("Directory of training images"))
    parser.add_argument("--labels", type=str, help=_t("CSV mapping image filenames to labels"))
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_sensor_training(
        Path(args.data) if args.data else None,
        Path(args.out) if args.out else None,
        Path(args.dir) if args.dir else None,
        Path(args.images) if args.images else None,
        Path(args.labels) if args.labels else None,
    )
