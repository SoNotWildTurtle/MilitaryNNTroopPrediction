"""Sequential YOLO training on multiple datasets."""

from pathlib import Path
from typing import List

from ultralytics import YOLO


def train_sequential(data_files: List[Path], epochs: int, out_model: Path) -> None:
    """Train a YOLO model sequentially on multiple datasets.

    Parameters
    ----------
    data_files : List[Path]
        List of YOLO data.yaml files.
    epochs : int
        Number of epochs for each dataset.
    out_model : Path
        Path to save the final model.
    """
    model = YOLO("yolov8n.pt")
    for yaml_file in data_files:
        model.train(data=str(yaml_file), epochs=epochs)
    model.save(str(out_model))
    print(f"Sequential YOLO model saved to {out_model}")


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Train YOLO sequentially on multiple datasets")
    parser.add_argument("data_files", type=Path, nargs='+', help="List of data.yaml files")
    parser.add_argument("out_model", type=Path)
    parser.add_argument("--epochs", type=int, default=50)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    train_sequential(args.data_files, args.epochs, args.out_model)


if __name__ == "__main__":
    main()
