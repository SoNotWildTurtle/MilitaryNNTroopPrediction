"""Parse Bluetooth RSSI logs into mock detections.

The log is expected to be a CSV with ``x``, ``y``, ``rssi`` and
``class`` columns. RSSI values are converted to a 0-1 confidence score to
approximate detection strength.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List


Detection = Dict[str, float | str]


def _load_log(log_path: str | Path) -> List[Detection]:
    """Return detections from a Bluetooth RSSI log."""
    log_path = Path(log_path)
    detections: List[Detection] = []
    with log_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                x = float(row.get("x", 0.0))
                y = float(row.get("y", 0.0))
                rssi = float(row.get("rssi", -100))
                cls = row.get("class", "unknown")
                conf = max(0.0, min(1.0, (rssi + 100.0) / 60.0))
                detections.append({
                    "x": x,
                    "y": y,
                    "class": cls,
                    "confidence": conf,
                })
            except (TypeError, ValueError):
                continue
    return detections


def detect_bluetooth_troops(log_path: str | Path) -> List[Detection]:
    """Return troop detections from a Bluetooth log."""
    return [d for d in _load_log(log_path) if d["class"] == "troop"]


def detect_bluetooth_vehicles(log_path: str | Path) -> List[Detection]:
    """Return vehicle detections from a Bluetooth log."""
    return [d for d in _load_log(log_path) if d["class"] == "vehicle"]


def detect_bluetooth_drones(log_path: str | Path) -> List[Detection]:
    """Return drone detections from a Bluetooth log."""
    return [d for d in _load_log(log_path) if d["class"] == "drone"]
