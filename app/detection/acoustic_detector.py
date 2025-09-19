"""Mock acoustic sensor detector for troop identification."""
from __future__ import annotations

from pathlib import Path
from typing import List


def detect_acoustic(csv_path: str) -> List[dict]:
    """Convert acoustic feature CSV rows into detections.

    The CSV is expected to contain columns: ``class`` and ``confidence``.
    """
    import pandas as pd  # heavy; import lazily
    df = pd.read_csv(Path(csv_path))
    detections = []
    for _, row in df.iterrows():
        detections.append({"class": row.get("class", "unknown"), "confidence": float(row.get("confidence", 0.5))})
    return detections
