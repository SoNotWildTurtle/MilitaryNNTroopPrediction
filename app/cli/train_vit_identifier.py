"""CLI to train a Vision Transformer classifier."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..training.vit_trainer import train_vit_classifier


def run_train_vit_identifier() -> None:
    parser = argparse.ArgumentParser(description="Train ViT target classifier")
    parser.add_argument("--images", nargs="+", required=True, help="Image files")
    parser.add_argument("--labels", nargs="+", required=True, help="Class labels")
    parser.add_argument("--model", default="vit_classifier.pkl", help="Output model path")
    args = parser.parse_args()

    imgs = [Path(p) for p in args.images]
    train_vit_classifier(imgs, args.labels, Path(args.model))
    print(f"Saved model to {args.model}")


if __name__ == "__main__":
    run_train_vit_identifier()
