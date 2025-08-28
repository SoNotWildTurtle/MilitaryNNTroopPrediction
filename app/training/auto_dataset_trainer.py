"""Automate dataset splitting, augmentation, and YOLO training."""

from pathlib import Path
from typing import List
import shutil
import random

from .train_with_augmentation import train_with_augmentation
from .train_yolo import DEFAULT_BATCH, DEFAULT_IMG_SIZE, DEFAULT_LR


def auto_dataset_train(
    dataset_dir: Path,
    classes: List[str],
    out_model: Path,
    val_split: float = 0.2,
    augment: bool = True,
    n_aug: int = 3,
    epochs: int = 50,
    batch: int = DEFAULT_BATCH,
    img_size: int = DEFAULT_IMG_SIZE,
    lr: float = DEFAULT_LR,
) -> None:
    """Split a dataset, optionally augment, and train YOLO.

    Parameters
    ----------
    dataset_dir: Path
        Directory containing ``images`` and ``labels`` subfolders.
    classes: List[str]
        Detection class names.
    out_model: Path
        Where to save the trained YOLO model.
    val_split: float
        Fraction of data reserved for validation.
    augment: bool
        Whether to augment the training images before training.
    n_aug: int
        Number of augmented copies per image when ``augment`` is True.
    epochs: int
        Number of training epochs.
    batch: int
        Training batch size.
    img_size: int
        Training image size.
    lr: float
        Initial learning rate.
    """
    images_dir = dataset_dir / "images"
    labels_dir = dataset_dir / "labels"
    train_dir = dataset_dir / "train"
    val_dir = dataset_dir / "val"

    # Reset train/val dirs
    if train_dir.exists():
        shutil.rmtree(train_dir)
    if val_dir.exists():
        shutil.rmtree(val_dir)

    (train_dir / "images").mkdir(parents=True)
    (train_dir / "labels").mkdir(parents=True)
    (val_dir / "images").mkdir(parents=True)
    (val_dir / "labels").mkdir(parents=True)

    stems = [p.stem for p in images_dir.glob("*.jpg")]
    random.shuffle(stems)
    split_idx = int(len(stems) * (1 - val_split))
    train_stems = stems[:split_idx]
    val_stems = stems[split_idx:]

    for stem in train_stems:
        shutil.copy(images_dir / f"{stem}.jpg", train_dir / "images" / f"{stem}.jpg")
        label_path = labels_dir / f"{stem}.txt"
        if label_path.exists():
            shutil.copy(label_path, train_dir / "labels" / f"{stem}.txt")

    for stem in val_stems:
        shutil.copy(images_dir / f"{stem}.jpg", val_dir / "images" / f"{stem}.jpg")
        label_path = labels_dir / f"{stem}.txt"
        if label_path.exists():
            shutil.copy(label_path, val_dir / "labels" / f"{stem}.txt")

    train_with_augmentation(
        train_dir,
        val_dir,
        classes,
        out_model,
        augment=augment,
        n_aug=n_aug,
        epochs=epochs,
        batch=batch,
        img_size=img_size,
        lr=lr,
    )


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Automatically split and train a dataset")
    parser.add_argument("dataset_dir", type=Path)
    parser.add_argument("out_model", type=Path)
    parser.add_argument("--classes", nargs="+", required=True)
    parser.add_argument("--val-split", type=float, default=0.2)
    parser.add_argument("--no-augment", action="store_true", help="Disable augmentation")
    parser.add_argument("--n-aug", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--img-size", type=int, default=DEFAULT_IMG_SIZE)
    parser.add_argument("--lr", type=float, default=DEFAULT_LR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    auto_dataset_train(
        args.dataset_dir,
        args.classes,
        args.out_model,
        val_split=args.val_split,
        augment=not args.no_augment,
        n_aug=args.n_aug,
        epochs=args.epochs,
        batch=args.batch,
        img_size=args.img_size,
        lr=args.lr,
    )


if __name__ == "__main__":
    main()
