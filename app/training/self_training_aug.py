"""Self-training loop with dataset augmentation."""

from pathlib import Path
from typing import List, Optional
import shutil

from ..utils.pseudo_labeler import pseudo_label_images
from ..training.train_with_augmentation import train_with_augmentation


def self_reinforce_aug(
    new_images: Path,
    train_dir: Path,
    val_dir: Path,
    classes: List[str],
    out_model: Path,
    epochs: int = 10,
    n_aug: int = 3,
    model_path: Optional[Path] = None,
) -> None:
    """Label new images, merge them into the dataset and train with augmentation."""

    label_dir = new_images / "labels"
    pseudo_label_images(new_images, label_dir, model_path=model_path)

    img_dest = train_dir
    label_dest = train_dir.parent.parent / "labels" / train_dir.name
    label_dest.mkdir(parents=True, exist_ok=True)

    for img_path in new_images.glob("*.jpg"):
        shutil.copy(img_path, img_dest / img_path.name)
        lab_path = label_dir / f"{img_path.stem}.txt"
        if lab_path.exists():
            shutil.copy(lab_path, label_dest / lab_path.name)

    train_with_augmentation(
        train_dir,
        val_dir,
        classes,
        out_model,
        augment=True,
        n_aug=n_aug,
        epochs=epochs,
    )


def self_training_aug_loop(
    new_images: Path,
    train_dir: Path,
    val_dir: Path,
    classes: List[str],
    model_path: Path,
    iterations: int = 3,
    epochs: int = 5,
    n_aug: int = 3,
) -> None:
    """Run multiple self-reinforcement cycles with augmentation."""

    current_model = model_path
    for i in range(iterations):
        print(f"\n=== Augmented self-training iteration {i+1}/{iterations} ===")
        self_reinforce_aug(
            new_images,
            train_dir,
            val_dir,
            classes,
            current_model,
            epochs=epochs,
            n_aug=n_aug,
            model_path=current_model,
        )


def _parse_args():
    import argparse

    p = argparse.ArgumentParser(description="Self-training with augmentation")
    p.add_argument("new_images", type=Path)
    p.add_argument("train_dir", type=Path)
    p.add_argument("val_dir", type=Path)
    p.add_argument("model_path", type=Path, help="Model path for output and labeling")
    p.add_argument("--classes", nargs="+", required=True)
    p.add_argument("--iterations", type=int, default=3)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--n-aug", type=int, default=3, help="Augmentations per image")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    self_training_aug_loop(
        args.new_images,
        args.train_dir,
        args.val_dir,
        args.classes,
        args.model_path,
        iterations=args.iterations,
        epochs=args.epochs,
        n_aug=args.n_aug,
    )


if __name__ == "__main__":
    main()
