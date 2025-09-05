"""Iterative self-training loop."""

from pathlib import Path
from typing import List

from ..cli.self_reinforce import self_reinforce


def self_training_loop(
    new_images: Path,
    train_dir: Path,
    val_dir: Path,
    classes: List[str],
    model_path: Path,
    iterations: int = 3,
    epochs: int = 5,
    ) -> None:
    """Run multiple self-reinforcement cycles."""

    for i in range(iterations):
        print(f"\n=== Self-training iteration {i+1}/{iterations} ===")
        self_reinforce(
            new_images,
            train_dir,
            val_dir,
            classes,
            model_path,
            epochs=epochs,
            model_path=model_path,
        )


def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Iterative self-training loop")
    p.add_argument("new_images", type=Path)
    p.add_argument("train_dir", type=Path)
    p.add_argument("val_dir", type=Path)
    p.add_argument("model_path", type=Path, help="Model path for output and labeling")
    p.add_argument("--classes", nargs="+", required=True)
    p.add_argument("--iterations", type=int, default=3)
    p.add_argument("--epochs", type=int, default=5)
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    self_training_loop(
        args.new_images,
        args.train_dir,
        args.val_dir,
        args.classes,
        args.model_path,
        iterations=args.iterations,
        epochs=args.epochs,
    )


if __name__ == "__main__":
    main()
