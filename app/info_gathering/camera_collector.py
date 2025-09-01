"""Capture frames from a camera or video stream at intervals."""

from pathlib import Path
import time
import cv2


def capture_frames(source: int | str, out_dir: Path, interval: int = 5) -> None:
    """Capture frames from ``source`` every ``interval`` seconds into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video source: {source}")
    idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        path = out_dir / f"frame_{idx:06d}.jpg"
        cv2.imwrite(str(path), frame)
        print(f"Saved {path}")
        idx += 1
        time.sleep(interval)
    cap.release()


def _parse_args():
    import argparse

    parser = argparse.ArgumentParser(description="Capture periodic frames")
    parser.add_argument("source", help="Camera index or video path")
    parser.add_argument("out_dir", type=Path, help="Directory to store frames")
    parser.add_argument("--interval", type=int, default=5, help="Seconds between captures")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    capture_frames(args.source, args.out_dir, args.interval)


if __name__ == "__main__":
    main()
