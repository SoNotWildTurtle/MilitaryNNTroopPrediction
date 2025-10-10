"""Extract HOG features from images for advanced analysis."""

from pathlib import Path
from typing import List

import cv2
import numpy as np

from ..config import settings


def extract_hog_features(image_dir: Path, out_npz: Path, scale: float | None = None) -> None:
    """Compute HOG descriptors for all ``.jpg`` images in ``image_dir``.

    ``scale`` (or the ``RESOLUTION_SCALE`` setting) upsamples images before feature
    extraction, allowing richer descriptors on systems with more memory.
    The descriptors are saved in ``out_npz`` with arrays ``files`` and ``features``.
    """
    scale = scale or settings.RESOLUTION_SCALE
    hog = cv2.HOGDescriptor()
    files: List[str] = []
    feats: List[np.ndarray] = []
    for img_path in sorted(image_dir.glob("*.jpg")):
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        if scale != 1.0:
            h, w = img.shape[:2]
            img = cv2.resize(img, (int(w * scale), int(h * scale)))
        descriptor = hog.compute(img)
        if descriptor is None:
            continue
        files.append(img_path.name)
        feats.append(descriptor.flatten())
    if not feats:
        print("No features extracted")
        return
    np.savez_compressed(out_npz, files=np.array(files), features=np.stack(feats))
    print(f"HOG features written to {out_npz}")


def _parse_args():
    import argparse

    p = argparse.ArgumentParser(description="Extract HOG features from images")
    p.add_argument("image_dir", type=Path, help="Directory with images")
    p.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("hog_features.npz"),
        help="Output .npz file",
    )
    p.add_argument(
        "--scale",
        type=float,
        default=None,
        help="Resolution scale factor (overrides RESOLUTION_SCALE)",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    extract_hog_features(args.image_dir, args.out, args.scale)


if __name__ == "__main__":
    main()
