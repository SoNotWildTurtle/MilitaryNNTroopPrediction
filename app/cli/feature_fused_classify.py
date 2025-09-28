"""CLI to classify an image using fused features."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..detection.feature_fused_identifier import (
    load_feature_fused_classifier,
    classify_feature_fused,
)


def run_feature_fused_classify() -> None:
    parser = argparse.ArgumentParser(description="Classify image with fused features")
    parser.add_argument("image", help="Image file")
    parser.add_argument("--model", default="feature_fused_classifier.pkl", help="Classifier path")
    args = parser.parse_args()

    clf = load_feature_fused_classifier(args.model)
    result = classify_feature_fused(Path(args.image), clf)
    print(f"{result['target']}: {result['confidence']:.2f}")


if __name__ == "__main__":
    run_feature_fused_classify()
