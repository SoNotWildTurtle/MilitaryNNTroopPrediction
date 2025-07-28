from pathlib import Path
from typing import List
import shutil

from ..utils.pseudo_labeler import pseudo_label_images
from ..training.train_yolo import train_yolo


def self_reinforce(
    new_images: Path,
    train_dir: Path,
    val_dir: Path,
    classes: List[str],
    out_model: Path,
    epochs: int = 10,
) -> None:
    label_dir = new_images / "labels"
    pseudo_label_images(new_images, label_dir)

    img_dest = train_dir
    label_dest = train_dir.parent.parent / "labels" / train_dir.name
    label_dest.mkdir(parents=True, exist_ok=True)

    for img_path in new_images.glob("*.jpg"):
        shutil.copy(img_path, img_dest / img_path.name)
        lab_path = label_dir / f"{img_path.stem}.txt"
        if lab_path.exists():
            shutil.copy(lab_path, label_dest / lab_path.name)

    train_yolo(train_dir, val_dir, classes, epochs, out_model)


def _parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Self-reinforcement training from new images")
    parser.add_argument("new_images", type=Path, help="Directory of unlabeled images")
    parser.add_argument("train_dir", type=Path, help="Training image directory")
    parser.add_argument("val_dir", type=Path, help="Validation image directory")
    parser.add_argument("--classes", nargs="+", required=True)
    parser.add_argument("--out-model", type=Path, default=Path("self_model.pt"))
    parser.add_argument("--epochs", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    self_reinforce(args.new_images, args.train_dir, args.val_dir, args.classes, args.out_model, args.epochs)


if __name__ == "__main__":
    main()
