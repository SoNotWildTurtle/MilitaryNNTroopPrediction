"""CLI to classify an image using ConvNeXt features."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..detection.convnext_identifier import (
    load_convnext_components,
    load_convnext_classifier,
    classify_convnext,
)

def run_convnext_classify() -> None:
    parser = argparse.ArgumentParser(description="Classify image with ConvNeXt")
    parser.add_argument("image", help="Image file")
    parser.add_argument("--model", default="convnext_classifier.pkl", help="Classifier path")
    args = parser.parse_args()

    model, transform = load_convnext_components()
    clf = load_convnext_classifier(args.model)
    result = classify_convnext(Path(args.image), clf, model, transform)
    print(f"{result['target']}: {result['confidence']:.2f}")

if __name__ == "__main__":
    run_convnext_classify()
