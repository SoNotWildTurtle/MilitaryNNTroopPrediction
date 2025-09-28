"""Verify YOLO dataset files have matching images and labels."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

def verify_dataset(dataset: str) -> dict[str, list[str]]:
    """Check for missing labels or images under ``dataset``.

    The dataset is expected to contain ``images`` and ``labels`` subfolders.
    Returns a dictionary with keys ``missing_labels`` and ``missing_images``.
    """
    root = Path(dataset)
    images = {p.stem for p in (root / "images").glob("*") if p.suffix.lower() in IMAGE_EXTS}
    labels = {p.stem for p in (root / "labels").glob("*.txt")}

    missing_labels = sorted(images - labels)
    missing_images = sorted(labels - images)

    return {"missing_labels": missing_labels, "missing_images": missing_images}


def _print(items: Iterable[str], title: str) -> None:
    print(f"{title}: {len(list(items))}")
    for name in list(items)[:10]:
        print(f" - {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify YOLO dataset consistency")
    parser.add_argument("dataset", help="Path containing images/ and labels/ subdirs")
    args = parser.parse_args()
    result = verify_dataset(args.dataset)
    _print(result["missing_labels"], "Images without labels")
    _print(result["missing_images"], "Labels without images")


if __name__ == "__main__":
    main()
