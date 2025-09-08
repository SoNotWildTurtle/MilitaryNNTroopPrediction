"""CLI to train a PointNet-Gaussian model."""
from __future__ import annotations

import argparse

from ..training.pointnet_gaussian_trainer import train_pointnet_gaussian_model
from ..translation import translate_text
from ..config import settings

_LANG = settings.UI_LANG

def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_pointnet_gaussian_training() -> None:
    parser = argparse.ArgumentParser(
        description=_t("Train PointNet-Gaussian model from labeled point clouds")
    )
    parser.add_argument("csv", help=_t("CSV file with x,y,z,label columns"))
    parser.add_argument("--epochs", type=int, default=5, help=_t("Training epochs"))
    parser.add_argument(
        "--model",
        default="pointnet_encoder.pt",
        help=_t("Output encoder weights"),
    )
    parser.add_argument(
        "--stats",
        default="pointnet_gaussian_model.json",
        help=_t("Output Gaussian stats JSON"),
    )
    args = parser.parse_args()

    model_path, stats_path = train_pointnet_gaussian_model(
        args.csv, args.model, args.stats, args.epochs
    )
    print(
        _t("Saved encoder to {model} and stats to {stats}").format(
            model=model_path, stats=stats_path
        )
    )


if __name__ == "__main__":
    run_pointnet_gaussian_training()
