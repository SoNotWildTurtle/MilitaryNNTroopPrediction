"""Generate a small synthetic dataset for offline demos.

Creates simple images with colored rectangles representing troops, vehicles,
 and drones and writes YOLO label files so the rest of the pipeline can run
 without live data sources.
"""
from pathlib import Path
import random
from typing import Tuple

from PIL import Image, ImageDraw

CLASSES = ["troop", "vehicle", "drone"]


def _rand_box(w: int, h: int) -> Tuple[int, int, int, int]:
    """Return random bounding box coordinates within image size."""
    x1 = random.randint(0, w // 2)
    y1 = random.randint(0, h // 2)
    x2 = random.randint(x1 + 10, w)
    y2 = random.randint(y1 + 10, h)
    return x1, y1, x2, y2


def generate_demo_dataset(out_dir: str, num_images: int = 10,
                          image_size: Tuple[int, int] = (640, 480)) -> None:
    """Create synthetic images and YOLO labels in ``out_dir``.

    Parameters
    ----------
    out_dir: str
        Destination directory; ``images`` and ``labels`` subfolders will be
        created inside.
    num_images: int
        Number of images to generate.
    image_size: tuple
        Width and height of each generated image.
    """
    out = Path(out_dir)
    img_dir = out / "images"
    lbl_dir = out / "labels"
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    w, h = image_size
    for i in range(num_images):
        img = Image.new("RGB", (w, h), color="black")
        draw = ImageDraw.Draw(img)
        labels = []
        # place 1-3 random objects per image
        for _ in range(random.randint(1, 3)):
            cls = random.randint(0, len(CLASSES) - 1)
            x1, y1, x2, y2 = _rand_box(w, h)
            draw.rectangle([x1, y1, x2, y2], outline="white", width=2)
            # convert to YOLO normalized format
            cx = (x1 + x2) / 2 / w
            cy = (y1 + y2) / 2 / h
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h
            labels.append(f"{cls} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
        img_path = img_dir / f"demo_{i:03d}.jpg"
        img.save(img_path)
        with open(lbl_dir / f"demo_{i:03d}.txt", "w", encoding="utf-8") as f:
            f.writelines(labels)


if __name__ == "__main__":
    generate_demo_dataset("demo_data")
