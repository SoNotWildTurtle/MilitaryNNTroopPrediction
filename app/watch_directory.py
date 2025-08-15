"""Monitor a directory and run detection when new images appear."""

import time
from pathlib import Path
from typing import Set

from .pipeline import realtime


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path, help="Directory of images")
    parser.add_argument("model", help="Path to trained trajectory model")
    parser.add_argument("area", help="Area identifier for detections")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds")
    return parser.parse_args()


def watch(directory: Path, model_path: str, area: str, poll_interval: int = 10) -> None:
    """Watch ``directory`` for new ``.tif`` files and process them."""
    seen: Set[Path] = set()
    directory.mkdir(parents=True, exist_ok=True)
    print(f"Watching {directory} for new images...")
    while True:
        for path in directory.glob("*.tif"):
            if path not in seen:
                seen.add(path)
                print(f"New image detected: {path}")
                realtime.process_area(area, model_path)
        time.sleep(poll_interval)


def main() -> None:
    args = _parse_args()
    watch(args.directory, args.model, args.area, args.interval)


if __name__ == "__main__":
    main()

