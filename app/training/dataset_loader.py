"""Utilities for preparing datasets for YOLO training."""

from pathlib import Path
from typing import List
import yaml


def create_data_yaml(train_dir: Path, val_dir: Path, classes: List[str], out_file: Path) -> Path:
    """Create a Ultralytics data YAML file.

    Parameters
    ----------
    train_dir: Path
        Directory with training images and labels.
    val_dir: Path
        Directory with validation images and labels.
    classes: List[str]
        List of class names for detection.
    out_file: Path
        Where to write the YAML configuration.
    """
    data = {
        "path": str(train_dir.parent),
        "train": train_dir.name,
        "val": val_dir.name,
        "names": {i: c for i, c in enumerate(classes)},
    }
    out_file.write_text(yaml.safe_dump(data))
    return out_file


def _parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Create data.yaml for YOLO training")
    parser.add_argument("train_dir", type=Path)
    parser.add_argument("val_dir", type=Path)
    parser.add_argument("-o", "--out", type=Path, default=Path("data.yaml"))
    parser.add_argument("--classes", nargs="+", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    path = create_data_yaml(args.train_dir, args.val_dir, args.classes, args.out)
    print(f"data.yaml written to {path}")


if __name__ == "__main__":
    main()

