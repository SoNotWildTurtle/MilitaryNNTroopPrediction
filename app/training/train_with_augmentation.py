"""Train YOLO with optional dataset augmentation."""

from pathlib import Path
from typing import List

from ..utils.dataset_augmentation import augment_images
from .train_yolo import train_yolo, DEFAULT_BATCH, DEFAULT_IMG_SIZE, DEFAULT_LR


def train_with_augmentation(
    train_dir: Path,
    val_dir: Path,
    classes: List[str],
    out_model: Path,
    augment: bool = True,
    n_aug: int = 3,
    epochs: int = 50,
    batch: int = DEFAULT_BATCH,
    img_size: int = DEFAULT_IMG_SIZE,
    lr: float = DEFAULT_LR,
) -> None:
    """Augment images then train a YOLO model."""
    final_train = train_dir
    if augment:
        aug_dir = train_dir.parent / f"{train_dir.name}_aug"
        augment_images(train_dir, aug_dir, n_aug=n_aug)
        final_train = aug_dir

    train_yolo(
        final_train,
        val_dir,
        classes,
        epochs,
        out_model,
        batch=batch,
        img_size=img_size,
        lr=lr,
    )


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Train YOLO with augmentation")
    parser.add_argument("train_dir", type=Path)
    parser.add_argument("val_dir", type=Path)
    parser.add_argument("out_model", type=Path)
    parser.add_argument("--classes", nargs="+", required=True)
    parser.add_argument("--no-augment", action="store_true", help="Skip augmentation")
    parser.add_argument("--n-aug", type=int, default=3, help="Augmentations per image")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--img-size", type=int, default=DEFAULT_IMG_SIZE)
    parser.add_argument("--lr", type=float, default=DEFAULT_LR)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    train_with_augmentation(
        args.train_dir,
        args.val_dir,
        args.classes,
        args.out_model,
        augment=not args.no_augment,
        n_aug=args.n_aug,
        epochs=args.epochs,
        batch=args.batch,
        img_size=args.img_size,
        lr=args.lr,
    )


if __name__ == "__main__":
    main()
