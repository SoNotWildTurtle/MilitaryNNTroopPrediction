"""CLI to classify an image using Swin features."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..detection.swin_identifier import (
    load_swin_components,
    load_swin_classifier,
    classify_swin,
)


def run_swin_classify() -> None:
    parser = argparse.ArgumentParser(description="Classify image with Swin Transformer")
    parser.add_argument("image", help="Image file")
    parser.add_argument("--model", default="swin_classifier.pkl", help="Classifier path")
    args = parser.parse_args()

    model, transform = load_swin_components()
    clf = load_swin_classifier(args.model)
    result = classify_swin(Path(args.image), clf, model, transform)
    print(f"{result['target']}: {result['confidence']:.2f}")


if __name__ == "__main__":
    run_swin_classify()
