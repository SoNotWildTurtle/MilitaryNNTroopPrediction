"""CLI to train acoustic sensor classifier."""
from __future__ import annotations

import argparse

from app.training.acoustic_trainer import train_acoustic_classifier


def run_acoustic_training() -> None:
    parser = argparse.ArgumentParser(description="Train acoustic classifier")
    parser.add_argument("--csv", required=True, help="Path to feature CSV")
    parser.add_argument("--out", required=True, help="Output model path")
    args = parser.parse_args()
    train_acoustic_classifier(args.csv, args.out)
