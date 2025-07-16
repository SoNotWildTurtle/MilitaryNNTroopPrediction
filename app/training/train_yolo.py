"""Train a YOLO model using the Ultralytics package."""

from pathlib import Path
from typing import List

from ultralytics import YOLO

from .dataset_loader import create_data_yaml


def train_yolo(train_dir: Path, val_dir: Path, classes: List[str], epochs: int, out_model: Path) -> None:
    """Train a YOLO model.

    Parameters
    ----------
    train_dir : Path
        Directory containing training images and labels.
    val_dir : Path
        Directory containing validation images and labels.
    classes : List[str]
        Detection class names.
    epochs : int
        Number of training epochs.
    out_model : Path
        Where to save the trained model.
    """
    yaml_path = create_data_yaml(train_dir, val_dir, classes, Path("data.yaml"))
    model = YOLO("yolov8n.pt")
    model.train(data=str(yaml_path), epochs=epochs)
    model.save(str(out_model))
    print(f"YOLO model saved to {out_model}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train YOLO model")
    parser.add_argument("train_dir", type=Path)
    parser.add_argument("val_dir", type=Path)
    parser.add_argument("out_model", type=Path)
    parser.add_argument("--classes", nargs="+", required=True, help="Class names")
    parser.add_argument("--epochs", type=int, default=50)
    args = parser.parse_args()

    train_yolo(args.train_dir, args.val_dir, args.classes, args.epochs, args.out_model)
