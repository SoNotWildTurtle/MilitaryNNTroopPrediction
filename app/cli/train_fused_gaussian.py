"""CLI to train fused Gaussian models from image/sensor pairs."""
from __future__ import annotations

import argparse

from ..training import train_fused_gaussian_model


def run_train_fused_gaussian() -> None:
    parser = argparse.ArgumentParser(description="Train fused Gaussian model")
    parser.add_argument("csv", help="CSV with image,sensor,label columns")
    parser.add_argument(
        "--model", default="fused_gaussian_model.json", help="Output model JSON"
    )
    args = parser.parse_args()
    path = train_fused_gaussian_model(args.csv, args.model)
    print(f"Saved model to {path}")


if __name__ == "__main__":
    run_train_fused_gaussian()
