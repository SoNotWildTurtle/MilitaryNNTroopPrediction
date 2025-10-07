"""CLI to classify an image using ResNet features."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..detection.resnet_identifier import (
    load_resnet_components,
    load_resnet_classifier,
    classify_resnet,
)


def run_resnet_classify() -> None:
    parser = argparse.ArgumentParser(description="Classify image with ResNet")
    parser.add_argument("image", help="Image file")
    parser.add_argument("--model", default="resnet_classifier.pkl", help="Classifier path")
    args = parser.parse_args()

    model, transform = load_resnet_components()
    clf = load_resnet_classifier(args.model)
    result = classify_resnet(Path(args.image), clf, model, transform)
    print(f"{result['target']}: {result['confidence']:.2f}")


if __name__ == "__main__":
    run_resnet_classify()
