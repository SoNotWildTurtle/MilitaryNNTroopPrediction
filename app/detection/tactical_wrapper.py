"""Doctrine tagging wrapper for YOLO detections."""

from pathlib import Path
from typing import List, Dict, Optional

from . import yolo

_DOCTRINE_THRESHOLD = 0.6


def tag_doctrine(detections: List[Dict], threshold: float = _DOCTRINE_THRESHOLD) -> List[Dict]:
    """Attach a simple doctrine label based on confidence."""
    for det in detections:
        conf = float(det.get("confidence", 0))
        det["doctrine"] = "modern" if conf >= threshold else "legacy"
    return detections


def detect_and_tag(image: Path, model_path: Optional[Path] = None, threshold: float = _DOCTRINE_THRESHOLD) -> List[Dict]:
    """Run YOLO detection and tag each result with a doctrine label."""
    detections = yolo.detect_vehicles(image, model_path)
    return tag_doctrine(detections, threshold)


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Detect and tag doctrine")
    parser.add_argument("image", type=Path)
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--threshold", type=float, default=_DOCTRINE_THRESHOLD)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    dets = detect_and_tag(args.image, args.model, args.threshold)
    for d in dets:
        print(d)


if __name__ == "__main__":
    main()
