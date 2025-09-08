"""Run a simple hyperparameter search for YOLO training."""

from itertools import product
from pathlib import Path
from typing import Iterable, List

from .train_yolo import DEFAULT_BATCH, DEFAULT_IMG_SIZE, DEFAULT_LR, train_yolo


def hyperparameter_search(
    train_dir: Path,
    val_dir: Path,
    classes: List[str],
    epochs: int,
    out_dir: Path,
    batches: Iterable[int] = (DEFAULT_BATCH,),
    lrs: Iterable[float] = (DEFAULT_LR, DEFAULT_LR / 10),
    img_sizes: Iterable[int] = (DEFAULT_IMG_SIZE,),
) -> None:
    """Train multiple YOLO models over a grid of parameters.

    Parameters
    ----------
    train_dir : Path
        Directory of training images and labels.
    val_dir : Path
        Directory of validation images and labels.
    classes : List[str]
        Detection class names.
    epochs : int
        Number of epochs for each experiment.
    out_dir : Path
        Where to store the resulting models.
    batches, lrs, img_sizes : Iterable
        Parameter grids to search over.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for batch, lr, img in product(batches, lrs, img_sizes):
        model_path = out_dir / f"yolo_b{batch}_lr{lr}_img{img}.pt"
        print(
            f"Training with batch={batch}, lr={lr}, img_size={img}. Output: {model_path}"
        )
        train_yolo(
            train_dir,
            val_dir,
            classes,
            epochs,
            model_path,
            batch=batch,
            img_size=img,
            lr=lr,
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hyperparameter search for YOLO")
    parser.add_argument("train_dir", type=Path)
    parser.add_argument("val_dir", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--classes", nargs="+", required=True, help="Detection classes")
    parser.add_argument("--epochs", type=int, default=25, help="Epochs per experiment")
    parser.add_argument(
        "--batches", nargs="+", type=int, default=[DEFAULT_BATCH], help="Batch sizes"
    )
    parser.add_argument(
        "--lrs", nargs="+", type=float, default=[DEFAULT_LR, DEFAULT_LR / 10], help="Learning rates"
    )
    parser.add_argument(
        "--img-sizes", nargs="+", type=int, default=[DEFAULT_IMG_SIZE], help="Image resolutions"
    )
    args = parser.parse_args()

    hyperparameter_search(
        args.train_dir,
        args.val_dir,
        args.classes,
        args.epochs,
        args.out_dir,
        batches=args.batches,
        lrs=args.lrs,
        img_sizes=args.img_sizes,
    )
