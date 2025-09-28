"""Report fused detections from image and point cloud inputs."""
from __future__ import annotations

import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..config import settings
from ..translation import translate_text
from ..analysis import coanalyze_pointcloud_and_images, image_to_pointcloud
from ..detection import (
    detect_camera_troops,
    detect_camera_vehicles,
    detect_camera_drones,
    detect_lidar_troops,
    detect_lidar_vehicles,
    detect_lidar_drones,
    detect_bluetooth_troops,
    detect_bluetooth_vehicles,
    detect_bluetooth_drones,
)

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_coanalysis_report(
    image_file: Path | None = None,
    pointcloud_file: Path | None = None,
    threshold: float | None = None,
    export: Path | None = None,
    bluetooth_log: Path | None = None,
) -> None:
    """Compare image-derived point clouds with sensor detections."""
    if image_file is None:
        image_file = Path(Prompt.ask(_t("Path to image file"), default="image.jpg"))
    if pointcloud_file is None:
        pointcloud_file = Path(Prompt.ask(_t("Path to point cloud"), default="cloud.pcd"))
    if bluetooth_log is None:
        log = Prompt.ask(_t("Bluetooth log (optional)"), default="")
        bluetooth_log = Path(log) if log else None
    if threshold is None:
        threshold = float(Prompt.ask(_t("Match threshold"), default="5"))

    img_points = image_to_pointcloud(image_file)
    image_dets = [{"x": x, "y": y, "class": "img", "conf": 1.0} for x, y in img_points]

    if export is not None:
        import csv

        export = Path(export)
        with export.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["x", "y"])
            writer.writerows(img_points)
        console.print(_t("Saved image point cloud to {path}").format(path=str(export)), style="green")

    cloud_dets = []
    cloud_dets.extend(detect_lidar_troops(pointcloud_file))
    cloud_dets.extend(detect_lidar_vehicles(pointcloud_file))
    cloud_dets.extend(detect_lidar_drones(pointcloud_file))
    if bluetooth_log is not None:
        cloud_dets.extend(detect_bluetooth_troops(bluetooth_log))
        cloud_dets.extend(detect_bluetooth_vehicles(bluetooth_log))
        cloud_dets.extend(detect_bluetooth_drones(bluetooth_log))

    fused = coanalyze_pointcloud_and_images(image_dets, cloud_dets, threshold)
    if not fused:
        console.print(_t("No matches"), style="yellow")
        return

    table = Table(title=_t("Fused detections"))
    table.add_column(_t("Class pair"))
    table.add_column("x", justify="right")
    table.add_column("y", justify="right")
    table.add_column(_t("Confidence"), justify="right")
    for det in fused:
        table.add_row(det["class"], f"{det['x']:.1f}", f"{det['y']:.1f}", f"{det['conf']:.2f}")
    console.print(table)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=_t("Co-analyze image and point cloud inputs"), add_help=True)
    parser.add_argument("--image", type=str, help=_t("Path to image file"))
    parser.add_argument("--pointcloud", type=str, help=_t("Path to point cloud"))
    parser.add_argument("--threshold", type=float, help=_t("Match threshold"))
    parser.add_argument("--export", type=str, help=_t("Optional CSV to save image point cloud"))
    parser.add_argument("--bluetooth", type=str, help=_t("Path to Bluetooth RSSI log"))
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_coanalysis_report(
        Path(args.image) if args.image else None,
        Path(args.pointcloud) if args.pointcloud else None,
        args.threshold,
        Path(args.export) if args.export else None,
        Path(args.bluetooth) if args.bluetooth else None,
    )
