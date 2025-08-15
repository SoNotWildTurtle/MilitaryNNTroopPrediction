"""Predict future positions from recent movement points."""

from typing import List, Dict
from datetime import datetime
import numpy as np


def predict_next_position(positions: List[Dict], dt_seconds: float = 60.0) -> Dict[str, float]:
    """Predict next lat/lon using a constant-velocity Kalman step.

    Parameters
    ----------
    positions: list of dict
        Each dict should contain ``lat``, ``lon`` and ``timestamp`` (datetime).
    dt_seconds: float
        Seconds ahead to predict.
    """
    if len(positions) < 2:
        print("Need at least two positions for prediction")
        return {}

    pts = sorted(positions, key=lambda p: p.get("timestamp", datetime.utcnow()))
    p1, p2 = pts[-2], pts[-1]
    t1 = p1.get("timestamp") or datetime.utcnow()
    t2 = p2.get("timestamp") or datetime.utcnow()
    dt = max((t2 - t1).total_seconds(), 1e-6)

    v_lat = (p2["lat"] - p1["lat"]) / dt
    v_lon = (p2["lon"] - p1["lon"]) / dt
    state = np.array([p2["lat"], p2["lon"], v_lat, v_lon])

    F = np.array([[1, 0, dt_seconds, 0],
                  [0, 1, 0, dt_seconds],
                  [0, 0, 1, 0],
                  [0, 0, 0, 1]])
    pred = F @ state
    return {"lat": float(pred[0]), "lon": float(pred[1])}


def _parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Predict next position from JSON list")
    p.add_argument("positions", help="JSON array of {'lat','lon','timestamp'}")
    p.add_argument("--dt", type=float, default=60.0, help="Seconds ahead to predict")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        import json
        pts = json.loads(args.positions)
        for p in pts:
            ts = p.get("timestamp")
            if isinstance(ts, str):
                p["timestamp"] = datetime.fromisoformat(ts)
    except Exception as e:
        print(f"Failed to parse positions: {e}")
        return
    pred = predict_next_position(pts, args.dt)
    if pred:
        print(pred)


if __name__ == "__main__":
    main()
