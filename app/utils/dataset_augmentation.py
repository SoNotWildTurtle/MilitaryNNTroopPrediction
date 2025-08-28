"""Dataset augmentation utilities using Albumentations."""

from pathlib import Path
from typing import Iterable

import albumentations as A
import cv2


def augment_images(src_dir: Path, dst_dir: Path, n_aug: int = 3) -> None:
    """Create augmented copies of images in ``src_dir``.

    Parameters
    ----------
    src_dir: Path
        Directory containing original images.
    dst_dir: Path
        Destination directory for augmented images.
    n_aug: int
        Number of augmentations per image.
    """
    dst_dir.mkdir(parents=True, exist_ok=True)
    pipeline = A.Compose(
        [
            A.HorizontalFlip(p=0.5),
            A.RandomBrightnessContrast(p=0.5),
            A.ShiftScaleRotate(shift_limit=0.05, scale_limit=0.1, rotate_limit=15, p=0.5),
        ]
    )

    for img_path in src_dir.glob("*.jpg"):
        image = cv2.imread(str(img_path))
        for i in range(n_aug):
            augmented = pipeline(image=image)["image"]
            out_path = dst_dir / f"{img_path.stem}_aug{i}.jpg"
            cv2.imwrite(str(out_path), augmented)


def _parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Augment dataset images")
    parser.add_argument("src", type=Path, help="Source image directory")
    parser.add_argument("dst", type=Path, help="Destination directory")
    parser.add_argument("-n", "--num", type=int, default=3, help="Augmentations per image")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    augment_images(args.src, args.dst, args.num)


if __name__ == "__main__":
    main()

