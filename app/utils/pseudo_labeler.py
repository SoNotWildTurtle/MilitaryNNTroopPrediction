"""Generate pseudo labels for unlabeled images."""

from pathlib import Path
from typing import List, Dict, Optional
import csv

from ..detection import yolo


def pseudo_label_images(
    img_dir: Path,
    label_dir: Path,
    conf_threshold: float = 0.6,
    model_path: Optional[Path] = None,
) -> None:
    """Run detection on ``img_dir`` and write YOLO label files.

    Parameters
    ----------
    img_dir: Path
        Directory with images to label.
    label_dir: Path
        Output directory for generated ``.txt`` files.
    conf_threshold: float
        Minimum confidence required to keep a detection.
    """

    label_dir.mkdir(parents=True, exist_ok=True)
    csv_rows: List[Dict[str, float]] = []

    for img_path in sorted(img_dir.glob("*.jpg")):
        detections = yolo.detect_vehicles(img_path, model_path=model_path)
        yolo_lines: List[str] = []
        for det in detections:
            if det.get("confidence", 0.0) >= conf_threshold:
                # Convert mock lat/lon into a dummy bounding box
                x_center = (det["lon"] % 1)
                y_center = (det["lat"] % 1)
                width = height = 0.1
                yolo_lines.append(f"0 {x_center:.4f} {y_center:.4f} {width:.4f} {height:.4f}\n")
                csv_rows.append(
                    {
                        "file": img_path.name,
                        "lat": det["lat"],
                        "lon": det["lon"],
                        "confidence": det["confidence"],
                    }
                )
        if yolo_lines:
            label_file = label_dir / f"{img_path.stem}.txt"
            with label_file.open("w") as f:
                f.writelines(yolo_lines)

    # Also save a CSV summary next to the labels for auditing
    csv_path = label_dir / "pseudo_labels.csv"
    if csv_rows:
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["file", "lat", "lon", "confidence"])
            writer.writeheader()
            writer.writerows(csv_rows)

    print(f"Pseudo labels written to {label_dir}")


def _parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Generate pseudo labels from images")
    parser.add_argument("img_dir", type=Path, help="Directory of unlabeled images")
    parser.add_argument("-o", "--out", type=Path, default=Path("pseudo_labels"))
    parser.add_argument("--conf", type=float, default=0.6, help="Confidence threshold")
    parser.add_argument("--model", type=Path, help="YOLO model to use for labeling", default=None)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    pseudo_label_images(args.img_dir, args.out, args.conf, model_path=args.model)



if __name__ == "__main__":
    main()
