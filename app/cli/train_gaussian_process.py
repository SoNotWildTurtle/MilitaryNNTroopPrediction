"""CLI to train Gaussian Process models from image/sensor pairs."""
from __future__ import annotations

import argparse
from pathlib import Path

from ..training import train_gaussian_process


def run_train_gaussian_process() -> None:
    parser = argparse.ArgumentParser(description="Train Gaussian Process model")
    parser.add_argument("--images", nargs="+", required=True, help="Image files")
    parser.add_argument("--sensors", nargs="+", required=True, help="Sensor CSV files")
    parser.add_argument("--labels", nargs="+", required=True, help="Class labels")
    parser.add_argument("--model", default="gaussian_process.pkl", help="Output model path")
    args = parser.parse_args()

    imgs = [Path(p) for p in args.images]
    sens = [Path(p) for p in args.sensors]
    train_gaussian_process(imgs, sens, args.labels, Path(args.model))
    print(f"Saved model to {args.model}")


if __name__ == "__main__":
    run_train_gaussian_process()
