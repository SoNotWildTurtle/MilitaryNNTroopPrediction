"""Compute image quality statistics for a dataset."""

from pathlib import Path
import csv
from typing import Iterable, Dict

import cv2
import numpy as np


def calc_blur(img) -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def calc_brightness(img) -> float:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return float(hsv[..., 2].mean())


def analyze_dataset(image_dir: Path, out_csv: Path) -> None:
    """Analyze all images in ``image_dir`` and write statistics to ``out_csv``."""
    rows: Iterable[Dict[str, float]] = []
    for img_path in sorted(image_dir.glob("*.jpg")):
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        rows.append(
            {
                "file": img_path.name,
                "brightness": calc_brightness(img),
                "blur": calc_blur(img),
                "width": img.shape[1],
                "height": img.shape[0],
            }
        )
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["file", "brightness", "blur", "width", "height"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(f"Dataset statistics written to {out_csv}")


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze image dataset quality")
    parser.add_argument("image_dir", type=Path, help="Directory of images")
    parser.add_argument(
        "-o", "--out", type=Path, default=Path("image_stats.csv"), help="CSV output"
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    analyze_dataset(args.image_dir, args.out)


if __name__ == "__main__":
    main()
