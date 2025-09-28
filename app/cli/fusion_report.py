"""Run camera and LIDAR detection then display fused results."""
from __future__ import annotations

import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

from ..config import settings
from ..translation import translate_text
from ..detection import detect_fused_objects

console = Console()
_LANG = settings.UI_LANG


def _t(text: str) -> str:
    return translate_text(text, target_lang=_LANG)


def run_fusion_report(
    image_file: Path | None = None,
    pointcloud_file: Path | None = None,
    bluetooth_log: Path | None = None,
) -> None:
    """Prompt for sensor files and print fused detections."""
    if image_file is None:
        image_file = Path(Prompt.ask(_t("Image file"), default="sample.jpg"))
    if pointcloud_file is None:
        pointcloud_file = Path(
            Prompt.ask(_t("Point cloud file"), default="sample.pcd")
        )
    if bluetooth_log is None:
        log = Prompt.ask(_t("Bluetooth log (optional)"), default="")
        bluetooth_log = Path(log) if log else None

    fused = detect_fused_objects(image_file, pointcloud_file, bluetooth_log)
    if not fused:
        console.print(_t("No detections"), style="yellow")
        return

    table = Table(title=_t("Fused detections"))
    table.add_column(_t("Class"))
    table.add_column(_t("Confidence"), justify="right")
    table.add_column(_t("Cover"))
    for det in fused:
        cover = det.get("in_cover")
        if cover is None:
            cover_text = "-"
        else:
            cover_text = _t("Yes") if cover else _t("No")
        table.add_row(det["class"], f"{det['confidence']:.2f}", cover_text)
    console.print(table)
 

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=_t("Fuse camera, LIDAR, and Bluetooth detections"),
        add_help=True,
    )
    parser.add_argument("--image", type=str, help=_t("Path to image file"))
    parser.add_argument(
        "--pointcloud", type=str, help=_t("Path to point cloud file")
    )
    parser.add_argument(
        "--bluetooth", type=str, help=_t("Path to Bluetooth RSSI log")
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_fusion_report(
        Path(args.image) if args.image else None,
        Path(args.pointcloud) if args.pointcloud else None,
        Path(args.bluetooth) if args.bluetooth else None,
    )
