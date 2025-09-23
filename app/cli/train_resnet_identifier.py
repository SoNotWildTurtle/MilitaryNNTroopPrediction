"""CLI to train a ResNet-based classifier."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..training.resnet_trainer import train_resnet_classifier


def run_train_resnet_identifier() -> None:
    parser = argparse.ArgumentParser(description="Train ResNet target classifier")
    parser.add_argument("--images", nargs="+", required=True, help="Image files")
    parser.add_argument("--labels", nargs="+", required=True, help="Class labels")
    parser.add_argument("--model", default="resnet_classifier.pkl", help="Output model path")
    args = parser.parse_args()

    imgs = [Path(p) for p in args.images]
    train_resnet_classifier(imgs, args.labels, Path(args.model))
    print(f"Saved model to {args.model}")


if __name__ == "__main__":
    run_train_resnet_identifier()
