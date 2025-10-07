"""CLI to classify an image using multiple identifiers and average results."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List

from ..detection.ensemble_identifier import classify_ensemble
from ..detection.feature_fused_identifier import (
    load_feature_fused_classifier,
    classify_feature_fused,
)
from ..detection.convnext_identifier import (
    load_convnext_components,
    load_convnext_classifier,
    classify_convnext,
)
from ..detection.resnet_identifier import (
    load_resnet_components,
    load_resnet_classifier,
    classify_resnet,
)


def run_ensemble_classify() -> None:
    parser = argparse.ArgumentParser(description="Classify image with an ensemble of models")
    parser.add_argument("image", help="Image file")
    parser.add_argument("--feature-fused", help="Path to feature-fused classifier")
    parser.add_argument("--convnext", help="Path to ConvNeXt classifier")
    parser.add_argument("--resnet", help="Path to ResNet classifier")
    args = parser.parse_args()

    image = Path(args.image)
    classifiers: List = []
    if args.feature_fused:
        ff_clf = load_feature_fused_classifier(args.feature_fused)
        classifiers.append(lambda p: classify_feature_fused(p, ff_clf))
    if args.convnext:
        cn_clf = load_convnext_classifier(args.convnext)
        cn_model, cn_transform = load_convnext_components()
        classifiers.append(lambda p: classify_convnext(p, cn_clf, cn_model, cn_transform))
    if args.resnet:
        rn_clf = load_resnet_classifier(args.resnet)
        rn_model, rn_transform = load_resnet_components()
        classifiers.append(lambda p: classify_resnet(p, rn_clf, rn_model, rn_transform))

    result = classify_ensemble(image, classifiers)
    print(f"{result['target']}: {result['confidence']:.2f}")


if __name__ == "__main__":
    run_ensemble_classify()
