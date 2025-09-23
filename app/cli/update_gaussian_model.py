"""CLI to update Gaussian point-cloud models with new data."""
from __future__ import annotations

import argparse

from app.training.gaussian_pointcloud_update import update_gaussian_pointcloud_model


def run_gaussian_update() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="CSV with x,y,z,label columns")
    parser.add_argument(
        "--model",
        default="gaussian_pointcloud_model.json",
        help="Existing model JSON to update",
    )
    args = parser.parse_args()
    path = update_gaussian_pointcloud_model(args.csv, args.model)
    print(f"Updated model saved to {path}")


if __name__ == "__main__":
    run_gaussian_update()
