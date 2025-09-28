"""CLI for training sensor models with image-derived point clouds."""
from __future__ import annotations

import argparse
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt

from ..config import settings
from ..translation import translate_text
from ..training.sensor_pointcloud_trainer import train_sensor_pointcloud_model

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_sensor_pointcloud_training(
    csv_path: Path | None = None,
    image_dir: Path | None = None,
    model_path: Path | None = None,
) -> None:
    """Prompt for paths and train the fused sensor model."""
    if csv_path is None:
        csv_path = Path(Prompt.ask(_t("Sensor CSV")))
    if image_dir is None:
        image_dir = Path(Prompt.ask(_t("Image directory")))
    if model_path is None:
        model_path = Path(Prompt.ask(_t("Output model"), default="sensor_pointcloud_model.joblib"))

    train_sensor_pointcloud_model(csv_path, image_dir, model_path)
    console.print(
        _t("Saved model to {path}").format(path=str(model_path)), style="green"
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=_t("Train sensor model with image point clouds"), add_help=True
    )
    parser.add_argument("--csv", type=str, help=_t("Sensor CSV"))
    parser.add_argument("--images", type=str, help=_t("Image directory"))
    parser.add_argument("--out", type=str, help=_t("Output model"))
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_sensor_pointcloud_training(
        Path(args.csv) if args.csv else None,
        Path(args.images) if args.images else None,
        Path(args.out) if args.out else None,
    )
