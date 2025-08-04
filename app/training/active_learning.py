"""Active learning training with human feedback."""

from pathlib import Path
from typing import List, Optional
import csv
import shutil

from ..utils.pseudo_labeler import pseudo_label_images
from ..utils.human_feedback_viewer import launch_feedback_gui
from .train_with_augmentation import train_with_augmentation


def _filter_low_conf(pred_csv: Path, out_csv: Path, threshold: float) -> None:
    """Save only low confidence predictions to ``out_csv`` with filename field."""
    if not pred_csv.exists():
        return
    rows = []
    with pred_csv.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if float(row.get("confidence", 0)) < threshold:
                rows.append({"filename": row.get("file"), **row})
    if rows:
        with out_csv.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


def _apply_feedback(label_dir: Path, feedback_csv: Path) -> None:
    """Remove label files marked incorrect."""
    if not feedback_csv.exists():
        return
    with feedback_csv.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("correct") not in {"True", "true", "1"}:
                lab = label_dir / f"{Path(row['filename']).stem}.txt"
                if lab.exists():
                    lab.unlink()


def _merge_into_dataset(new_images: Path, label_dir: Path, train_dir: Path) -> None:
    """Copy images and labels into the training dataset."""
    label_dest = train_dir.parent.parent / "labels" / train_dir.name
    label_dest.mkdir(parents=True, exist_ok=True)
    for img_path in new_images.glob("*.jpg"):
        shutil.copy(img_path, train_dir / img_path.name)
        lab = label_dir / f"{img_path.stem}.txt"
        if lab.exists():
            shutil.copy(lab, label_dest / lab.name)


def active_learning_train(
    new_images: Path,
    train_dir: Path,
    val_dir: Path,
    classes: List[str],
    out_model: Path,
    conf_threshold: float = 0.5,
    epochs: int = 10,
    n_aug: int = 3,
    model_path: Optional[Path] = None,
) -> None:
    """Run pseudo labeling, review low confidence cases, then train with augmentation."""

    label_dir = new_images / "labels"
    pseudo_label_images(new_images, label_dir, conf_threshold=0.0, model_path=model_path)
    pred_csv = label_dir / "pseudo_labels.csv"
    low_conf_csv = label_dir / "low_conf.csv"
    feedback_csv = label_dir / "feedback.csv"

    _filter_low_conf(pred_csv, low_conf_csv, conf_threshold)
    if low_conf_csv.exists():
        print("Launching feedback GUI for low-confidence detections...")
        launch_feedback_gui(new_images, low_conf_csv, feedback_csv)
        _apply_feedback(label_dir, feedback_csv)

    _merge_into_dataset(new_images, label_dir, train_dir)

    train_with_augmentation(
        train_dir,
        val_dir,
        classes,
        out_model,
        augment=True,
        n_aug=n_aug,
        epochs=epochs,
    )


def _parse_args():
    import argparse

    p = argparse.ArgumentParser(description="Active learning training with human feedback")
    p.add_argument("new_images", type=Path)
    p.add_argument("train_dir", type=Path)
    p.add_argument("val_dir", type=Path)
    p.add_argument("out_model", type=Path)
    p.add_argument("--classes", nargs="+", required=True)
    p.add_argument("--conf-threshold", type=float, default=0.5)
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--n-aug", type=int, default=3)
    p.add_argument("--model", type=Path, default=None, help="Existing model for labeling")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    active_learning_train(
        args.new_images,
        args.train_dir,
        args.val_dir,
        args.classes,
        args.out_model,
        conf_threshold=args.conf_threshold,
        epochs=args.epochs,
        n_aug=args.n_aug,
        model_path=args.model,
    )


if __name__ == "__main__":
    main()
