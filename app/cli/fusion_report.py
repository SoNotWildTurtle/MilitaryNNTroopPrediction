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
    image_file: Path | None = None, pointcloud_file: Path | None = None
) -> None:
    """Prompt for sensor files and print fused detections."""
    if image_file is None:
        image_file = Path(Prompt.ask(_t("Image file"), default="sample.jpg"))
    if pointcloud_file is None:
        pointcloud_file = Path(
            Prompt.ask(_t("Point cloud file"), default="sample.pcd")
        )

    fused = detect_fused_objects(image_file, pointcloud_file)
    if not fused:
        console.print(_t("No detections"), style="yellow")
        return

    table = Table(title=_t("Fused detections"))
    table.add_column(_t("Class"))
    table.add_column(_t("Confidence"), justify="right")
    for det in fused:
        table.add_row(det["class"], f"{det['confidence']:.2f}")
    console.print(table)
 

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=_t("Fuse camera and LIDAR detections"), add_help=True
    )
    parser.add_argument("--image", type=str, help=_t("Path to image file"))
    parser.add_argument(
        "--pointcloud", type=str, help=_t("Path to point cloud file")
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()
    run_fusion_report(
        Path(args.image) if args.image else None,
        Path(args.pointcloud) if args.pointcloud else None,
    )
