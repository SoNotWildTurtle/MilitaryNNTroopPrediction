"""Continuously fetch imagery for an area and run the real-time pipeline."""
import time
import argparse

from . import realtime


def _parse_args():
    parser = argparse.ArgumentParser(description="Monitor an area via Sentinel Hub")
    parser.add_argument("area", help="Area identifier")
    parser.add_argument("model", help="Path to trajectory model")
    parser.add_argument("--interval", type=int, default=300, help="Fetch interval in seconds")
    return parser.parse_args()


def monitor(area: str, model_path: str, interval: int = 300) -> None:
    while True:
        realtime.process_area(area, model_path)
        time.sleep(interval)


def main() -> None:
    args = _parse_args()
    monitor(args.area, args.model, args.interval)


if __name__ == "__main__":
    main()
