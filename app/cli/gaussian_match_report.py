"""CLI to identify entities by matching Gaussian point clouds."""
from __future__ import annotations

import argparse
import csv
from typing import List, Tuple

from rich.console import Console
from rich.table import Table

from ..analysis import image_to_pointcloud3d, rank_pointcloud_gaussian
from ..translation import translate_text
from ..config import settings

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def _load_sensor_cloud(path: str) -> List[Tuple[float, float, float]]:
    pts: List[Tuple[float, float, float]] = []
    with open(path, "r", newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 3:
                pts.append((float(row[0]), float(row[1]), float(row[2])))
    return pts


def run_gaussian_match_report() -> None:
    parser = argparse.ArgumentParser(description=_t("Match image and sensor point clouds"))
    parser.add_argument("image", help=_t("Image file to convert into a point cloud"))
    parser.add_argument("sensor", help=_t("CSV file of sensor point cloud (x,y,z)"))
    parser.add_argument(
        "--model",
        default="gaussian_pointcloud_model.json",
        help=_t("Trained model JSON"),
    )
    parser.add_argument(
        "--top",
        type=int,
        default=3,
        help=_t("Number of top classes to display"),
    )
    args = parser.parse_args()

    image_cloud = image_to_pointcloud3d(args.image)
    sensor_cloud = _load_sensor_cloud(args.sensor)
    results = rank_pointcloud_gaussian(image_cloud, sensor_cloud, args.model, args.top)

    table = Table(title=_t("Gaussian match results"))
    table.add_column(_t("Class"))
    table.add_column(_t("Distance"), justify="right")
    table.add_column(_t("Probability"), justify="right")
    for label, score, prob in results:
        table.add_row(label, f"{score:.2f}", f"{prob:.2f}")
    console.print(table)


if __name__ == "__main__":
    run_gaussian_match_report()

