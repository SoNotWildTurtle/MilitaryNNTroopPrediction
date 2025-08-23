"""Calibrate model confidence using human feedback."""

from pathlib import Path
import csv
from typing import List
import numpy as np
from sklearn.isotonic import IsotonicRegression


def calibrate_confidence(feedback_csv: Path, model_out: Path) -> None:
    """Fit an isotonic regression model to map raw confidence to accuracy.

    Parameters
    ----------
    feedback_csv: Path
        CSV produced by the human feedback GUI with `confidence` and `correct` columns.
    model_out: Path
        Path to save the calibration model (.npz).
    """
    conf: List[float] = []
    correct: List[float] = []
    with feedback_csv.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "confidence" in row and "correct" in row:
                try:
                    conf.append(float(row["confidence"]))
                    correct.append(1.0 if row["correct"].lower() == "true" else 0.0)
                except ValueError:
                    continue
    if not conf:
        raise ValueError("No feedback records with confidence found")
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(conf, correct)
    xs = np.linspace(0, 1, 100)
    ys = iso.predict(xs)
    np.savez(model_out, x=xs, y=ys)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Calibrate detection confidence")
    p.add_argument("feedback_csv", type=Path)
    p.add_argument("out_model", type=Path)
    args = p.parse_args()
    calibrate_confidence(args.feedback_csv, args.out_model)
