"""CLI to train Gaussian pointcloud models."""
from __future__ import annotations

import argparse

from ..training import train_gaussian_pointcloud_model


def run_gaussian_pointcloud_training() -> None:
    parser = argparse.ArgumentParser(description="Train Gaussian pointcloud model")
    parser.add_argument("csv", help="CSV file with x,y,z,label columns")
    parser.add_argument(
        "--model", default="gaussian_pointcloud_model.json", help="Output model JSON"
    )
    args = parser.parse_args()
    path = train_gaussian_pointcloud_model(args.csv, args.model)
    print(f"Saved model to {path}")
