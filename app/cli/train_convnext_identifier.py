"""CLI to train a ConvNeXt-based classifier from labeled images."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..training.convnext_trainer import train_convnext_classifier

def run_train_convnext_identifier() -> None:
    parser = argparse.ArgumentParser(description="Train ConvNeXt classifier")
    parser.add_argument("images", nargs="+", help="List of image:label pairs")
    parser.add_argument("--model", default="convnext_classifier.pkl", help="Output model path")
    args = parser.parse_args()

    paths = [Path(p.split(":")[0]) for p in args.images]
    labels = [p.split(":")[1] for p in args.images]
    train_convnext_classifier(paths, labels, Path(args.model))

if __name__ == "__main__":
    run_train_convnext_identifier()
