"""Extract HOG features from images for advanced analysis."""

from pathlib import Path
from typing import List

import cv2
import numpy as np


def extract_hog_features(image_dir: Path, out_npz: Path) -> None:
    """Compute HOG descriptors for all ``.jpg`` images in ``image_dir``.

    The descriptors are saved in ``out_npz`` with arrays ``files`` and ``features``.
    """
    hog = cv2.HOGDescriptor()
    files: List[str] = []
    feats: List[np.ndarray] = []
    for img_path in sorted(image_dir.glob("*.jpg")):
        img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
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
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    extract_hog_features(args.image_dir, args.out)


if __name__ == "__main__":
    main()
